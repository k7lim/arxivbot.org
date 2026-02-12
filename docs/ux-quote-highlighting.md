# UX Design: Bidirectional Quote Highlighting

## Status: Draft
## Issue: arxivbot.org-122

---

## 1. Current State

The split-pane viewer and basic quote highlighting already work:

- **Split-pane:** Paper HTML on the left (iframe via `/ar5iv/{id}`), chat on the right. Draggable resize handle, collapsible paper pane, responsive stacking on mobile.
- **LLM quoting:** System prompt instructs the model to use `> "exact text"` blockquote format. `quote-highlighter.js` extracts these with regex, wraps them in clickable `<a class="quote-link">` elements.
- **Chat → Paper:** Clicking a quote link sends `FIND_AND_HIGHLIGHT` via `postMessage` to the iframe. `ar5iv-bridge.js` fuzzy-matches against a normalized text index, scrolls to the element, and applies a yellow highlight pulse.
- **Paper → Chat:** Not implemented. No way to select text in the paper and find which chat messages referenced it.

### Current Limitations

1. Quotes are format-inferred (regex on `> "..."`) — no structured metadata from the LLM.
2. No section/paragraph IDs or page numbers attached to quotes.
3. No persistent quote storage — quotes exist only as rendered chat text.
4. The `citations` field in the API response is always `[]` (unused).
5. Quote matching is fuzzy substring — can fail on heavily-formatted TeX.
6. No visual indication in the paper of *which* passages have been referenced.

---

## 2. Design Goals

1. **Reliable quote identification** — quotes should be structured, not regex-inferred.
2. **Bidirectional linking** — chat quotes scroll the paper; paper passages link back to chat messages.
3. **Persistent highlights** — accumulate referenced passages across the conversation.
4. **Low disruption** — build on existing architecture (iframe postMessage, SSE streaming, blockquote format).

---

## 3. Quote Identification in LLM Output

### Approach: Structured blockquotes with location hints

Keep the `> "..."` format the user already sees, but enrich the system prompt to elicit section references. The LLM already has the full TeX source, which contains `\section{}`, `\subsection{}`, and paragraph structure.

**Updated system prompt addition:**

```
When quoting, include a section reference in parentheses after the quote:
> "exact text from the paper" (Section 3.2)

If the section is unclear, omit the parenthetical. Never fabricate a section number.
```

**Why not special tokens or JSON?** The output is streamed as markdown and rendered directly in the chat. Any structured format (JSON blocks, XML tags) would be visible during streaming before post-processing, creating a jarring UX. Parenthetical section hints are human-readable and degrade gracefully — they're useful even without JavaScript.

**Post-processing enrichment:** After streaming completes, `processQuotes()` already runs. Extend it to:

1. Parse the optional `(Section X.Y)` suffix from each quote.
2. Attach it as `data-section` on the quote link.
3. Use section info as a primary lookup hint before falling back to fuzzy text search.

### Quote Data Model

```typescript
interface Quote {
  text: string;           // Exact quoted text
  section?: string;       // "3.2", "Introduction", etc.
  messageIndex: number;   // Which chat message contains this quote
  elementId?: string;     // DOM element ID in the paper iframe (once resolved)
}
```

Quotes are ephemeral per-session in the first iteration. Persistent storage is a future concern (see Section 8).

---

## 4. Mapping Quotes to Paper Locations

### Current: Fuzzy text matching (keep as fallback)

`ar5iv-bridge.js` normalizes both the quote and all paragraph text (lowercase, collapse whitespace, normalize unicode/quotes), then does substring matching. This works well for exact quotes and is the right fallback.

### Enhancement: Section-aware lookup

When a quote includes `(Section 3.2)`:

1. **Bridge builds a section index** at initialization alongside the text index. arXiv HTML papers use heading elements (`h2`, `h3`, etc.) with section numbering. Map section numbers to DOM subtrees.
2. **Narrow the search scope:** If `data-section="3.2"` is present, search only within that section's DOM subtree. This reduces false matches and speeds up lookup.
3. **Anchor elements:** When a match is found, tag the matched element with a `data-quote-id` attribute for reverse lookup.

