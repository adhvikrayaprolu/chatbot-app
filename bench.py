"""Fast leaderboard for document search and answering methods.

Two tracks share the frozen question suite and private source annotations:

* ``retrieval`` measures the evidence each method would hand the generator, under the
  same 3,072-token budget: passage recall, gold-page hit rate, MRR, model calls and latency.
* ``answers`` runs the full pipeline and grades it: correctness (abstention rules first,
  then a semantic judge), citation precision against annotated pages, calls and latency.

Runs are journaled per (question, method) and resume after interruption. ``report`` writes
aggregate-only ``benchmarks/leaderboard.{md,json}``; answers and passages stay in instance/.

    python bench.py retrieval [--split all] [--methods lexical,dense,...]
    python bench.py answers   [--split development] [--methods rag,okf,...]
    python bench.py report
"""

from __future__ import annotations

import argparse
import os
import re
import statistics
import time
from pathlib import Path

from evaluation import PRIVATE, PUBLIC, baseline, journal, knowledge, questions, read, require_service, rows, save
from knowledge import create_models
from strategies import STRATEGIES, decision

OWNER = "local-evaluation"
RETRIEVAL = ["lexical", "dense", "hybrid", "rerank", "scoped", "okf", "agentic"]
ANSWERS = ["no_retrieval", "rag", "rerank", "scoped", "okf", "agentic", "gold_evidence"]
LABELS = {
    "lexical": "BM25 (FTS5)", "dense": "Dense cosine", "hybrid": "Hybrid RRF", "rag": "Standard RAG (hybrid)",
    "rerank": "Hybrid + LLM rerank", "scoped": "TOC-scoped hybrid", "okf": "OKF outline navigation",
    "agentic": "Agentic RAG (LangGraph)", "no_retrieval": "No retrieval (control)", "gold_evidence": "Gold evidence (ceiling)",
}
GRADE = {
    "type": "object",
    "properties": {"correct": {"type": "boolean", "description": "True when the answer states the reference fact, allowing paraphrase, extra correct detail and equivalent code or arithmetic."}},
    "required": ["correct"],
}


def slug(name: str) -> str:
    if name == "ollama":
        name = "ollama:" + os.getenv("LOCAL_CHAT_MODEL", "qwen3:4b")
    return re.sub(r"[^A-Za-z0-9.-]+", "_", name)


def journal_path(track: str, generator: str, judge: str | None = None) -> Path:
    """One journal per model setup so runs with different generators never mix."""
    suffix = f"@{slug(generator)}" + (f"@judge-{slug(judge)}" if judge else "")
    return PRIVATE / f"bench-{track}{suffix}.jsonl"


def corpus(generator: str):
    k = knowledge()
    k.models = create_models(generator)
    did = (PRIVATE.parent / "textbook-id.txt").read_text().strip()
    annotations = {a["id"]: a for a in read(PRIVATE / "annotations.json")}
    return k, did, annotations


def evidence_for(k, did: str, q: dict, method: str) -> tuple[list[dict], dict]:
    if method in ("lexical", "dense", "hybrid"):
        return k.search(OWNER, did, q["question"], mode=method), {"calls": 0, "input_tokens": 0, "output_tokens": 0}
    acquired = STRATEGIES[method](k, OWNER, did, q["question"], q["history"])
    return acquired["evidence"], acquired


def retrieval(split: str, methods: list[str], limit: int | None, generator: str, judge: str):
    k, did, annotations = corpus(generator)
    require_service(k)
    path = journal_path("retrieval", generator)
    done = {(r["id"], r["method"]) for r in rows(path)}
    cases = [q for q in questions(None if split == "all" else split) if not annotations[q["id"]]["unanswerable"]][:limit]
    for q in cases:
        gold, pages = set(annotations[q["id"]]["gold_ids"]), set(annotations[q["id"]]["source_pages"])
        for method in methods:
            if (q["id"], method) in done:
                continue
            record = {"id": q["id"], "category": q["category"], "split": q["split"], "method": method}
            started = time.perf_counter()
            try:
                hits, usage = evidence_for(k, did, q, method)
                selected = k.select_evidence(hits)
                ids = [h["id"] for h in selected]
                first = next((i for i, cid in enumerate(ids) if cid in gold), None)
                record.update(
                    status="complete", seconds=time.perf_counter() - started, calls=usage["calls"],
                    tokens=usage["input_tokens"] + usage["output_tokens"], evidence=len(ids),
                    recall=len(gold & set(ids)) / len(gold) if gold else None,
                    page_hit=bool(pages & {h["page"] for h in selected}),
                    rr=0.0 if first is None else 1 / (first + 1),
                )
            except Exception as error:
                require_service(k)
                record.update(status="failed", error=type(error).__name__, seconds=time.perf_counter() - started)
            journal(path, record)
            print("retrieval", q["id"], method, record["status"], f"{record['seconds']:.1f}s", flush=True)


