/**
 * quote-highlighter.js
 *
 * Handles:
 * - Extracting quotes from LLM responses
 * - Converting quotes to clickable links
 * - Communicating with ar5iv iframe for highlighting
 */
(function () {
  "use strict";

  let iframeReady = false;
  let pendingHighlight = null;

  /**
   * Extract quotes from text.
   * Matches: > "..." (straight or curly quotes)
   */
  function extractQuotes(text) {
    const quotes = [];

    // Match > "..." with straight quotes
    const regex1 = /^>\s*"([^"]+)"/gm;
    // Match > "..." with curly quotes
    const regex2 = /^>\s*"([^"]+)"/gm;

    let match;
    while ((match = regex1.exec(text)) !== null) {
      quotes.push(match[1]);
    }
    while ((match = regex2.exec(text)) !== null) {
      quotes.push(match[1]);
    }

    // Dedupe while preserving order
    return [...new Set(quotes)];
  }

  /**
   * Escape special regex characters in a string.
   */
  function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  /**
   * Escape HTML entities.
   */
  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Convert quotes in a message element to clickable links.
   */
  function linkifyQuotes(messageEl) {
    const contentEl = messageEl.querySelector(".message-content");
    if (!contentEl) return;

    const text = contentEl.textContent;
    const quotes = extractQuotes(text);

    if (quotes.length === 0) return;

    // Get current HTML and replace quotes with links
    let html = contentEl.innerHTML;

    quotes.forEach((quote, index) => {
      // Match the quote in both straight and curly quote formats
      const escapedQuote = escapeHtml(quote);

      // Pattern for > "quote" format (with straight quotes in HTML)
      const pattern1 = new RegExp(
        `(&gt;\\s*)"(${escapeRegex(escapedQuote)})"`,
        "g"
      );

      // Pattern for > "quote" format (with curly quotes)
      const pattern2 = new RegExp(
        `(&gt;\\s*)"(${escapeRegex(escapedQuote)})"`,
        "g"
      );

      const quoteAttr = escapeHtml(quote).replace(/"/g, "&quot;");
      // Use a replacer function so "$" in the quote (e.g. LaTeX "$2^n$") is
      // inserted literally instead of being treated as a replacement pattern.
      const replacement = (match, prefix, body) =>
        `${prefix}"<a class="quote-link" data-quote="${quoteAttr}" href="#">${body}</a>"`;

      html = html.replace(pattern1, replacement);
      html = html.replace(pattern2, replacement);
    });

    contentEl.innerHTML = html;
  }

  /**
   * Handle click on a quote link.
   */
  function handleQuoteClick(event) {
    const link = event.target.closest(".quote-link");
    if (!link) return;

    event.preventDefault();

    const quote = link.dataset.quote;
    if (!quote) return;

    // Get the ar5iv iframe
    const iframe = document.getElementById("ar5iv-iframe");
    if (!iframe || !iframe.contentWindow) {
      showToast("Paper viewer not available");
      return;
    }

    // Always try to send - the bridge will respond if ready
    // This handles cases where we missed the READY signal
    iframe.contentWindow.postMessage(
      {
        type: "FIND_AND_HIGHLIGHT",
        quote: quote,
      },
      "*"
    );

    // If iframe not confirmed ready, also store as pending and show feedback
    if (!iframeReady) {
      pendingHighlight = quote;
      showToast("Searching in paper...");
    }
  }

  /**
   * Show a brief toast notification.
   */
  function showToast(message) {
    // Remove existing toast
    const existing = document.querySelector(".quote-toast");
    if (existing) existing.remove();

    const toast = document.createElement("div");
    toast.className = "quote-toast";
    toast.textContent = message;
    document.body.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => {
      toast.classList.add("show");
    });

    // Remove after delay
    setTimeout(() => {
      toast.classList.remove("show");
      setTimeout(() => toast.remove(), 300);
    }, 2000);
  }

  /**
   * Handle messages from the ar5iv iframe.
   */
  function handleIframeMessage(event) {
    const data = event.data;
    if (!data || !data.type) return;

    switch (data.type) {
      case "READY":
        iframeReady = true;
        console.log("[quote-highlighter] ar5iv iframe ready");

        // Process any pending highlight
        if (pendingHighlight) {
          const iframe = document.getElementById("ar5iv-iframe");
          if (iframe && iframe.contentWindow) {
            iframe.contentWindow.postMessage(
              {
                type: "FIND_AND_HIGHLIGHT",
                quote: pendingHighlight,
              },
              "*"
            );
          }
          pendingHighlight = null;
        }
        break;

      case "HIGHLIGHT_RESULT":
        if (!data.found) {
          showToast("Quote not found in viewer");
        }
        break;
    }
  }

  /**
   * Process a new assistant message after streaming completes.
   */
  function processAssistantMessage(messageEl) {
    if (!messageEl.classList.contains("assistant")) return;
    if (messageEl.dataset.quotesProcessed) return;

    linkifyQuotes(messageEl);
    messageEl.dataset.quotesProcessed = "true";
  }

  /**
   * Initialize the quote highlighter.
   */
  function init() {
    // Listen for iframe messages
    window.addEventListener("message", handleIframeMessage);

    // Use event delegation for quote link clicks
    document.addEventListener("click", handleQuoteClick);

    // Expose function for processing new messages
    window.processQuotes = processAssistantMessage;

    // Process any existing assistant messages on page load
    document.querySelectorAll(".message.assistant").forEach((msg) => {
      processAssistantMessage(msg);
    });

    console.log("[quote-highlighter] Initialized");
  }

  // Initialize when DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
