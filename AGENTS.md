# Agent Guidelines

## Task Tracking

Use bd as the source of truth for tasks. Do not maintain separate TODO lists unless asked.

Start:
- If possible, run `bd prime`.
- Get work: `bd ready --json`.

During work:
- Claim: `bd update <id> --status in_progress --json`.
- Create discoveries: `bd create "Title" -p 1 -t task --deps discovered-from:<id> --json`.
- Add blockers: `bd dep add <child> <parent> --json`.

Finish:
- Close: `bd close <id> --reason "Summary" --json`.
- Sync and push: `git pull --rebase && bd sync && git push`.
- Verify: `git status` must show "up to date with origin".

Rules:
- Always use `--json` for machine output.
- Always double-quote titles/descriptions.
- Do not use `bd edit` (human-only); use `bd update` flags instead.
- If daemon is unsafe (sandbox/CI/worktrees), use `bd --sandbox` or `bd --no-daemon`.
- Work is NOT complete until `git commit` succeeds. Never say "ready to push when you are".

## Current Issues
- #1: Handle papers without TeX source available (PDF fallback)
- #2: Support bundling multiple arXiv papers (will reintroduce RAG)

## Deployment

**Production database:** `/data/arxivbot.db` (Fly.io persistent volume)
- Do NOT change `DATABASE_PATH` in `fly.toml` without updating the mount destination
- Volume name: `arxivbot_data`

**Deploy commands:** Use `just deploy` (see Justfile)

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
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