def grade(judge, q: dict, annotation: dict, result: dict) -> dict:
    reply = result["reply"]
    abstained = reply.startswith("Insufficient evidence")
    if annotation["unanswerable"] or abstained:
        return {"correct": abstained == annotation["unanswerable"], "judged": False}
    verdict, _ = decision(
        judge,
        "Grade a study assistant's answer against the reference answer. Judge only whether the answer is correct; ignore citation markers.",
        f"Question: {q['question']}\nReference answer: {annotation['reference']}\nAssistant answer: {reply}",
        GRADE,
    )
    return {"correct": bool(verdict.get("correct")), "judged": True}


def answers(split: str, methods: list[str], limit: int | None, generator: str, judge: str):
    k, did, annotations = corpus(generator)
    require_service(k)
    grader = k.models if judge == generator else create_models(judge)
    chunks = {c["id"]: c for c in k.chunks(OWNER, did)}
    path = journal_path("answers", generator, judge)
    done = {(r["id"], r["method"]) for r in rows(path)}
    for q in questions(None if split == "all" else split)[:limit]:
        annotation = annotations[q["id"]]
        pages = set(annotation["source_pages"])
        for method in methods:
            if (q["id"], method) in done:
                continue
            record = {"id": q["id"], "category": q["category"], "split": q["split"], "method": method}
            try:
                if method in ("no_retrieval", "gold_evidence"):
                    gold = [chunks[cid] for cid in annotation["gold_ids"]]
                    result = baseline(k, did, q, gold, method)
                else:
                    result = k.answer(OWNER, did, q["question"], history=q["history"], method=method)
                cited = result["citations"]
                record.update(
                    status="complete", seconds=result["seconds"], calls=result["model_calls"],
                    tokens=result["input_tokens"] + result["output_tokens"],
                    abstained=result["reply"].startswith("Insufficient evidence"),
                    citation_precision=(sum(c["page"] in pages for c in cited) / len(cited)) if cited and pages else None,
                    **grade(grader, q, annotation, result),
                )
            except Exception as error:
                require_service(k)
                record.update(status="failed", error=type(error).__name__, correct=False)
            journal(path, record)
            print("answers", q["id"], method, record["status"], record.get("correct"), flush=True)


def mean(values) -> float | None:
    values = [v for v in values if v is not None]
    return round(statistics.fmean(values), 3) if values else None


def percentile(values, p: int) -> float | None:
    values = sorted(values)
    return round(values[min(len(values) - 1, int((len(values) - 1) * p / 100))], 2) if values else None


def summarize(records: list[dict], method: str, fields: list[str]) -> dict:
    group = [r for r in records if r["method"] == method]
    ok = [r for r in group if r["status"] == "complete"]
    summary = {"method": method, "label": LABELS[method], "n": len(group), "failed": len(group) - len(ok),
               "p50_seconds": percentile([r["seconds"] for r in ok], 50), "p90_seconds": percentile([r["seconds"] for r in ok], 90),
               "mean_calls": mean(r["calls"] for r in ok), "mean_tokens": mean(r["tokens"] for r in ok)}
    for field in fields:
        summary[field] = mean(float(r[field]) if r.get(field) is not None else None for r in group if r["status"] == "complete" or field == "correct")
    summary["by_category"] = {
        category: mean(float(r[fields[0]]) if r.get(fields[0]) is not None else 0.0 for r in group if r["category"] == category)
        for category in sorted({r["category"] for r in group})
    }
    return summary


