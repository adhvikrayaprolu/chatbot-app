"""Offline evaluator correctness and public-export privacy boundaries."""

import json

import pytest

import evaluation


def test_numeric_checks_do_not_count_citation_page_numbers():
    assert evaluation.numeric_check("401", "The index is 401 [p3-c0].") == 1
    assert evaluation.numeric_check("401", "The index is 400 [p401-c0].") == 0
    assert evaluation.numeric_check("[2, 3, 6, 8]", "Inclusive scan: [2,3,6,8] [p253-c1]") == 1
    assert evaluation.numeric_check("[2, 3]", "Bad array [2,3,], then [2,3]") == 1
    assert evaluation.numeric_check("[2, 3]", "Bad array [2,3,]") == 0
    assert evaluation.numeric_check("No.", "No.") is None


def test_paired_intervals_cluster_repeats_by_question():
    rows = [
        {"id": q, "method": m, "correctness": v}
        for q in ["a", "b"]
        for _ in range(3)
        for m, v in [("rag", 0), ("agentic", 1)]
    ]
    interval = evaluation.paired_interval(rows, "agentic", "rag", "correctness")
    assert interval == {"difference": 1, "lower": 1, "upper": 1, "paired_questions": 2}


def test_journal_recovers_only_final_torn_write(tmp_path):
    path = tmp_path / "runs.jsonl"
    path.write_text('{"id":"done"}\n{"id":')
    assert evaluation.rows(path) == [{"id": "done"}]
    evaluation.journal(path, {"id": "next"})
    assert len(evaluation.rows(path)) == 2
    path.write_text('{broken}\n{"id":"done"}\n')
    with pytest.raises(ValueError):
        evaluation.rows(path)


def test_public_export_is_allowlisted_and_incomplete(tmp_path, monkeypatch):
    private = tmp_path / "private"
    public = tmp_path / "public"
    private.mkdir()
    public.mkdir()
    monkeypatch.setattr(evaluation, "PRIVATE", private)
    monkeypatch.setattr(evaluation, "PUBLIC", public)
    monkeypatch.setattr(evaluation, "questions", lambda split: [{"id": "a"}])
    evaluation.journal(
        private / "heldout-scores.jsonl",
        {
            "id": "a",
            "category": "factual",
            "method": "rag",
            "repeat": 0,
            "status": "failed",
            "judge_reason": "PRIVATE SOURCE TEXT",
            "secret": "private credential",
        },
    )
    evaluation.report("heldout")
    assert "PRIVATE SOURCE TEXT" not in (public / "heldout-aggregate.csv").read_text()
    assert "private credential" not in (public / "heldout-aggregate.csv").read_text()
    assert json.loads((public / "heldout-summary.json").read_text())["status"] == "incomplete"


def test_original_suite_has_frozen_stratified_sizes():
    questions = evaluation.questions()
    assert len(questions) == 120
    assert len({q["id"] for q in questions}) == 120
    for category in {q["category"] for q in questions}:
        group = [q for q in questions if q["category"] == category]
        assert len(group) == 20
        assert sum(q["split"] == "development" for q in group) == 4
        assert sum(q["split"] == "heldout" for q in group) == 16


def test_external_export_cannot_publish_unexpected_source_fields(tmp_path, monkeypatch):
    import evaluation_external

    private, public = tmp_path / "private", tmp_path / "public"
    private.mkdir()
    public.mkdir()
    monkeypatch.setattr(evaluation_external, "PRIVATE", private)
    monkeypatch.setattr(evaluation_external, "PUBLIC", public)
    evaluation.journal(
        private / "ragbench-calibration.jsonl",
        {
            "id": "example",
            "status": "failed",
            "error": "ValueError",
            "documents": ["PRIVATE SOURCE"],
            "reply": "PRIVATE ANSWER",
        },
    )
    evaluation_external.report()
    assert "PRIVATE" not in (public / "ragbench-calibration.json").read_text()
    assert json.loads((public / "external-summary.json").read_text())["ragbench"]["status"] == "incomplete"


