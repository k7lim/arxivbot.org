# UX: shapeof.ai patterns for lay readers

## Status: first pass shipped (arxivbot.org-nf4)

## The need

ArxivBot's reader is usually not a researcher. They heard about a paper
(a news story, a post, a friend) and want to *get it*: the one big idea, what
the jargon means, and why it matters. When something clicks, they want to pass
that moment on to a friend, and the friend should land on the answer, not an
empty chat.

That gives three jobs:

1. **Get started without knowing what to ask.** A blank chat box next to a
   dense PDF is intimidating. Newcomers need entry points written in their words.
2. **Understand, and trust what you understood.** Answers need everyday
   language by default, a way to drill into a confusing phrase, and a way to
   check the claim against the paper.
3. **Share the a-ha.** A link should point at one answer, make sense to
   someone who wasn't there, and invite them to keep asking without changing
   what the sender shared.

The pre-pass UI served experts: reviewer-style starters ("What are the
limitations?"), a home page that led with the URL trick, and a share button
that copied the whole chat. A recipient who asked a question also appended to
the sender's chat, so the sender's link changed under them.

## Top 20 patterns

From the [Shape of AI](https://www.shapeof.ai/) catalog, ranked by fit with the
three jobs above. "Shipped" means it's in this pass.

| # | Pattern (category) | Job | What it means here | Status |
|---|---|---|---|---|
| 1 | [Initial CTA](https://www.shapeof.ai/patterns/cta) (Wayfinder) | 1 | Home hero is the paper box, under a plain promise: "Understand any AI paper in plain English." | Shipped |
| 2 | [Example gallery](https://www.shapeof.ai/patterns/gallery) (Wayfinder) | 1 | Eight landmark AI papers, each with a one-line hook and a first question; a card opens the paper with that question pre-filled (`?ask=`). | Shipped |
| 3 | [Suggestions](https://www.shapeof.ai/patterns/suggestions) (Wayfinder) | 1 | Starters rewritten for newcomers: "Explain this paper like I'm new to AI", "What's the one big idea?", ... | Shipped |
| 4 | [Follow up](https://www.shapeof.ai/patterns/follow-up) (Wayfinder) | 1, 2 | Every answer ends with three model-written "Ask next" questions, shown as buttons under the latest answer. | Shipped |
| 5 | [Modes](https://www.shapeof.ai/patterns/modes) (Tuner) | 2 | "Plain English / Technical" toggle under the chat box; changes the system prompt's audience block. Remembered per browser. | Shipped |
| 6 | [Inline action](https://www.shapeof.ai/patterns/inline-action) (Prompt action) | 2 | Select a phrase in an answer *or in the paper* and an "Explain ..." bar appears above the chat box. | Shipped |
| 7 | [Transform](https://www.shapeof.ai/patterns/transform) / [Expand](https://www.shapeof.ai/patterns/expand) (Prompt action) | 2 | "Simpler", "Analogy", "Go deeper" buttons on the latest answer. | Shipped |
| 8 | [Summary](https://www.shapeof.ai/patterns/summary) (Prompt action) | 1, 2 | "What's the one big idea?" starter; plain-mode answers open with a one- or two-sentence answer before any detail. | Shipped |
| 9 | [Citations](https://www.shapeof.ai/patterns/citations) (Governor) | 2 | Existing quote links that highlight the passage in the paper; now pointed to in the caveat line and on the home page. | Shipped (existing) |
| 10 | [Caveat](https://www.shapeof.ai/patterns/caveat) (Trust builder) | 2 | Under the chat box: "AI answers can be wrong. Tap a quote to check it in the paper." | Shipped |
| 11 | [Disclosure](https://www.shapeof.ai/patterns/disclosure) (Trust builder) | 3 | Each answer is labeled "ArxivBot · AI answer", which matters most when a screenshot or link travels. | Shipped |
| 12 | [Footprints](https://www.shapeof.ai/patterns/footprints) (Trust builder) | 3 | "Share this answer" links to `/chat/<slug>#m-<n>`; the page scrolls to that answer and outlines it. Uses the native share sheet on touch devices. | Shipped |
| 13 | [Branches](https://www.shapeof.ai/patterns/branches) (Governor) | 3 | A recipient's first question forks the shared chat (`fork: true`): the history is copied into a new chat and the original is untouched. Ownership is tracked in `localStorage`. | Shipped |
| 14 | [Nudges](https://www.shapeof.ai/patterns/nudges) (Wayfinder) | 3 | Recipients see "Someone shared this conversation with you. Keep asking below..." with a "Start fresh" link. | Shipped |
| 15 | [Randomize](https://www.shapeof.ai/patterns/randomize) (Wayfinder) | 1 | "Surprise me" on the home page opens a random gallery paper. | Shipped |
| 16 | [Controls](https://www.shapeof.ai/patterns/controls) (Governor) | 2 | Stop button while an answer streams. | Follow-up issue |
| 17 | [Regenerate](https://www.shapeof.ai/patterns/regenerate) (Prompt action) | 2 | "Try again" on the latest answer; needs a way to replace a saved turn. | Follow-up issue |
| 18 | [Watermark](https://www.shapeof.ai/patterns/watermark) (Trust builder) | 3 | Opt-in link preview for a shared answer (question as og:title, answer card image). Chat previews are currently kept generic on purpose, so this needs an explicit opt-in. | Follow-up issue |
| 19 | [Synthesis](https://www.shapeof.ai/patterns/synthesis) (Prompt action) | 2 | A running glossary of the terms explained so far in the chat. | Follow-up issue |
| 20 | [Personality](https://www.shapeof.ai/patterns/personality) / [Name](https://www.shapeof.ai/patterns/name) (Identifier) | 1 | A consistent, friendly guide voice across empty states, errors and answers. | Follow-up issue |

## Considered and left out

- **Memory, Incognito, Data ownership, Consent:** there are no accounts, and
  chats are link-shared only, so they don't apply yet.
- **Model management, Cost estimates, Draft mode, Parameters:** these expose
  controls a lay reader doesn't need. The Plain/Technical mode covers the one
  setting that matters to them.
- **Inpainting, Restyle, Preset styles:** these are for generated media.

## Implementation notes

- Prompt: `paper_service.LEVEL_INSTRUCTIONS` holds the audience block for each
  level. `FOLLOW_UP_HEADING` (`**Ask next:**`) marks the follow-up block the
  model must end with.
- `static/followups.js` splits that block off the answer text. The split runs
  while the answer streams, so the raw list never flashes on screen. Saved
  messages keep the block, so shared chats also get the buttons.
- `static/explain-selection.js` watches selections in the message list and in
  the same-origin paper iframe.
- API: `level` (`plain` | `technical`) and `fork` on `/api/chat` and
  `/api/chat/stream`. A fork is saved in one transaction
  (`db.save_turn(copy_from_chat_id=...)`), so a failed answer writes nothing.
- Message anchors (`id="m-<n>"`) are the message's index in the chat. Forks
  copy the history, so the indices stay the same.
