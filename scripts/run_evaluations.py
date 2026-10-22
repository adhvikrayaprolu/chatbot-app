"""Serial, resumable local pipeline. Run after source review, ablation and freezing.

This coordinator does not create annotations, change frozen choices or publish to GitHub.
Unix file locking prevents two copies from contending for the same measured model service.
"""

import argparse
import csv
import fcntl
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def export_generations(split):
    """Export closed generation journals only; never read an active writer's journal."""
    from evaluation import METHODS, PRIVATE, PUBLIC, questions, rows, save

    records = rows(PRIVATE / f"{split}-runs.jsonl")
    methods = {}
    for method in METHODS:
        group = [r for r in records if r["method"] == method]
        methods[method] = {
            "recorded": len(group),
            "succeeded": sum(r["status"] == "complete" for r in group),
            "failed": sum(r["status"] != "complete" for r in group),
        }
        for status in ("complete", "failed"):
            times = sorted(
                (r["result"]["seconds"] if status == "complete" else r["seconds"])
                for r in group
                if r["status"] == status
            )
            methods[method][status + "_latency"] = {
                "n": len(times),
                **{
                    f"p{p}": times[min(len(times) - 1, int((len(times) - 1) * p / 100))] if times else None
                    for p in (50, 90, 95)
                },
            }
    expected = len(questions(split)) * len(METHODS) * (3 if split == "heldout" else 1)
    save(
        PUBLIC / f"{split}-generation-summary.json",
        {
            "status": "complete" if len(records) == expected else "incomplete",
            "expected": expected,
            "recorded": len(records),
            "methods": methods,
            "note": "Generation only; semantic scoring is separate. Failed-response token usage is unavailable.",
        },
    )
    keys = [
        "id",
        "category",
        "method",
        "repeat",
        "status",
        "error",
        "seconds",
        "input_tokens",
        "output_tokens",
        "model_calls",
        "load_seconds",
    ]
    with (PUBLIC / f"{split}-generation-metrics.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=keys, lineterminator="\n")
        writer.writeheader()
        for record in records:
            item = {key: record.get(key) for key in keys[:6]}
            item["seconds"] = record["result"]["seconds"] if record["status"] == "complete" else record["seconds"]
            for key in keys[7:]:
                item[key] = record.get("result", {}).get(key)
            writer.writerow(item)



def launch_detached(phase):
    """Keep a long run independent of its terminal; the worker still owns the serial lock."""
    private = ROOT / "instance/benchmarks"
    private.mkdir(parents=True, exist_ok=True)
    with (private / "pipeline.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("An evaluation coordinator is already running.") from None
    command = [sys.executable, "-u", str(Path(__file__).resolve()), "--phase", phase]
    if sys.platform == "darwin" and shutil.which("caffeinate"):
        command = ["caffeinate", "-i", *command]
    with (private / "pipeline.log").open("ab") as log:
        process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
    (private / "detached-launch.json").write_text(json.dumps({"pid": process.pid, "phase": phase}) + "\n")
    print("Started independent evaluation process", process.pid, "; inspect instance/benchmarks/pipeline-status.json and pipeline.log.")


def main():
    private = ROOT / "instance/benchmarks"
    private.mkdir(parents=True, exist_ok=True)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("development", "heldout", "external", "all"), default="all")
    parser.add_argument("--detach", action="store_true", help="Run independently of this terminal; inspect private progress/log files.")
    args = parser.parse_args()
    if args.detach:
        launch_detached(args.phase)
        return
    commands = {
        "development": [
            ("evaluation.py", "run", "--split", "development"),
            ("evaluation.py", "score", "--split", "development"),
            ("evaluation.py", "report", "--split", "development"),
        ],
        "heldout": [
            ("evaluation.py", "run", "--split", "heldout"),
            ("evaluation.py", "score", "--split", "heldout"),
            ("evaluation.py", "report", "--split", "heldout"),
        ],
        "external": [
            ("evaluation_external.py", "qasper"),
            ("evaluation_external.py", "calibrate"),
            ("evaluation_external.py", "report"),
        ],
    }
    with (private / "pipeline.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("An evaluation coordinator is already running. Resume after it exits.") from None
        phases = list(commands) if args.phase == "all" else [args.phase]
        for phase in phases:
            for command in commands[phase]:
                state = {
                    "phase": phase,
                    "command": list(command),
                    "status": "running",
                    "pid": __import__("os").getpid(),
                    "started_at": time.time(),
                }
                state_path = private / "pipeline-status.json"
                temporary = state_path.with_suffix(".tmp")
                temporary.write_text(json.dumps(state) + "\n")
                temporary.replace(state_path)
                result = subprocess.run([sys.executable, *command], cwd=ROOT)
                state.update(
                    status="complete" if result.returncode == 0 else "paused" if result.returncode == 75 else "failed",
                    completed_at=time.time(),
                    exit_code=result.returncode,
                )
                temporary.write_text(json.dumps(state) + "\n")
                temporary.replace(state_path)
                if result.returncode:
                    raise SystemExit(result.returncode)
                if command[1] == "run":
                    export_generations(phase)
        print(
            "Requested execution phases finished. Inspect score failures and perform the separate 24-case audit before recommending a method."
        )


if __name__ == "__main__":
    main()
