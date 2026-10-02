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
    monkeypatch.setattr(evaluation, "require_service", lambda *args: None)
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


@pytest.mark.parametrize("unanswerable,vote,expected", [(True, False, 1), (False, True, 0)])
def test_reviewed_abstention_policy_overrules_a_contradictory_judge(tmp_path, monkeypatch, unanswerable, vote, expected):
    private = tmp_path / "private"
    private.mkdir()
    monkeypatch.setattr(evaluation, "PRIVATE", private)
    monkeypatch.setattr(evaluation, "validate_manifest", lambda *args: {})
    monkeypatch.setattr(evaluation, "require_service", lambda *args: None)
    monkeypatch.setattr(
        evaluation, "questions", lambda split: [{"id": "missing", "question": "A private live value?", "history": []}]
    )
    evaluation.save(
        private / "annotations.json",
        [
            {
                "id": "missing",
                "reference": "Insufficient evidence in this document." if unanswerable else "Threads synchronize within a block.",
                "gold_ids": [],
                "unanswerable": unanswerable,
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
        lambda *args: ({"correct": vote, "supported": False, "reason": "Contradictory verdict"}, {}),
    )
    fake = type("Knowledge", (), {"models": None, "context": lambda self, evidence: ""})()
    evaluation.score_runs(fake, "document", "development")
    scored = evaluation.rows(private / "development-scores.jsonl")[0]
    assert scored["correctness"] == expected
    assert scored["citation_support"] is None
    assert scored["abstention_accuracy"] == int(unanswerable)


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


class AvailableModels:
    model = "chat"
    embedding = "embed"
    available = True

    def digest(self, name):
        if not self.available:
            raise ConnectionError("Service stopped")
        return name


@pytest.mark.parametrize("service_lost", [True, False])
def test_generation_outage_pauses_without_consuming_cases_but_healthy_failure_is_recorded(tmp_path, monkeypatch, service_lost):
    private = tmp_path / "private"
    private.mkdir()
    monkeypatch.setattr(evaluation, "PRIVATE", private)
    monkeypatch.setattr(evaluation, "METHODS", ["rag"])
    monkeypatch.setattr(evaluation, "validate_manifest", lambda *args: {})
    monkeypatch.setattr(evaluation, "questions", lambda split: [{"id": key, "category": "factual", "question": "Question?", "history": []} for key in ("a", "b")])
    evaluation.save(private / "annotations.json", [{"id": key, "gold_ids": []} for key in ("a", "b")])
    models = AvailableModels()
    fake = type("Knowledge", (), {"models": models, "chunks": lambda *args: []})()
    calls = []

    def answer(*args):
        calls.append(args[2]["id"])
        if len(calls) == 1:
            models.available = not service_lost
            raise ValueError("Inference failed")
        return {"reply": "A final answer", "seconds": 1}

    monkeypatch.setattr(evaluation, "baseline", answer)
    if service_lost:
        with pytest.raises(evaluation.EvaluationInterrupted):
            evaluation.run(fake, "document", "development")
        assert len(calls) == 1
        first = calls[0]
        assert not (private / "development-runs.jsonl").exists()
        models.available = True
        evaluation.run(fake, "document", "development")
        assert len(calls) == 3
        assert calls[:2] == [first, first]
    else:
        evaluation.run(fake, "document", "development")
    records = evaluation.rows(private / "development-runs.jsonl")
    assert sorted(r["id"] for r in records) == ["a", "b"]
    assert [r["status"] for r in records] == (["complete", "complete"] if service_lost else ["failed", "complete"])
    evaluation.run(fake, "document", "development")
    assert len(evaluation.rows(private / "development-runs.jsonl")) == 2


def test_scoring_service_loss_does_not_persist_a_false_judge_failure(tmp_path, monkeypatch):
    private = tmp_path / "private"
    private.mkdir()
    monkeypatch.setattr(evaluation, "PRIVATE", private)
    monkeypatch.setattr(evaluation, "validate_manifest", lambda *args: {})
    monkeypatch.setattr(evaluation, "questions", lambda split: [{"id": "a", "question": "Unavailable?", "history": []}])
    evaluation.save(private / "annotations.json", [{"id": "a", "reference": "Insufficient evidence", "gold_ids": [], "unanswerable": True}])
    evaluation.journal(private / "development-runs.jsonl", {
        "id": "a", "category": "unanswerable", "method": "rag", "repeat": 0, "status": "complete",
        "result": {"reply": "Insufficient evidence in this document.", "evidence": [], "seconds": 1,
                   "input_tokens": 0, "output_tokens": 0, "model_calls": 1, "evidence_tokens": 0, "load_seconds": 0},
    })
    models = AvailableModels()
    fake = type("Knowledge", (), {"models": models, "context": lambda *args: ""})()

    def judge(*args):
        models.available = False
        raise ConnectionError("Service stopped during judging")

    monkeypatch.setattr(evaluation, "decision", judge)
    with pytest.raises(evaluation.EvaluationInterrupted):
        evaluation.score_runs(fake, "document", "development")
    assert not (private / "development-scores.jsonl").exists()
    models.available = True
    monkeypatch.setattr(evaluation, "decision", lambda *args: ({"correct": True, "supported": False}, {}))
    evaluation.score_runs(fake, "document", "development")
    assert evaluation.rows(private / "development-scores.jsonl")[0]["score_status"] == "complete"


@pytest.mark.parametrize("probe", ["qasper", "calibrate"])
def test_external_service_outage_pauses_without_marking_example_failed(tmp_path, monkeypatch, probe):
    import evaluation_external as external

    private = tmp_path / "private"
    private.mkdir()
    monkeypatch.setattr(external, "PRIVATE", private)
    monkeypatch.setattr(external, "validate_external", lambda *args: None)
    models = AvailableModels()

    def fail_answer(*args, **kwargs):
        models.available = False
        raise ConnectionError("Inference stopped")

    async def fail_scoring(*args):
        models.available = False
        raise ConnectionError("Judge stopped")

    fake = type("Knowledge", (), {"models": models, "answer": fail_answer})()
    if probe == "qasper":
        evaluation.save(private / "qasper-dev.json", {})
        evaluation.save(private / "qasper-imports.json", {"paper": "document"})
        evaluation.save(private / "qasper-sample.json", [{"paper_id": "paper", "question_id": "q", "question": "Question?"}])
        journal = private / "qasper-runs.jsonl"
    else:
        monkeypatch.setattr(external, "ragas_score", fail_scoring)
        evaluation.save(private / "ragbench-sample.json", [{"id": "x", "adherence_score": 1, "relevance_score": 1,
                                                          "documents": ["Original fixture"], "response": "Answer", "question": "Question?"}])
        journal = private / "ragbench-calibration.jsonl"
    with pytest.raises(evaluation.EvaluationInterrupted):
        getattr(external, probe)(fake)
    assert not journal.exists()


def test_detached_launcher_refuses_an_existing_coordinator(tmp_path, monkeypatch):
    import fcntl

    from scripts import run_evaluations as coordinator

    private = tmp_path / "instance/benchmarks"
    private.mkdir(parents=True)
    monkeypatch.setattr(coordinator, "ROOT", tmp_path)
    with (private / "pipeline.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(SystemExit, match="already running"):
            coordinator.launch_detached("all")
    assert not (private / "detached-launch.json").exists()