### Matching priority

```
1. Section hint + exact substring match within section → high confidence
2. Section hint + fuzzy match within section → medium confidence
3. Global fuzzy text match (current behavior) → low confidence fallback
4. No match found → show "Quote not found" toast (current behavior)
```

---

## 5. Bidirectional Linking

### Direction 1: Chat → Paper (enhance existing)

**Current:** Click quote → scroll & highlight in paper → fade after 1s.

**Enhancements:**

- **Persistent gutter markers:** After a quote is successfully located, place a small colored dot in the paper's left margin at that paragraph. Multiple quotes in the same paragraph stack dots vertically. Dots persist for the session.
- **Active highlight state:** The clicked quote link in chat gets an `active` class (background highlight) while its corresponding paper passage is highlighted. Clicking a different quote deactivates the previous one.
- **Smooth scroll with offset:** Scroll the matched element to ~30% from the top of the viewport (not flush to top), giving the reader context above.

### Direction 2: Paper → Chat (new)

**Interaction:** User hovers or clicks a gutter marker (dot) in the paper.

**Behavior:**
1. Gutter marker click sends `QUOTE_MARKER_CLICK` message from iframe to parent with the `data-quote-id`.
2. Parent window looks up which chat message(s) contain that quote.
3. Chat pane scrolls to the relevant message and pulses the quote link.
4. If multiple messages reference the same passage, show a small popover listing the messages ("Referenced in messages 2, 5, 7") — clicking one scrolls to it.

**Alternative (simpler v1):** Instead of gutter markers, add a "Referenced passages" mode toggle. When active, all paragraphs that have been quoted get a subtle left-border highlight. Clicking one scrolls the chat to the first message that quoted it.

### Message protocol additions

```javascript
// Parent → iframe
{ type: "MARK_QUOTES", quotes: [{ id, text, section }] }
// Tells iframe to place gutter markers for all session quotes

// iframe → parent
{ type: "QUOTE_MARKER_CLICK", quoteId: "q-3" }
// User clicked a gutter marker; parent should scroll chat to message

// iframe → parent
{ type: "QUOTE_RESOLVED", quoteId: "q-3", elementId: "p-42", found: true }
// Confirms quote was located; parent stores the mapping
```

---

## 6. Visual Treatment

### Color System

Use a single accent color (the existing `#ffc107` amber) with opacity variations:

| Element | Style | Notes |
|---------|-------|-------|
| Quote link in chat (default) | `text-decoration: underline dotted; color: var(--secondary)` | Existing style, keep |
| Quote link in chat (hover) | `text-decoration: underline solid; color: var(--primary)` | Existing style, keep |
| Quote link in chat (active) | `background: rgba(255, 193, 7, 0.15); border-radius: 2px` | New: shows which quote is "selected" |
| Paper highlight (transient) | `background: #fff59d; outline: 2px solid #ffc107` | Existing pulse animation, keep |
| Paper highlight (persistent marker) | `border-left: 3px solid #ffc107` | Subtle, doesn't obscure text |
| Gutter dot | `width: 8px; height: 8px; border-radius: 50%; background: #ffc107` | Positioned in left margin |
| Multiple-reference dot | Same, but with a small count badge (`2`, `3`) | Only if > 1 message references same passage |

### Animations

- **Highlight pulse:** Keep existing 0.5s pulse (2 cycles) for chat→paper navigation.
- **Chat scroll:** Smooth scroll + brief background flash on the target message (0.3s ease-out).
- **Gutter marker appear:** Fade in (0.2s) when a quote is first resolved in the paper.

### Focus Management

- When navigating chat→paper, do NOT steal keyboard focus from the chat input. Users may want to keep typing.
- When navigating paper→chat, scroll the chat pane but keep the paper pane's scroll position stable.

---

## 7. Mobile / Responsive Considerations

### Current behavior (< 768px)

Panes stack vertically: paper on top, chat below. Resize handle hidden.

### Quote navigation on mobile

