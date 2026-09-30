# Project
Maintain independent conversations with a language-model chatbot.

# Architecture
app.py: Flask routes and readiness; gpt_handler.py: stateless demo/OpenAI boundary; storage.py: owner-scoped SQLite persistence; templates/ and static/: vanilla browser UI.

# Local Development
Follow the verified root README workflow. Root Makefiles coordinate Python/React environments where present; Spring defaults to persistent local H2; Android needs JDK17 and an explicit SDK path. Do not use source-level credentials or mutate live Firebase.

# Validation
Recommended startup: copy `.env.example` to `.env`, then `docker compose up --build --wait --wait-timeout 90`. Native setup/run/check commands: `make setup; make dev; make test` (run as separate commands). See README for prerequisites. Behavioral tests are mandatory and CI runs them; do not reduce checks to syntax or zero-test builds. Provider tests use fakes or demo-gatherlink emulators.

# Frontend Rules
Keep the native stack (JSP, vanilla HTML or Android Java/XML). Preserve keyboard/accessibility, loading/error/empty states; do not migrate to React.

# Backend Rules
Preserve existing API behavior unless the selected issue explicitly changes it. Validate ownership, inputs and provider failures. Add rollback/permission tests before splitting responsibilities. Never print credentials or use real paid/cloud integrations in tests without explicit authorization.

# Testing Rules
Add meaningful regression tests for the selected workflow, including failure/authorization paths. Use fakes or local emulators; document remaining test gaps. Measure a baseline before any performance claim.

# GitHub Workflow
Read open GitHub issues as the work source. Branch from current main as codex/<issue>-<scope>; link the real issue in a draft PR, record validation and verification limits. Use Closes #N only when all criteria are met; issue closes on human merge, not when the draft opens. Never merge or push directly to main.

# Do Not
Do not commit secrets, migrate frameworks, change unrelated features, deploy, rotate credentials or mutate live cloud data. Inspect open PRs before selecting an issue; the quality integration PR publishes earlier product and control-plane work. Never redo work already present in an active PR.

# Issue Selection Rules
1. Read the Portfolio readiness tracking meta issue; stop if complete.
2. Search open issues labelled automation:ready; exclude any blocked/human-review/do-not-touch issue.
3. Select P0, then P1, then P2; confirm all dependencies are closed and accepted. Within a priority choose foundations first, then oldest issue.
4. Choose one coherent issue; skip work already covered by an open PR.
5. If credentials/decisions/failed baseline block it, document the blocker and remove ready eligibility.
6. Implement, run canonical checks and issue-specific tests, open a linked draft PR. Never merge.
