# ArxivBot

Chat with any arXiv paper using AI. Simply change `arxiv.org` to `arxivbot.org` in any paper URL.

## Quickstart

### 1. Get a Gemini API Key

Get your free API key from [Google AI Studio](https://aistudio.google.com/apikey).

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### 3. Start Qdrant (Vector Database)

```bash
docker-compose up -d qdrant
```

### 4. Install and Run

```bash
# Install dependencies
pip install -e .

# Run the server
uvicorn arxivbot.main:app --reload
```

### 5. Open in Browser

Visit `http://localhost:8000/abs/2401.12345` (replace with any arXiv paper ID).

## Usage

### URL Format

Change any arXiv URL from `arxiv.org` to `arxivbot.org`:

```
https://arxiv.org/abs/2401.12345  →  https://arxivbot.org/abs/2401.12345
https://arxiv.org/pdf/2401.12345  →  https://arxivbot.org/pdf/2401.12345
```

### Shareable Chats

Every conversation gets a unique permalink like:
```
https://arxivbot.org/chat/what-is-the-main-contribution-a1b2c3d4
```

Click "Share" to copy the link. Anyone with the link can view and continue the conversation.

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google AI Studio API key | (required) |
| `LLM_MODEL` | Chat model | `gemini/gemini-3-flash-preview` |
| `EMBEDDING_MODEL` | Embedding model | `gemini/gemini-embedding-001` |
| `QDRANT_URL` | Qdrant server URL | `http://localhost:6333` |
| `DATABASE_PATH` | SQLite database path | `./data/arxivbot.db` |

## Docker Deployment

```bash
# Set your API key
export GEMINI_API_KEY=your-key-here

# Start everything
docker-compose up -d
```

The app will be available at `http://localhost:8000`.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  FastAPI Backend                                        │
│  ├─ /abs/{paper_id}  → New chat UI page                 │
│  ├─ /pdf/{paper_id}  → Redirect to /abs/{paper_id}      │
│  ├─ /chat/{slug}     → Load existing chat (permalink)   │
│  ├─ /api/chat        → POST chat messages               │
│  └─ /api/status/{id} → GET indexing progress            │
├─────────────────────────────────────────────────────────┤
│  Paper Service (paper-qa)                               │
│  └─ Docs.aadd_url() → fetch/index PDF                   │
│  └─ Docs.aquery()   → RAG query with citations          │
├─────────────────────────────────────────────────────────┤
│  Storage                                                │
│  └─ Qdrant (Docker) → Vector store for embeddings       │
│  └─ SQLite → Papers, chats, messages                    │
└─────────────────────────────────────────────────────────┘
```

## License

MIT
