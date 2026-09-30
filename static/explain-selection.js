/**
 * explain-selection.js
 *
 * Inline action: select a phrase in an answer or in the paper and an
 * "Explain" bar appears above the chat box. Pressing it asks about exactly
 * that phrase. The page supplies what "ask" means:
 *
 *   window.initExplainSelection({ bar, label, button, dismiss, scope, iframe, ask })
 *
 * scope is the element whose selections count (the message list); iframe is
 * the same-origin paper viewer, watched once it has loaded.
 */
(function () {
  "use strict";

  var MIN_CHARS = 2;
  var MAX_CHARS = 300;

  function initExplainSelection(opts) {
    var current = "";
    var hideTimer = null;
    var pressed = false;

    function show(text) {
      clearTimeout(hideTimer);
      current = text;
      var shown = text.length > 60 ? text.slice(0, 57) + "..." : text;
      opts.label.textContent = "“" + shown + "”";
      opts.bar.hidden = false;
    }

    function hide() {
      current = "";
      opts.bar.hidden = true;
    }

    function readSelection(doc, requireScope) {
      var sel = doc.getSelection && doc.getSelection();
      if (!sel || sel.isCollapsed || !sel.rangeCount) return "";
      if (requireScope) {
        var node = sel.anchorNode;
        if (!node || !opts.scope.contains(node)) return "";
      }
      return sel.toString().replace(/\s+/g, " ").trim();
    }

    function onChange(doc, requireScope) {
      var text = readSelection(doc, requireScope);
      if (text.length >= MIN_CHARS) {
        // A long selection (a whole paragraph) is asked about by its opening words
        if (text.length > MAX_CHARS) {
          text = text.slice(0, MAX_CHARS).replace(/\s+\S*$/, "") + "...";
        }
        show(text);
      } else if (!text) {
        // Tapping the bar can clear the selection first; give the tap time to land.
        clearTimeout(hideTimer);
        hideTimer = setTimeout(function () {
          if (!pressed) hide();
        }, 400);
      }
    }

    document.addEventListener("selectionchange", function () {
      onChange(document, true);
    });

    function watchIframe() {
      try {
        var doc = opts.iframe.contentDocument;
        if (doc) {
          doc.addEventListener("selectionchange", function () {
            onChange(doc, false);
          });
        }
      } catch (e) {
        // Cross-origin or error page: no inline action in the paper
      }
    }
    if (opts.iframe) opts.iframe.addEventListener("load", watchIframe);

    opts.bar.addEventListener("pointerdown", function (e) {
      pressed = true;
      // Keep the chat selection alive while the button is pressed
      if (e.target.closest("button")) e.preventDefault();
    });
    opts.bar.addEventListener("pointerup", function () {
      setTimeout(function () {
        pressed = false;
      }, 0);
    });

    opts.button.addEventListener("click", function () {
      if (!current) return;
      var text = current;
      hide();
      opts.ask(text);
    });
    opts.dismiss.addEventListener("click", hide);

    return { hide: hide };
  }

  window.initExplainSelection = initExplainSelection;
})();