def test_judge_failure_is_recorded_without_losing_the_next_run(tmp_path, monkeypatch):
    private = tmp_path / "private"
    private.mkdir()
    monkeypatch.setattr(evaluation, "PRIVATE", private)
    monkeypatch.setattr(evaluation, "validate_manifest", lambda *args: {})
    monkeypatch.setattr(
        evaluation,
        "questions",
        lambda split: [{"id": key, "question": "Unavailable information?", "history": []} for key in ("a", "b")],
    )
    evaluation.save(
        private / "annotations.json",
        [{"id": key, "reference": "Insufficient evidence", "gold_ids": [], "unanswerable": True} for key in ("a", "b")],
    )
    for key in ("a", "b"):
        evaluation.journal(
            private / "development-runs.jsonl",
            {
                "id": key,
                "category": "unanswerable",
                "method": "rag",
                "repeat": 0,
                "status": "complete",
                "result": {
                    "reply": "Insufficient evidence in this document.",
                    "evidence": [],
                    "seconds": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "model_calls": 0,
                    "evidence_tokens": 0,
                    "load_seconds": 0,
                },
            },
        )
    attempts = 0

    def judge(*args):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError()
        return {"correct": True, "supported": True, "reason": "Appropriate abstention"}, {}

    monkeypatch.setattr(evaluation, "decision", judge)
    fake = type("Knowledge", (), {"models": None, "context": lambda self, evidence: ""})()
    evaluation.score_runs(fake, "document", "development")
    records = evaluation.rows(private / "development-scores.jsonl")
    assert records[0]["score_status"] == "failed"
    assert records[0]["judge_error"] == "TimeoutError"
    assert records[1]["score_status"] == "complete"
    assert records[1]["correctness"] == 1


def test_reviewed_unanswerable_label_overrules_a_contradictory_judge(tmp_path, monkeypatch):
    private = tmp_path / "private"
    private.mkdir()
    monkeypatch.setattr(evaluation, "PRIVATE", private)
    monkeypatch.setattr(evaluation, "validate_manifest", lambda *args: {})
    monkeypatch.setattr(
        evaluation, "questions", lambda split: [{"id": "missing", "question": "A private live value?", "history": []}]
    )
    evaluation.save(
        private / "annotations.json",
        [
            {
                "id": "missing",
                "reference": "Insufficient evidence in this document.",
                "gold_ids": [],
                "unanswerable": True,
            }
        ],
    )
    evaluation.journal(
        private / "development-runs.jsonl",
        {
            "id": "missing",
            "category": "unanswerable",
            "method": "rag",
            "repeat": 0,
            "status": "complete",
            "result": {
                "reply": "Insufficient evidence in this document.",
                "evidence": [],
                "seconds": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "model_calls": 0,
                "evidence_tokens": 0,
                "load_seconds": 0,
            },
        },
    )
    monkeypatch.setattr(
        evaluation,
        "decision",
        lambda *args: ({"correct": False, "supported": False, "reason": "Contradictory verdict"}, {}),
    )
    fake = type("Knowledge", (), {"models": None, "context": lambda self, evidence: ""})()
    evaluation.score_runs(fake, "document", "development")
    scored = evaluation.rows(private / "development-scores.jsonl")[0]
    assert scored["correctness"] == 1
    assert scored["citation_support"] is None
    assert scored["abstention_accuracy"] == 1


def test_generation_export_excludes_private_content_and_preserves_failure_timing(tmp_path, monkeypatch):
    from scripts.run_evaluations import export_generations

    private, public = tmp_path / "private", tmp_path / "public"
    private.mkdir()
    public.mkdir()
    monkeypatch.setattr(evaluation, "PRIVATE", private)
    monkeypatch.setattr(evaluation, "PUBLIC", public)
    monkeypatch.setattr(evaluation, "questions", lambda split: [{"id": "a"}])
    for status in ("complete", "failed"):
        evaluation.journal(
            private / "development-runs.jsonl",
            {
                "id": "a", "category": "factual", "method": "rag", "repeat": 0,
                "status": status, "error": "TimeoutError" if status == "failed" else None,
                "error_detail": "PRIVATE CREDENTIAL", "seconds": 12,
                "result": {"seconds": 3, "reply": "PRIVATE ANSWER", "evidence": ["PRIVATE SOURCE"]},
            },
        )
    export_generations("development")
    csv = (public / "development-generation-metrics.csv").read_text()
    assert "PRIVATE" not in csv
    summary = json.loads((public / "development-generation-summary.json").read_text())
    assert summary["status"] == "incomplete"
    assert summary["methods"]["rag"]["failed_latency"]["p50"] == 12
    assert summary["methods"]["rag"]["complete_latency"]["p50"] == 3
