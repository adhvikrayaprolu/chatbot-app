"""Copy a user-supplied PDF into ignored evaluation storage; no network upload."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation import knowledge  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("pdf", type=Path)
args = parser.parse_args()
k = knowledge()
try:
    did = k.import_file("local-evaluation", args.pdf, args.pdf.name, synchronous=True)
    k.ready("local-evaluation", did)
    (Path(__file__).resolve().parents[1] / "instance/textbook-id.txt").write_text(did)
    print("Private corpus ready:", did)
finally:
    k.worker.shutdown(wait=True)