- **Chat → Paper:** Tapping a quote link should scroll the page to the paper pane (top), highlight the passage, then auto-scroll back to the chat after 3 seconds (with a "Back to chat" floating button as override).
- **Paper → Chat:** Tapping a gutter marker scrolls to the chat pane (bottom) and highlights the message. A "Back to paper" button appears.
- **Collapse behavior:** If the paper pane is collapsed, tapping a quote link should expand it first, then highlight.

### Touch targets

Gutter dots need a minimum 44x44px tap target (even if visually 8px). Use padding on the clickable area.

---

## 8. Multiple Quotes Referencing Nearby Passages

### Scenario

Messages 2, 5, and 7 all quote text from Section 3.1, perhaps overlapping paragraphs.

### Resolution

- **In the paper:** A single gutter marker with a count badge ("3") on the relevant paragraph. Clicking it shows a compact list: "Msg 2: 'our method achieves...', Msg 5: 'the loss function...', Msg 7: 'convergence rate...'". Each entry is clickable.
- **In the chat:** Each quote link navigates independently. Clicking quote in Msg 5 highlights the specific text in the paper, even if adjacent to other quotes.
- **Overlapping text:** If two quotes overlap the same sentence, the most recently clicked one gets the transient highlight. Persistent markers remain for both.

---

## 9. Persistence

### Phase 1 (current task): Session-only

Quotes live in a JavaScript `Map<quoteId, Quote>` in the parent window. Cleared on page refresh. The chat history (including quote text) is already persisted in SQLite via the `messages` table.

When reloading a saved chat (`/chat/{slug}`), re-run `processQuotes()` on all existing messages to rebuild the quote map and re-send `MARK_QUOTES` to the iframe. This gives "free" persistence through existing DB storage.

### Phase 2 (future): Explicit quote storage

Add a `quotes` table:

```sql
CREATE TABLE quotes (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER REFERENCES chats(id),
    message_id INTEGER REFERENCES messages(id),
    quote_text TEXT NOT NULL,
    section_ref TEXT,
    paper_element_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Benefits: faster reload (no re-parsing), shareable highlight links, analytics on which sections are most-discussed.

---

## 10. Implementation Sequence

### Step 1: Enrich system prompt with section references
- Update prompt in `paper_service.py` to request `(Section X.Y)` on quotes.
- Update `extractQuotes()` regex to capture the optional section suffix.
- Attach `data-section` to quote links.

### Step 2: Section-aware matching in iframe bridge
- Build section index in `ar5iv-bridge.js` at initialization.
- Use section hint to narrow search scope in `findQuote()`.
- Fall back to global fuzzy match if section search fails.

### Step 3: Persistent gutter markers
- After each quote resolution, send `MARK_QUOTES` to iframe.
- Iframe places gutter dots with `data-quote-id`.
- Track resolved quotes in a session `Map`.

### Step 4: Paper → Chat navigation
- Iframe sends `QUOTE_MARKER_CLICK` on gutter dot click.
- Parent scrolls chat to the relevant message.
- Handle multiple references with a popover.

### Step 5: Chat reload quote restoration
- On `/chat/{slug}` load, re-run `processQuotes()` on historical messages.
- Rebuild session quote map and gutter markers.

### Step 6: Mobile polish
- Add "Back to chat" / "Back to paper" floating buttons.
- Expand collapsed paper pane on quote click.
- Touch-friendly tap targets on gutter markers.

---

## 11. Open Questions

1. **Should the LLM be prompted for paragraph-level granularity?** Section references are easy to elicit reliably. Paragraph numbers are harder and more error-prone. The fuzzy text match already handles paragraph-level precision — section hints just narrow the search.

2. **PDF fallback:** Issue #1 tracks papers without TeX source. For PDF-only papers displayed via `<embed>` or pdf.js, text search is fundamentally different. Defer bidirectional linking for PDF to that issue.

3. **Multi-paper chats:** Issue #2 tracks bundling multiple papers. Quotes would need a `paper_id` field to disambiguate which paper is being quoted. The quote data model above can be extended with `paperId: string`.

4. **Quote editing by users:** Should users be able to select arbitrary text in the paper and "pin" it as a reference, independent of LLM output? This is a powerful feature but a different interaction model — defer to a separate issue.
