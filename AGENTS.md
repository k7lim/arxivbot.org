# Agent Guidelines

## Task Tracking

Use **GitHub Issues** as the source of truth for tasks. Do not use bd/beads or maintain separate TODO lists.

### Creating issues
```bash
gh issue create --title "Title" --body "Description"
```

### Viewing issues
```bash
gh issue list
gh issue view <number>
```

### Updating issues
```bash
gh issue comment <number> --body "Update"
gh issue close <number>
```

### Current issues
- #1: Handle papers without TeX source available (PDF fallback)
- #2: Support bundling multiple arXiv papers (will reintroduce RAG)
