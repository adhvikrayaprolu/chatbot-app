# Reproducible Python dependencies

`requirements.in` contains direct runtime requirements; `requirements-dev.in` adds pytest. The generated `requirements.txt` and `requirements-dev.txt` pin every transitive version with SHA-256 distribution hashes. The development lock is constrained by the runtime lock, keeping shared versions identical. Native setup, Docker and CI install these same files with pip's `--require-hashes`; `pip check` verifies installed metadata compatibility.

## Refresh

Run `make lock` after editing a direct requirement. It creates ignored `.lock-venv/`, installs compiler **uv 0.11.18** there, and regenerates both files. App startup/test installation does not require uv. Existing compatible pins are retained; `make lock LOCK_ARGS=--upgrade` deliberately refreshes transitive versions within the direct requirements. Commit inputs and outputs together, then run `make setup` and `make test`, plus the Compose runtime checks used in CI. Do not edit generated hashes or use `--no-deps` for application installation.

CI checks lock freshness on Python 3.12 and installs/tests the locks on Python 3.12 and 3.13. Docker uses Python 3.12. The compiler generates a universal lock using Python 3.12 as its minimum target, including environment markers and available distribution hashes; this is not a claim of testing every wheel or platform. Native runtime is macOS/Linux: `app.py` uses Unix file locking and is not currently supported on native Windows. The Python image tag/OS packages and pip bootstrap remain separate from Python package locks; whole-image bit-for-bit reproducibility is not claimed.

Dependabot checks pip and Actions weekly, groups compatible Python updates, and limits open version-update PRs to two Python and one Actions PR. No auto-merge is configured. Update PRs must regenerate inputs/locks consistently and pass freshness, application and container checks. Settings apply from the default branch after human merge; security-update limits follow GitHub's separate policy.

## Security and scope

The first exact-version audit found three distinct advisory identifiers affecting Flask 3.1.2, python-dotenv 1.2.1 and pytest 8.4.2 (the tool emitted duplicated records). This change uses their listed fixed releases: Flask 3.1.3, python-dotenv 1.2.2 and pytest 9.0.3. Flask's finding concerns session-aware caching; this app also sets `Cache-Control: no-store`. The dotenv finding concerns environment-file rewriting, which the app does not call. pytest is development tooling. These exposure notes do not replace updates or establish general security.

A package audit is a dated registry snapshot, not proof that an application is secure. Historical notebook credential review remains owner-only issue #4; do not print, validate, revoke or rewrite that credential automatically. No real provider calls are needed for tests.

This lock covers the **published Flask/vanilla app**, based on main `e3dd5e4f`. Pending document-retrieval/UI PRs #15–#19 add Python/Rust/Node dependencies; they must refresh/extend locks and adapt their build/check commands during integration. This draft does not include or validate those new features. Their branches and private data are untouched.
