# Findings — work in progress

**No answering-method winner is established.** The long local evaluations are resumable; unfinished runs remain incomplete in the public status files.

## Completed source and retrieval work

The private textbook has 555 PDF pages, 1,040 chunks and a 15,544,320-byte SQLite index. One short/empty extraction page is flagged. Outline-aware ingestion took 65.83 seconds on an Apple M4 with 16 GiB memory and resident local models. This is one observation, not a cold-start baseline or performance improvement claim.

All 120 annotations were reviewed before held-out execution. Codex inspected the relevant extracted source passages for 100 source-backed cases and reviewed the scope of 20 unanswerable cases. No human or independent domain-expert verification is claimed. The earlier local-model annotation review flagged 22 cases; some verdicts contradicted their own arithmetic. Corrections and previous verdicts are retained privately.

| Retrieval mode | Mean annotated passage recall@5 | Questions |
| --- | ---: | ---: |
| Lexical FTS5 | 0.400 | 20 |
| Dense cosine | 0.600 | 20 |
| Hybrid reciprocal-rank fusion | 0.675 | 20 |

![Development retrieval ablation](retrieval-ablation.png)

Hybrid retains the highest observed development mean and remains the default. The sample is small; paired intervals are in `retrieval-ablation-summary.json`. Passage-ID recall is sensitive to annotation coverage and chunk boundaries. It does not measure answer correctness, citation support or robustness on unseen domains.

## Evaluation status

- The frozen textbook comparison has 24 development questions and 96 held-out questions across six categories. Five conditions include standard RAG, agentic RAG, OKF navigation, no-retrieval and gold-evidence controls. Three held-out repetitions require 1,440 generation runs plus separate scoring.
- `development-summary.json` and `heldout-summary.json` report recorded generation, scoring coverage, failures, metric denominators, latency percentiles and paired intervals. CSV exports contain permitted metrics only.
- `external-summary.json` tracks the separate 150-run QASPER experiment and 50-example RAGBench evaluator calibration. Calibration is not end-to-end retrieval performance.
- `audit-sample-ids.json` selects 24 stratified held-out cases for separate inspection of generated answers, source support and judge disagreements. Selection alone is not a completed audit.

## Known errors and interpretation limits

The annotation pilot exposed judge inconsistency, motivating direct source inspection and explicit review actors. Numeric presence checks now require agreement with the semantic correctness judge; an incidental matching number cannot alone establish correctness. Ragas faithfulness and relevance remain supplemental estimates from the same small local model. Scoring failures/nulls are preserved, and sample sizes accompany aggregates.

The text extractor cannot resolve figure-only evidence and can distort mathematics or code layout. Follow-up retrieval may miss context that a bounded agent can reformulate; that is a hypothesis to evaluate, not a measured advantage. OKF navigation must choose among page-range indexes under a two-hop limit; it is not built from benchmark answers. Extra model calls can cost time without improving quality.

A recommendation will require complete comparisons, uncertainty intervals, external calibration and the 24-case audit. An inconclusive outcome is acceptable. Until then, use the standard RAG default for its simpler execution path, without claiming superior measured answer quality.
