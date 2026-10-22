# Roadmap: from "RAG over a PDF" to measurably better search for agents

The question this project should answer is no longer "can an LLM chat with a PDF?" but **how should a
model look things up in a long, structured, technical document, and what does each approach cost?**
The pieces are in place: a hard corpus (a 555-page CUDA textbook full of code, formulas and figures),
five strategies behind one interface, and a harness with floor and ceiling controls. Each phase below
adds one idea, a hypothesis, and the benchmark that would confirm or kill it.

## Where it stands

- Hybrid retrieval beats BM25 by a wide margin (recall@5 0.675 vs 0.400) and dense by a little.
- On the development set, one-shot RAG already ties the LangGraph agent (21/24) at half the latency,
  and roughly matches the gold-evidence ceiling. The 4B generator, not retrieval, is the bottleneck
  on the remaining misses.
- OKF navigation over an artificial page-window index failed (recall 0.15). It now walks the book's
  real outline, and the new **scoped** strategy combines the two ideas: the model picks sections,
  vectors rank inside them. See [the leaderboard](../benchmarks/leaderboard.md) for current numbers.

## Phase 1: cheap wins on the existing pipeline

| Idea | Hypothesis | Measure |
| --- | --- | --- |
| **Contextual chunk headers**: prefix each chunk with its outline path ("Ch. 5 › 5.2 CUDA memory types") before BM25 and embedding; optionally a one-sentence model-written situating line | Fixes chunks that are ambiguous out of context; published results show large drops in retrieval misses | Retrieval track, all strategies, before/after |
| **Cross-encoder reranker** (e.g. bge-reranker-v2-m3) instead of the LLM listwise rerank | Same precision gain at about a tenth of the latency | Recall/MRR vs `rerank`, p50 latency |
| **Neighbor expansion**: add the previous/next chunk of each hit while budget allows | Answers split across a chunk boundary stop failing | Gold-page hit rate on synthesis and code questions |
| **Stronger, calibrated judge**: grade with a frontier model through the Cursor backend (`--judge cursor:<model>`), calibrated on the pinned RAGBench sample | Removes self-grading bias from the 4B judge | Judge agreement with RAGBench labels |
| **Finish the held-out split** (96 questions × 3 repeats) | Development conclusions hold on unseen questions | Paired bootstrap intervals |
| **Frontier generator** (`--generator cursor:<model>`) | A stronger model narrows the gap between strategies, or reorders them | Same leaderboard, second generator |

## Phase 2: search as tool use (headline experiment)

Coding agents don't use vector databases. They `grep`, list directories and open files. Give the
model the same kind of tools over the book and let it decide:

- `toc()` and `open_section(id)`: navigate structure (what OKF does, but on demand)
- `search(query, scope?)`: hybrid search, optionally inside sections
- `grep(pattern)`: exact matching for identifiers like `__syncthreads` or `cudaMemcpyAsync`, which embeddings blur
- `read(passage_id, before=1, after=1)`: widen context around a hit

The loop runs under a hard token and call budget and every trajectory is logged.

**Benchmark: "Do agents need embeddings?"** Compare the tool-using agent with and without `search`
(grep + navigation only) against hybrid RAG, on accuracy, latency, tokens and trajectory length
(redundant reads, backtracking). Add a question category of exact-identifier and code-listing lookups,
where lexical tools should win, and report results per category. This turns the project from a RAG
demo into a measured answer to an open question.

## Phase 3: make it useful to other agents

- **MCP server.** Expose `toc`, `search`, `grep` and `read` over a library as a Model Context Protocol
  server, so Claude Code, Claude Desktop or any MCP client can study a book with cited passages. The
  Rust engine already speaks JSON over stdio, so this is a thin layer. Demo: a coding agent writing a
  tiled matrix-multiply kernel while citing the textbook chapter it relied on.
- **Adaptive routing.** RAG and the agent tie on accuracy, but the agent costs 2× latency. Answer with
  RAG first, run a cheap sufficiency check, and escalate to the agent only when it fails. Target: the
  agent's accuracy at close to RAG's median latency, reported as a cost/quality Pareto chart.
- **Long-context baseline.** The whole book is about 300k tokens. With a long-context model and prompt
  caching, measure whether "put the entire book in context" beats retrieval on accuracy, latency and
  cost per question. Either answer is a useful, current result. This one sends the book to a hosted
  model, so it runs only on an explicit opt-in.

## Phase 4: beyond extracted text

- **Page-image retrieval.** pypdf flattens figures, diagrams and equations, and the CUDA book leans on
  them. Index page images with a late-interaction vision retriever (ColPali/ColQwen style) and answer
  with a vision-language model. Add a figure/equation question category to measure the gap against
  text-only retrieval.
- **Compiled knowledge.** OKF exists so agents can keep a knowledge base current with provenance and
  trust metadata. Have an agent compile concept pages across chapters ("shared-memory tiling",
  "warp divergence"), each citing its source passages, then compare answering from compiled concepts
  with answering from raw passages on synthesis questions.

## Benchmark additions

- Question categories: exact identifier / code lookup, figure-dependent, multi-hop across chapters,
  near-miss unanswerable (plausible but absent).
- Metrics: claim-level citation entailment (not only page overlap), evidence sufficiency judged
  directly rather than by gold-ID overlap, cost per correct answer, agent trajectory length.
- External: complete the pinned QASPER probe; add a second long technical corpus so conclusions
  aren't specific to one book.
