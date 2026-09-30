# Contributing to ArxivBot

Thanks for helping out. ArxivBot is a small FastAPI app that runs in production at
[arxivbot.org](https://arxivbot.org), so every change goes through a pull request.

## Setup

You need [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
git clone https://github.com/k7lim/arxivbot.org.git
cd arxivbot.org
uv sync                      # creates .venv with runtime and dev dependencies
uv run pytest -q             # should pass without a .env or API key
```

To run the app itself you need a free Gemini key from
[Google AI Studio](https://aistudio.google.com/apikey):

```bash
cp .env.example .env         # then set GEMINI_API_KEY
uv run uvicorn arxivbot.main:app --reload
```

Open http://localhost:8000/abs/1706.03762.

## Project layout

| Path | What lives there |
|------|------------------|
| `src/arxivbot/routes/` | Page routes (`pages.py`) and the JSON/streaming API (`api.py`) |
| `src/arxivbot/services/` | Paper fetching, LLM chat with model fallbacks, SQLite storage |
| `templates/`, `static/` | Jinja templates and plain JS/CSS (no build step) |
| `tests/` | pytest suite; page and API tests use FastAPI's `TestClient` |
| `docs/` | UX design notes |

## Making a change

1. Find or open an issue first for anything bigger than a small fix, so we can agree on the approach.
2. Branch from `main`, make your change, and add or update tests. Good patterns to copy:
   `tests/test_pages.py` (monkeypatches paper fetching) and `tests/test_chat_persistence.py` (seeds chats).
3. Run `uv run pytest -q` before pushing.
4. Open a pull request. CI runs the tests; a maintainer reviews and merges.

Merging to `main` deploys to production automatically once tests pass, so keep PRs focused.

### Guidelines

- Tests must not call real LLMs or arXiv. Mock network calls (see `aioresponses` usage in `tests/test_arxiv_fetch.py`).
- Keep the frontend dependency-free: plain JS modules in `static/`, no bundler.
- Match the surrounding code style.

## Issue tracking

GitHub Issues is the place to report bugs and propose features. The maintainer also
uses [beads](https://github.com/steveyegge/beads) (`bd`, stored in `.beads/`) to track work
with coding agents; you don't need it to contribute, and please don't edit `.beads/` in PRs.
`AGENTS.md` is the guide for those agents, not for human contributors.

## Security

Please don't open public issues for vulnerabilities. See [SECURITY.md](SECURITY.md).

## License

By contributing you agree that your contributions are licensed under the [MIT License](LICENSE).
