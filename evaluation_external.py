"""Frozen external probes: QASPER document QA and separate RAGBench calibration.

Source documents, questions, generated replies and evaluator explanations stay private.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import os
import random
import statistics
import tarfile
import time
from typing import Any

import httpx

from evaluation import JUDGE, PRIVATE, PUBLIC, SEED, decision, digest, journal, knowledge, ragas_score, rows, save
from knowledge import METHODS

RAGBENCH_REVISION = "97808f3e5fd16ede40bbff6c2949af8139b2eb7b"
QASPER_URL = "https://qasper-dataset.s3.us-west-2.amazonaws.com/qasper-train-dev-v0.3.tgz"


def download():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=180) as client:
        archive = PRIVATE / "qasper-v0.3.tgz"
        if not archive.exists():
            response = client.get(QASPER_URL)
            response.raise_for_status()
            archive.write_bytes(response.content)
        with tarfile.open(fileobj=io.BytesIO(archive.read_bytes())) as bundle:
            member = bundle.getmember("qasper-dev-v0.3.json")
            stream = bundle.extractfile(member)
            if stream is None:
                raise ValueError("QASPER archive missing validation data")
            (PRIVATE / "qasper-dev.json").write_bytes(stream.read())
        parquet = PRIVATE / "ragbench-emanual.parquet"
        if not parquet.exists():
            response = client.get(
                f"https://huggingface.co/datasets/galileo-ai/ragbench/resolve/{RAGBENCH_REVISION}/emanual/test-00000-of-00001.parquet"
            )
            response.raise_for_status()
            parquet.write_bytes(response.content)
    save(
        PUBLIC / "external-provenance.json",
        {
            "qasper": {"url": QASPER_URL, "sha256": digest(archive), "split": "validation", "license": "CC BY 4.0"},
            "ragbench": {
                "revision": RAGBENCH_REVISION,
                "sha256": digest(parquet),
                "config": "emanual",
                "split": "test",
                "license": "CC BY 4.0",
            },
            "seed": SEED,
        },
    )


def sample(k):
    dataset = json.loads((PRIVATE / "qasper-dev.json").read_text())
    rng = random.Random(SEED)
    ids = sorted(dataset)
    rng.shuffle(ids)
    selected = []
    for pid in ids:
        paper = dataset[pid]
        eligible = [
            q
            for q in paper["qas"]
            if q["answers"] and not any("FLOAT SELECTED" in e for e in q["answers"][0]["answer"]["evidence"])
        ]
        if not eligible:
            continue
        q = rng.choice(eligible)
        a = q["answers"][0]["answer"]
        reference = (
            "Insufficient evidence in this document."
            if a["unanswerable"]
            else str(a["yes_no"])
            if a["yes_no"] is not None
            else a["free_form_answer"] or "; ".join(a["extractive_spans"])
        )
        selected.append(
            {
                "paper_id": pid,
                "question_id": q["question_id"],
                "question": q["question"],
                "reference": reference,
                "annotation_id": q["answers"][0]["annotation_id"],
                "unanswerable": a["unanswerable"],
                "gold_paragraphs": a["evidence"],
            }
        )
        if len(selected) == 50:
            break
    if len(selected) != 50:
        raise ValueError("Insufficient eligible QASPER documents")
    save(PRIVATE / "qasper-sample.json", selected)
    save(
        PUBLIC / "qasper-sample-ids.json",
        [{key: q[key] for key in ("paper_id", "question_id", "annotation_id")} for q in selected],
    )
    import pyarrow.parquet as pq

    candidates = pq.read_table(PRIVATE / "ragbench-emanual.parquet").to_pylist()
    candidates = [
        r
        for r in candidates
        if k.tokens.count("\n".join(r["documents"])) <= 3072 and k.tokens.count(r["response"]) <= 1024
    ]
    candidates.sort(key=lambda r: r["id"])
    rng.shuffle(candidates)
    if len(candidates) < 50:
        raise ValueError("Insufficient full-context RAGBench samples")
    save(PRIVATE / "ragbench-sample.json", candidates[:50])
    save(PUBLIC / "ragbench-sample-ids.json", [r["id"] for r in candidates[:50]])
    save(
        PUBLIC / "external-configuration.json",
        {
            "model_digest": k.models.digest(k.models.model),
            "embedding_digest": k.models.digest(k.models.embedding),
            "tokenizer_digest": k.tokens.fingerprint(),
            "implementation_sha256": {
                name: digest(PUBLIC.parent / name)
                for name in (
                    "knowledge.py",
                    "strategies.py",
                    "evaluation.py",
                    "evaluation_external.py",
                    "retrieval/src/main.rs",
                    "requirements-eval.txt",
                )
            },
            "datasets_sha256": {
                name: digest(PRIVATE / name)
                for name in ("qasper-dev.json", "qasper-sample.json", "ragbench-sample.json")
            },
            "seed": SEED,
            "evidence_budget": 3072,
            "context": 8192,
            "temperature": 0,
            "thinking": False,
            "output_limit": 1024,
            "timing": "serial local runs; method latency excludes the separate judge call",
        },
    )


def validate_external(k):
    config = json.loads((PUBLIC / "external-configuration.json").read_text())
    if (
        config["model_digest"] != k.models.digest(k.models.model)
        or config["embedding_digest"] != k.models.digest(k.models.embedding)
        or config["tokenizer_digest"] != k.tokens.fingerprint()
    ):
        raise ValueError("Frozen external experiment models changed")
    for name, expected in config["implementation_sha256"].items():
        if digest(PUBLIC.parent / name) != expected:
            raise ValueError("Frozen external experiment implementation changed")
    for name, expected in config["datasets_sha256"].items():
        if digest(PRIVATE / name) != expected:
            raise ValueError("Frozen external dataset changed")


def qasper(k):
    validate_external(k)
    papers = json.loads((PRIVATE / "qasper-dev.json").read_text())
    path = PRIVATE / "qasper-runs.jsonl"
    existing = {(r["question_id"], r["method"]) for r in rows(path)}
    imported = (
        json.loads((PRIVATE / "qasper-imports.json").read_text()) if (PRIVATE / "qasper-imports.json").exists() else {}
    )
    for q in json.loads((PRIVATE / "qasper-sample.json").read_text()):
        # Separate evaluation owners bypass the per-browser ten-document limit while retaining ownership checks.
        owner = "qasper:" + q["paper_id"]
        did = imported.get(q["paper_id"])
        if not did:
            paper = papers[q["paper_id"]]
            text = "# " + paper["title"] + "\n\n## Abstract\n" + paper["abstract"] + "\n\n"
            for section in paper["full_text"]:
                text += "## " + section["section_name"] + "\n\n" + "\n\n".join(section["paragraphs"]) + "\n\n"
            source = PRIVATE / "qasper-source.md"
            source.write_text(text)
            did = k.import_file(owner, source, paper["title"], synchronous=True, markdown=True)
            k.ready(owner, did)
            imported[q["paper_id"]] = did
            save(PRIVATE / "qasper-imports.json", imported)
        methods = list(METHODS)
        random.Random(SEED + int(hashlib.sha256(q["question_id"].encode()).hexdigest()[:8], 16)).shuffle(methods)
        for method in methods:
            if (q["question_id"], method) in existing:
                continue
            record = {"question_id": q["question_id"], "paper_id": q["paper_id"], "method": method}
            try:
                result = k.answer(owner, did, q["question"], method=method)
                judged, _ = decision(
                    k.models,
                    "Evaluate correctness and support against the dataset reference and supplied evidence. Accept semantic paraphrases. Return one brief verdict sentence of at most 30 words.",
                    json.dumps(
                        {
                            "question": q["question"],
                            "reference": q["reference"],
                            "answer": result["reply"],
                            "evidence": k.context(result["evidence"]),
                        }
                    ),
                    JUDGE,
                )
                # Evidence paragraph recall uses exact normalized paragraph containment as a conservative proxy.
                context = " ".join(c["text"] for c in result["evidence"])
                normalized = re_space(context)
                gold = q["gold_paragraphs"]
                recall = sum(re_space(p) in normalized for p in gold) / len(gold) if gold else None
                record.update(
                    status="complete",
                    result=result,
                    correctness=int(result["reply"].startswith("Insufficient evidence"))
                    if q["unanswerable"]
                    else int(judged["correct"]),
                    citation_support=int(judged["supported"]) if result["citations"] else None,
                    paragraph_recall=recall,
                    abstention_accuracy=int(result["reply"].startswith("Insufficient evidence") == q["unanswerable"]),
                )
            except Exception as error:
                record.update(status="failed", error=type(error).__name__)
            journal(path, record)
            print("QASPER", q["question_id"], method, record["status"], flush=True)


def re_space(text):
    return " ".join(text.lower().split())


def calibrate(k):
    validate_external(k)
    path = PRIVATE / "ragbench-calibration.jsonl"
    existing = {r["id"] for r in rows(path)}
    for sample in json.loads((PRIVATE / "ragbench-sample.json").read_text()):
        if sample["id"] in existing:
            continue
        record = {
            "id": sample["id"],
            "adherence_label": float(sample["adherence_score"]),
            "relevance_label": sample["relevance_score"],
        }
        start = time.perf_counter()
        try:
            evidence = [{"id": f"p1-c{i}", "page": 1, "text": text} for i, text in enumerate(sample["documents"])]
            result = {"reply": sample["response"], "evidence": evidence}
            record.update(asyncio.run(ragas_score(k, sample["question"], result)))
            if record.get("faithfulness") is None or record.get("relevance") is None:
                raise ValueError("Missing evaluator score")
            sentences = [pair for document in sample["documents_sentences"] for pair in document]
            schema = {
                "type": "object",
                "properties": {
                    "ids": {"type": "array", "items": {"type": "string", "enum": [s[0] for s in sentences]}}
                },
                "required": ["ids"],
            }
            selected, _ = decision(
                k.models,
                "Select the IDs of all source sentences relevant to answering the question. Relevance means helping answer it, not merely being fluent or mentioning the domain.",
                json.dumps({"question": sample["question"], "sentences": sentences}),
                schema,
            )
            if not isinstance(selected.get("ids"), list) or not set(selected["ids"]) <= {s[0] for s in sentences}:
                raise ValueError("Invalid relevance decisions")
            record["context_relevance"] = len(set(selected["ids"])) / len(sentences) if sentences else None
            record["status"] = "complete"
        except Exception as error:
            record.update(status="failed", error=type(error).__name__)
        record["seconds"] = time.perf_counter() - start
        journal(path, record)
        print("RAGBench evaluator calibration", sample["id"], record["status"], flush=True)


def report():
    external: dict[str, Any] = {}
    qasper_rows = rows(PRIVATE / "qasper-runs.jsonl")
    public_rows = []
    for r in qasper_rows:
        item = {
            key: r.get(key)
            for key in (
                "question_id",
                "paper_id",
                "method",
                "status",
                "correctness",
                "citation_support",
                "paragraph_recall",
                "abstention_accuracy",
            )
        }
        for key in ("seconds", "input_tokens", "output_tokens", "model_calls"):
            item[key] = r.get("result", {}).get(key)
        public_rows.append(item)
    save(PUBLIC / "qasper-results.json", public_rows)
    external["qasper"] = {
        "status": "complete" if len(public_rows) == 150 else "incomplete",
        "completed": len(public_rows),
        "expected": 150,
        "failures": sum(r["status"] != "complete" for r in public_rows),
        "methods": {},
    }
    for method in METHODS:
        group = [r for r in public_rows if r["method"] == method]
        stats = {"runs": len(group), "failures": sum(r["status"] != "complete" for r in group)}
        for metric in (
            "correctness",
            "citation_support",
            "paragraph_recall",
            "abstention_accuracy",
            "input_tokens",
            "output_tokens",
            "model_calls",
        ):
            values = [r[metric] for r in group if r.get(metric) is not None]
            stats[metric] = {"mean": statistics.mean(values) if values else None, "n": len(values)}
        latencies = sorted(r["seconds"] for r in group if r.get("seconds") is not None)
        stats["latency"] = {
            f"p{p}": latencies[min(len(latencies) - 1, int((len(latencies) - 1) * p / 100))] if latencies else None
            for p in (50, 90, 95)
        }
        external["qasper"]["methods"][method] = stats
    calibrated = rows(PRIVATE / "ragbench-calibration.jsonl")
    save(
        PUBLIC / "ragbench-calibration.json",
        [
            {
                key: r.get(key)
                for key in (
                    "id",
                    "status",
                    "error",
                    "seconds",
                    "adherence_label",
                    "relevance_label",
                    "faithfulness",
                    "relevance",
                    "context_relevance",
                )
            }
            for r in calibrated
        ],
    )
    external["ragbench"] = {
        "status": "complete" if len(calibrated) == 50 else "incomplete",
        "completed": len(calibrated),
        "expected": 50,
        "failures": sum(r["status"] != "complete" for r in calibrated),
    }
    for prediction, label in [("faithfulness", "adherence_label"), ("context_relevance", "relevance_label")]:
        pairs = [(r[prediction], r[label]) for r in calibrated if r.get(prediction) is not None]
        external["ragbench"][prediction + "_n"] = len(pairs)
        if pairs:
            external["ragbench"][prediction + "_mae"] = statistics.mean(abs(a - b) for a, b in pairs)
            try:
                external["ragbench"][prediction + "_correlation"] = statistics.correlation(
                    [p[0] for p in pairs], [p[1] for p in pairs]
                )
            except statistics.StatisticsError:
                external["ragbench"][prediction + "_correlation"] = None
    save(PUBLIC / "external-summary.json", external)
    print(external)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["download", "sample", "qasper", "calibrate", "report"])
    args = parser.parse_args()
    os.environ["RAGAS_DO_NOT_TRACK"] = "true"
    os.environ["LANGSMITH_TRACING"] = "false"
    if args.command == "download":
        download()
        return
    if args.command == "report":
        report()
        return
    k = knowledge()
    try:
        {"sample": sample, "qasper": qasper, "calibrate": calibrate}[args.command](k)
    finally:
        k.worker.shutdown(wait=True)


if __name__ == "__main__":
    main()
