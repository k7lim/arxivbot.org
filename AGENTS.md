# Agent Guidelines

## Task Tracking

Two trackers, with different jobs. Do not maintain separate TODO lists unless asked.

**GitHub Issues is the public backlog.** Anything an outside contributor could pick up or would want to know about goes there: user-visible bugs, features, roadmap. When unsure, use GitHub.

**bd is agent working memory:**
- the breakdown of a GitHub issue you are working on (`discovered-from` subtasks, blockers)
- ops and prod-only tasks: Fly secrets, the production database, logs, certificates
- spikes, brainstorms, UX review notes, and changes that come down to the owner's taste (voice, copy, branding)

**How they connect:**
- To work a GitHub issue, create a bead with `--external-ref gh-<N>` and put `Fixes #N` in the commit or PR so GitHub closes it.
- Moving a bead to GitHub is one-way: create the issue, then `bd update <id> --external-ref gh-<N>` and close the bead with reason "Moved to GitHub #N".
- Discoveries a contributor could do go to GitHub (`gh issue create`); discoveries that are part of your current work go in bd.
- `.beads/issues.jsonl` is committed to a public repo. Never put secrets, security findings or personal data in bd; report vulnerabilities privately (see `SECURITY.md`).

Start:
- If possible, run `bd prime`.
- Get work: `bd ready --json`.

During work:
- Claim: `bd update <id> --status in_progress --json`.
- Create discoveries: `bd create "Title" -p 1 -t task --deps discovered-from:<id> --json`.
- Add blockers: `bd dep add <child> <parent> --json`.

Finish:
- Close: `bd close <id> --reason "Summary" --json`.
- Export, commit, push: `bd export -o .beads/issues.jsonl && git add .beads/issues.jsonl .beads/interactions.jsonl && git commit`, then `git pull --rebase && git push`. (`bd sync` no longer exists in bd 1.0.)
- Verify: `git status` must show "up to date with origin".

Rules:
- Always use `--json` for machine output.
- Always double-quote titles/descriptions.
- Do not use `bd edit` (human-only); use `bd update` flags instead.
- If bd misbehaves in a sandbox, CI or worktree, use `bd --sandbox`.
- Work is NOT complete until `git commit` succeeds. Never say "ready to push when you are".

## Deployment

**Production database:** `/data/arxivbot.db` (Fly.io persistent volume)
- Do NOT change `DATABASE_PATH` in `fly.toml` without updating the mount destination
- Volume name: `arxivbot_data`

**Every push to `main` deploys to production.** `.github/workflows/fly-deploy.yml` runs the test suite (`.github/workflows/ci.yml`) and then `flyctl deploy` on push, so a failing test blocks the deploy. Still run the tests before you push. This includes docs-only and bd-only commits.
- Confirm the deploy: `gh run watch $(gh run list -L 1 --json databaseId -q '.[0].databaseId') --exit-status`, then `curl -sf https://arxivbot.org/health`.
- `just deploy` does the same thing by hand and needs an authenticated `fly` CLI. Do not run it as well as pushing.
- Protected-workspace agents have no `fly` login. Anything that needs `fly status`, `fly logs` or `fly machines list` is an owner step; say so in the close reason instead of guessing.

## Testing and Verification

- Tests: `uv run pytest -q` (about 100 tests, a few seconds, no `.env` or API key needed). This is the only quality gate; no linter is configured.
- Page and API tests use FastAPI's `TestClient`; follow the patterns in `tests/test_pages.py` (it monkeypatches `paper_service.fetch_paper_metadata`) and `tests/test_chat_persistence.py` (seeding chats).
- In a protected workspace `localhost` is blocked, so `just dev` and `just check` cannot be reached. Verify with `TestClient` tests before pushing, then with read-only `curl` against https://arxivbot.org after the deploy finishes.
- Do not POST to the production chat API unless the issue says you may. Each question spends a small daily free-tier LLM quota and leaves a chat row in the prod database.
- `templates/home.html` and `templates/chat.html` are edited by many issues. Work on one such issue at a time and `git pull --rebase` before starting.

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   bd export -o .beads/issues.jsonl   # then commit it
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
