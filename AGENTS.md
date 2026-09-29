# Project
Maintain independent conversations with a language-model chatbot.

# Architecture
app.py: Flask routes; gpt_handler.py: OpenAI boundary and currently process-global history; templates/index.html: vanilla UI and browser localStorage. No server persistence in published main.

# Local Development
Create .venv and install requirements.txt. make check PYTHON=/absolute/path/to/.venv/bin/python validates syntax/dependency imports only. Current app requires source-level provider configuration; do not insert credentials into source. Safe env/offline startup is a blocking issue.

# Validation
Canonical command: `make check`. See docs/engineering-control-plane.md for prerequisites and known gaps. A build with zero tests is not behavioral validation. Do not skip a failing check or claim hosted CI passed before a run exists.

# Frontend Rules
Keep the native stack (JSP, vanilla HTML or Android Java/XML). Preserve keyboard/accessibility, loading/error/empty states; do not migrate to React.

# Backend Rules
Preserve existing API behavior unless the selected issue explicitly changes it. Validate ownership, inputs and provider failures. Add rollback/permission tests before splitting responsibilities. Never print credentials or use real paid/cloud integrations in tests without explicit authorization.

# Testing Rules
Add meaningful regression tests for the selected workflow, including failure/authorization paths. Use fakes or local emulators; document remaining test gaps. Measure a baseline before any performance claim.

# GitHub Workflow
Read open GitHub issues as the work source. Branch from current main as codex/<issue>-<scope>; link the real issue in a draft PR, record validation and verification limits. Use Closes #N only when all criteria are met; issue closes on human merge, not when the draft opens. Never merge or push directly to main.

# Do Not
Do not commit secrets, migrate frameworks, change unrelated features, deploy, rotate credentials or mutate live cloud data. Do not treat unmerged local sprint branches as main. Before implementing overlapping work inspect the existing local branch listed in docs/engineering-control-plane.md and avoid duplicate PRs.

# Issue Selection Rules
1. Read the Portfolio readiness tracking meta issue; stop if complete.
2. Search open issues labelled automation:ready; exclude any blocked/human-review/do-not-touch issue.
3. Select P0, then P1, then P2; confirm all dependencies are closed and accepted. Within a priority choose foundations first, then oldest issue.
4. Choose one coherent issue; skip work already covered by an open PR.
5. If credentials/decisions/failed baseline block it, document the blocker and remove ready eligibility.
6. Implement, run canonical checks and issue-specific tests, open a linked draft PR. Never merge.
