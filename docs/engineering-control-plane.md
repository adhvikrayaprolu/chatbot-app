# Engineering control plane

Maintain independent conversations with a language-model chatbot.

## Setup and validation
Create .venv and install requirements.txt. make check PYTHON=/absolute/path/to/.venv/bin/python validates syntax/dependency imports only. Current app requires source-level provider configuration; do not insert credentials into source. Safe env/offline startup is a blocking issue.

## Verified state
Published main audit SHA: `ecb359748f384e95833311b5563f4f9b6b4fa944`. No root AGENTS.md, issues or PRs existed at this audit. No existing Actions pipeline or meaningful behavior test suite in published main.

## Unmerged work
Earlier local branch `codex/chatbot-engineering-foundation` at `6d2dbf78da828fa1514f826b7678bdd955aa3167` has tested improvements, but is not hosted or merged. Review/reuse it before reimplementing. Its reported checks are not checks of this control-plane branch.

## Backlog and stop rule
Use GitHub issues after publication; local draft identifiers must never be treated as GitHub issue numbers. Portfolio tracking covers core flows, safe configuration, meaningful tests, green PR CI, reproducible setup and concise demo documentation. Stop after the tracker is complete; no speculative features.

## Queue
`is:issue is:open label:"automation:ready" sort:updated-asc` scoped to this repository. Apply priority and dependency checks from AGENTS.md.
