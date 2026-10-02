"""Serial, resumable local pipeline. Run after source review, ablation and freezing.

This coordinator does not create annotations, change frozen choices or publish to GitHub.
Unix file locking prevents two copies from contending for the same measured model service.
"""
import argparse
import fcntl
import json
import subprocess
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
private = root / 'instance/benchmarks'
private.mkdir(parents=True, exist_ok=True)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--phase', choices=('development', 'heldout', 'external', 'all'), default='all')
args = parser.parse_args()
commands = {
    'development': [('evaluation.py', 'run', '--split', 'development'), ('evaluation.py', 'score', '--split', 'development'), ('evaluation.py', 'report', '--split', 'development')],
    'heldout': [('evaluation.py', 'run', '--split', 'heldout'), ('evaluation.py', 'score', '--split', 'heldout'), ('evaluation.py', 'report', '--split', 'heldout')],
    'external': [('evaluation_external.py', 'qasper'), ('evaluation_external.py', 'calibrate'), ('evaluation_external.py', 'report')],
}
with (private / 'pipeline.lock').open('a') as lock:
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('An evaluation coordinator is already running. Resume after it exits.') from None
    phases = list(commands) if args.phase == 'all' else [args.phase]
    for phase in phases:
        for command in commands[phase]:
            state = {'phase': phase, 'command': list(command), 'status': 'running', 'started_at': time.time()}
            state_path = private / 'pipeline-status.json'
            temporary = state_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(state) + '\n')
            temporary.replace(state_path)
            result = subprocess.run([sys.executable, *command], cwd=root)
            state.update(status='complete' if result.returncode == 0 else 'failed', completed_at=time.time(), exit_code=result.returncode)
            temporary.write_text(json.dumps(state) + '\n')
            temporary.replace(state_path)
            if result.returncode:
                raise SystemExit(result.returncode)
    print('Requested execution phases finished. Inspect score failures and perform the separate 24-case audit before recommending a method.')
