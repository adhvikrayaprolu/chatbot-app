# Evaluation methodology and current findings

**Status: incomplete. No quality winner has been established.** See [findings](findings.md). This folder distinguishes
measured development results from pending held-out comparisons. Run status and denominators
are exported explicitly; an empty result is never a zero-quality completed benchmark.

## Questions and source annotations

`questions.json` contains 120 independently written questions: 20 factual lookup, conceptual
explanation, synthesis, code/formula interpretation, follow-ups and unanswerable cases each.
Each category has four development and sixteen held-out questions. Follow-up questions carry
fixed prior turns so every method receives the same context. The first four topic families
are used for development; domain/topic overlap remains a limitation of this small custom suite.
Unanswerable questions involve private, live, unpublished or unmeasured information; many are
comparatively easy to recognize. This suite does not establish broad out-of-domain safety.

Private annotations record original reference answers, eligible PDF pages, source passage IDs,
author/reviewer actors, model digests, timestamps and review verdicts. Annotation authoring uses
source page ranges and does not build OKF concepts from benchmark answers. All 100 source-backed annotations received a local-model review followed by direct
Codex inspection of the relevant extracted PDF passages; 20 unanswerable annotations received
authored scope review. The earlier model review flagged 22 cases, including contradictory
arithmetic verdicts. These were resolved before any held-out answer runs. Review actors,
previous verdicts and corrections remain in the private annotation record. No human validation or independent expert review is claimed. A stratified 24-case
independent audit must be recorded before a final recommendation.

## Comparable methods and controls

Standard RAG retrieves five passages once. The LangGraph agent plans a query, retrieves and
assesses evidence, with at most two rounds and five model calls including its final answer.
OKF navigates a source-backed Markdown root index and passage links, with two hops and three
calls. All use the same local qwen3:4b generator, thinking disabled, temperature zero,
8,192-token context and 1,024-token output cap; the same citation/abstention prompt; and a
3,072-token evidence budget. Generation is schema-constrained to a public final answer.
LangChain supplies model adapters, LangGraph supplies state transitions, and neither owns
storage. Exact cosine and FTS5 search remain in the Rust engine.

No-retrieval runs invoke the same generator with empty evidence and the same abstention policy.
This measures unsupported answering under the policy, rather than unconstrained model knowledge.
Gold-evidence runs supply source annotation passages directly to separate retrieval and generation
failures. Three repetitions of the 96 held-out questions across five conditions produce 1,440
runs. Order is shuffled with seed 481516. Serial local execution avoids simultaneous methods
contending for the model during measured runs. Reports state model residency/timing conditions;
no cold-start or performance-improvement claim is made without a comparable measurement.

Freeze corpus/extraction, annotations, tokenizer/model digests, prompts, budgets, implementation
hashes and hardware after development work. The runner rejects changed manifests. Development
retrieval ablations compare lexical, dense and hybrid modes; no tuning uses held-out outcomes.

## Metrics and uncertainty

Measure source passage ID recall against annotated evidence, citation ID validity, automated
citation support, correctness, abstention accuracy, tokens, model calls, failures and latency
p50/p90/p95. Numeric/vector answers receive deterministic checks, combined with the semantic judge
rather than allowing a matching incidental number to establish correctness. Scalar checks
have a relative tolerance of 1e-6; judge errors and incidental matches still need audit.
Citation ID validity is syntactic, not a guarantee of support. Passage recall depends on chunk
boundaries and annotation completeness; it is not semantic recall of all acceptable evidence.

Local Ragas faithfulness and response relevance are supplemental automated metrics. Ragas uses
the same local model and embedding service, with one relevance-generation sample and bounded
retry; failures/null scores remain visible. The small local model can contradict its own verdict
rationale. Judge errors and self-evaluation bias must be assessed through calibration and audit.
Reported correctness for nonnumeric cases remains an automated estimate, not expert ground truth.
Question-paired bootstrap intervals cluster repetitions by question (2,000 draws); repeated
outputs are not treated as independent questions. Category results and denominator counts are
reported alongside aggregate metrics. A final recommendation requires complete scored runs and
audit, and may remain inconclusive.

## External probes

