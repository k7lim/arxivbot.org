/**
 * ar5iv-bridge.js
 *
 * Injected into proxied ar5iv HTML to enable:
 * - Text indexing for quote search
 * - postMessage communication with parent chat window
 * - Quote highlighting and scrolling
 */
(function () {
  "use strict";

  // Text index: array of { text, element }
  let textIndex = [];
  let currentHighlight = null;

  /**
   * Normalize text for fuzzy matching:
   * - Lowercase
   * - Collapse whitespace
   * - Unicode NFC normalization
   * - Remove common punctuation variations
   */
  function normalize(text) {
    return text
      .normalize("NFC")
      .toLowerCase()
      .replace(/[\u2018\u2019]/g, "'") // curly single quotes
      .replace(/[\u201C\u201D]/g, '"') // curly double quotes
      .replace(/[\u2013\u2014]/g, "-") // en/em dashes
      .replace(/\s+/g, " ")
      .trim();
  }

  /**
   * Build the text index from the document.
   * Index content from paragraphs, headings, list items, etc.
   */
  function buildIndex() {
    textIndex = [];

    const selectors = [
      "p",
      "h1",
      "h2",
      "h3",
      "h4",
      "h5",
      "h6",
      "li",
      "td",
      "th",
      "figcaption",
      ".ltx_theorem",
      ".ltx_title",
      ".ltx_para",
      "blockquote",
      "span.ltx_text",
    ];

    document.querySelectorAll(selectors.join(", ")).forEach((el) => {
      const text = el.textContent;
      if (text && text.trim().length > 5) {
        textIndex.push({
          text: normalize(text),
          element: el,
        });
      }
    });

    console.log(`[ar5iv-bridge] Built index with ${textIndex.length} entries`);
  }

  /**
   * Find an element containing the given quote.
   * Uses normalized substring matching.
   */
  function findQuote(quote) {
    const normalizedQuote = normalize(quote);

    // First 150 chars for initial search (optimization for long quotes)
    const searchText =
      normalizedQuote.length > 150
        ? normalizedQuote.slice(0, 150)
        : normalizedQuote;

    for (const entry of textIndex) {
      if (entry.text.includes(searchText)) {
        // For long quotes, verify the full match
        if (
          normalizedQuote.length > 150 &&
          !entry.text.includes(normalizedQuote)
        ) {
          continue;
        }
        return entry.element;
      }
    }

    return null;
  }

  /**
   * Clear previous highlight.
   */
  function clearHighlight() {
    if (currentHighlight) {
      currentHighlight.classList.remove("llm-highlight", "llm-highlight-pulse");
      currentHighlight = null;
    }
  }

  /**
   * Highlight an element and scroll it into view.
   */
  function highlightElement(element) {
    clearHighlight();

    element.classList.add("llm-highlight", "llm-highlight-pulse");
    currentHighlight = element;

    // Scroll into view with some margin at top
    element.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });

    // Remove pulse animation after it completes
    setTimeout(() => {
      element.classList.remove("llm-highlight-pulse");
    }, 1000);
  }

  /**
   * Handle messages from parent window.
   */
  function handleMessage(event) {
    const data = event.data;

    if (!data || !data.type) return;

    switch (data.type) {
      case "FIND_AND_HIGHLIGHT": {
        const element = findQuote(data.quote);
        if (element) {
          highlightElement(element);
          window.parent.postMessage(
            {
              type: "HIGHLIGHT_RESULT",
              found: true,
              quote: data.quote,
            },
            "*"
          );
        } else {
          window.parent.postMessage(
            {
              type: "HIGHLIGHT_RESULT",
              found: false,
              quote: data.quote,
            },
            "*"
          );
        }
        break;
      }

      case "CLEAR_HIGHLIGHT": {
        clearHighlight();
        break;
      }

      case "PING": {
        // Respond to health check
        window.parent.postMessage({ type: "PONG" }, "*");
        break;
      }
    }
  }

  /**
   * Initialize the bridge.
   */
  function init() {
    // Build text index
    buildIndex();

    // Listen for messages from parent
    window.addEventListener("message", handleMessage);

    // Signal to parent that we're ready (retry a few times in case parent isn't listening yet)
    function sendReady(attempts) {
      window.parent.postMessage({ type: "READY" }, "*");
      console.log("[ar5iv-bridge] Sent READY signal, attempt", attempts);
      if (attempts < 5) {
        setTimeout(() => sendReady(attempts + 1), 500);
      }
    }
    sendReady(1);

    console.log("[ar5iv-bridge] Initialized and ready");
  }

  // Initialize when DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    // Small delay to ensure parent frame is ready
    setTimeout(init, 100);
  }
})();