def table(lines: list[str], retrieval_summary: list[dict], answer_summary: list[dict]):
    if retrieval_summary:
        n = max(s["n"] for s in retrieval_summary)
        lines += [f"### Retrieval ({n} answerable questions)", "",
                  "| Method | Passage recall | Gold page hit | MRR | Model calls | p50 s | p90 s |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for s in sorted(retrieval_summary, key=lambda s: -(s["page_hit"] or 0)):
            lines.append(f"| {s['label']} | {s['recall']:.3f} | {s['page_hit']:.3f} | {s['rr']:.3f} | {s['mean_calls']:.1f} | {s['p50_seconds']} | {s['p90_seconds']} |")
        lines.append("")
    if answer_summary:
        n = max(s["n"] for s in answer_summary)
        lines += [f"### Answers ({n} questions incl. unanswerable)", "",
                  "| Method | Correct | Citation precision | Model calls | Tokens | p50 s | p90 s | Failed |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for s in sorted(answer_summary, key=lambda s: -(s["correct"] or 0)):
            precision = "—" if s["citation_precision"] is None else f"{s['citation_precision']:.3f}"
            lines.append(f"| {s['label']} | {s['correct']:.3f} | {precision} | {s['mean_calls']:.1f} | {s['mean_tokens']:.0f} | {s['p50_seconds']} | {s['p90_seconds']} | {s['failed']} |")
        categories = sorted({c for s in answer_summary for c in s["by_category"]})
        lines += ["", "Correctness by question type:", "", "| Method | " + " | ".join(categories) + " |", "| --- |" + " ---: |" * len(categories)]
        for s in answer_summary:
            lines.append(f"| {s['label']} | " + " | ".join(f"{s['by_category'].get(c, 0):.2f}" for c in categories) + " |")
        lines.append("")


def report():
    def latest(path):
        # Keep the most recent record for each case so a rerun replaces, never double counts.
        return list({(r["id"], r["method"]): r for r in rows(path)}.values())

    setups: dict[str, dict] = {}
    for path in sorted(PRIVATE.glob("bench-*@*.jsonl")):
        track, generator, *judge = path.stem.split("@")
        setup = setups.setdefault(generator, {"generator": generator, "retrieval": [], "answers": {}})
        records = latest(path)
        if track == "bench-retrieval":
            setup["retrieval"] = [summarize(records, m, ["recall", "page_hit", "rr"]) for m in RETRIEVAL if any(r["method"] == m for r in records)]
        else:
            setup["answers"][judge[0].removeprefix("judge-")] = [
                summarize(records, m, ["correct", "citation_precision"]) for m in ANSWERS if any(r["method"] == m for r in records)]
    save(PUBLIC / "leaderboard.json", {"setups": list(setups.values())})
    lines = ["# Leaderboard", "", "Generated by `python bench.py report` from private run journals. Within a setup every method "
             "shares the generator, prompt and 3,072-token evidence budget; only evidence acquisition differs.", ""]
    for setup in setups.values():
        lines += [f"## Generator: `{setup['generator']}`", ""]
        table(lines, setup["retrieval"], [])
        for judge, summary in setup["answers"].items():
            lines += [f"Judge: `{judge}`", ""]
            table(lines, [], summary)
    (PUBLIC / "leaderboard.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("track", choices=["retrieval", "answers", "report"])
    parser.add_argument("--split", default="all", choices=["all", "development", "heldout"])
    parser.add_argument("--methods", help="comma-separated subset")
    parser.add_argument("--limit", type=int, help="first N questions only (smoke runs)")
    parser.add_argument("--generator", default=os.getenv("GENERATOR", "ollama"), help="ollama or cursor:<model>")
    parser.add_argument("--judge", help="grader for the answer track; defaults to the generator")
    args = parser.parse_args()
    if args.track == "report":
        return report()
    methods = args.methods.split(",") if args.methods else (RETRIEVAL if args.track == "retrieval" else ANSWERS)
    (retrieval if args.track == "retrieval" else answers)(args.split, methods, args.limit, args.generator, args.judge or args.generator)


if __name__ == "__main__":
    main()