QASPER uses a fixed 50-question validation sample, one question per paper, excluding selected
figure/table evidence. It evaluates document QA on each complete paper using all three methods;
150 runs are distinct from the textbook comparison. The first dataset annotation is recorded;
multiple valid references and extraction artifacts are limitations. Paragraph recall uses exact
normalized containment as a conservative proxy, not the official QASPER evidence F1 metric.

RAGBench uses 50 labeled `emanual` test examples whose full context fits the shared budget.
It calibrates grounding and sentence relevance evaluators against published labels, reporting
MAE/correlation and failures. It does **not** evaluate this application's end-to-end retriever.
Ragas response relevance differs from labeled context relevance; a separate sentence-selector
estimates the latter. Faithfulness is continuous while RAGBench adherence is binary, so direct
comparison requires care. The single-domain sample cannot establish cross-domain judge accuracy.
Exact revision, download hashes, sample IDs, seed and licenses are recorded in the public files.

Primary sources: [QASPER dataset](https://allenai.org/data/qasper),
[RAGBench paper](https://arxiv.org/abs/2407.11005),
[RAGBench dataset](https://huggingface.co/datasets/galileo-ai/ragbench),
[Ragas evaluation](https://docs.ragas.io/en/stable/), and
[OKF v0.2 specification](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md).
QASPER and RAGBench are CC BY 4.0; public sample manifests credit their authors through these
links. Source corpus copies and detailed outputs stay local.

## Reproduce locally

Install the application/toolchain/models per the root README, then install optional evaluation
packages (they are not needed by the application or offline CI):

```sh
.venv/bin/pip install -r requirements-eval.txt
# Local import into the evaluation registry; never commits the PDF.
.venv/bin/python scripts/import_evaluation_corpus.py /path/to/your/textbook.pdf
.venv/bin/python evaluation.py prepare
# Verify reference answers/source IDs and record annotation reviewers before freezing.
.venv/bin/python evaluation.py ablate
.venv/bin/python evaluation.py freeze
.venv/bin/python evaluation.py run --split development
.venv/bin/python evaluation.py score --split development
.venv/bin/python evaluation.py report --split development
.venv/bin/python evaluation.py run --split heldout
.venv/bin/python evaluation.py score --split heldout
.venv/bin/python evaluation.py report --split heldout
.venv/bin/python evaluation_external.py download
.venv/bin/python evaluation_external.py sample
.venv/bin/python evaluation_external.py qasper
.venv/bin/python evaluation_external.py calibrate
.venv/bin/python evaluation_external.py report
# Select the stratified independent audit cases; inspect actual outputs/source evidence.
.venv/bin/python evaluation.py audit-plan
```

Private reference annotations are specific to the selected textbook and are not distributed.
A new user's document requires new source-backed annotations; public questions alone cannot
recreate gold-evidence results. The public original GPU fixture supports application/CI checks
without this copyrighted corpus. Interrupted commands resume from atomic journals. After review and freezing,
`python scripts/run_evaluations.py --phase all` coordinates the commands serially and
records phase progress under ignored `instance/benchmarks/`; it never publishes or merges. Do not run
parallel measured experiments on the same machine. Failed generation records stay failures;
a rerun of a changed configuration needs a new revision, not overwriting prior outcomes.

## Current measured findings

- Private PDF import: 555 pages, 1,040 chunks, one short/empty extraction page, 15,544,320-byte
  SQLite index. Outline-aware import took 65.83 seconds on an Apple M4 with 16 GiB memory.
  This is one local observation with resident models, not a cold-start baseline or speedup claim.
- Development retrieval ablation on 20 available answerable development annotations:
  mean passage ID recall@5 was 0.400 lexical, 0.600 dense and 0.675 hybrid after the completed
  source review. There are 20 measurements per mode; IDs and timings are exported in
  `development-retrieval-ablation.json`.
  Hybrid remains the implementation default. These figures do not establish answer quality.
- Real-model public-fixture checks produce cited answers through all three methods. These are
  smoke checks, not comparative benchmark scores.
- The offline browser, Python/Rust regressions and container checks pass. No textbook content
  is required by CI.

Held-out answer comparison, QASPER execution, RAGBench calibration and 24-case audit remain
incomplete. Their status JSON/CSV files say so explicitly. No ranking or recruiter-facing
performance claim should be inferred from unfinished runs.
