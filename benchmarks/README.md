# Evaluation methodology

Results: [findings.md](findings.md).

## Question suite

`questions.json` holds 120 original questions about a GPU-programming textbook, 20 in each category:

| Category | What it tests |
| --- | --- |
| factual | Single-fact lookup (an API name, a constant, a definition) |
| conceptual | Explaining a mechanism in the book's terms |
| synthesis | Combining evidence from more than one section |
| code_formula | Reading kernels, index arithmetic and performance formulas |
| followup | A question that only makes sense given fixed prior turns |
| unanswerable | Plausible questions the book cannot answer; the right response is to abstain |

Each category is split 4 development / 16 held-out. Reference answers, gold passage IDs and source
pages live in a private annotation file next to the indexed PDF, because they quote a copyrighted
book; the public repository carries only the questions and aggregate results.

## Conditions

All conditions share the generator (qwen3:4b via Ollama, temperature 0, thinking off, 8,192-token
context), the answer prompt, a JSON schema that only allows supplied citation IDs or an explicit
abstention, and a 3,072-token evidence budget. Only evidence acquisition differs.

- **Standard RAG**: one hybrid search (BM25 + dense, reciprocal-rank fusion) for five passages.
- **Agentic RAG**: a LangGraph loop that plans a query, retrieves, judges sufficiency and may rewrite
  once (at most five model calls).
- **OKF navigation**: the model reads the document's outline as an Open Knowledge Format bundle,
  picks sections, then picks passages (two hops, no vector search).
- **No retrieval** and **gold evidence** bracket the range: the floor without evidence and the
  ceiling with perfect retrieval.

## Metrics

- Passage recall: fraction of annotated gold passages present in the evidence.
- Correctness: unanswerable cases must abstain and answerable ones must not; numeric answers are
  checked deterministically; everything else goes to a local LLM judge against the reference.
- Citation support: whether cited passages support the answer (cited answers only).
- Latency percentiles, model calls and tokens; failures are kept as failures, never dropped.
- Paired bootstrap intervals (2,000 draws, clustered by question) for method differences.

Development questions were used to fix prompts and grading rules; held-out questions are only for
final numbers.

## External probes (pinned, not yet run)

- [QASPER](https://allenai.org/data/qasper): 50 questions on full NLP papers, one per paper, to check
  the methods outside the textbook.
- [RAGBench](https://huggingface.co/datasets/galileo-ai/ragbench): 50 labeled examples to calibrate
  the local judge against human grounding labels.

Sample IDs, dataset revisions, hashes and licenses (both CC BY 4.0) are in `*-sample-ids.json` and
`external-provenance.json`.

## Reproduce

After the root README setup:

```sh
.venv/bin/pip install -r requirements-eval.txt
.venv/bin/python scripts/import_evaluation_corpus.py path/to/textbook.pdf
.venv/bin/python evaluation.py ablate                       # retrieval modes
.venv/bin/python evaluation.py freeze                       # record hashes before measuring
.venv/bin/python evaluation.py run --split development      # generation, resumable
.venv/bin/python evaluation.py score --split development
.venv/bin/python evaluation.py report --split development
```

Runs journal every case under `instance/benchmarks/` and resume where they stopped. If Ollama goes
away mid-run the case is paused (exit code 75) rather than recorded as a failure. `freeze` records
hashes of the corpus, models, prompts and code so a later run can prove it measured the same thing.
