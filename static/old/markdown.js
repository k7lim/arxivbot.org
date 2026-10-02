/**
 * markdown.js
 *
 * Small escape-first markdown renderer for assistant messages.
 *
 * Message text is untrusted (model output, stored chats). Nothing from the
 * input reaches the output as markup: every piece of text goes through
 * escapeHtml(), and the only tags emitted are the fixed ones written in this
 * file. Link targets are limited to http(s) and mailto.
 *
 * Supported: headings, paragraphs, bold/italic, inline code, fenced code
 * blocks, ordered/unordered (nested) lists, blockquotes, horizontal rules,
 * links. Math ($...$, $$...$$, \(...\), \[...\]) is kept as literal text and
 * protected from emphasis parsing. Tables and raw HTML are not supported.
 *
 * A blockquote line of the form > "exact text" (straight or curly quotes)
 * becomes a .quote-link, which quote-highlighter.js turns into a highlight
 * in the paper viewer on click.
 *
 * Loads in the browser (window.renderMarkdown) and in node (module.exports);
 * the renderer itself needs no DOM.
 */
(function (root) {
  "use strict";

  var MAX_DEPTH = 8;
  var MATH_BLOCK_MAX_LINES = 60;

  var RE_BLANK = /^\s*$/;
  var RE_FENCE = /^ {0,3}(`{3,}|~{3,})[^`]*$/;
  var RE_HEADING = /^ {0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$/;
  var RE_HR = /^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$/;
  var RE_BLOCKQUOTE = /^ {0,3}>/;
  var RE_LIST = /^( *)([-*+]|\d{1,9}[.)])( +)(.*)$/;
  var RE_MATH_OPEN = /^\s*(\$\$|\\\[)/;
  var RE_QUOTE_LINE =
    /^\s*([*_]{0,3})(?:(")([^"]+)(")|(“)([^”]+)(”))\1(.*)$/;

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  /**
   * Render inline markdown. Code spans, math and link tags are swapped for
   * NUL-delimited placeholders (NUL is stripped from the input up front, so
   * the input cannot forge one) before the rest is escaped and emphasised.
   */
  function renderInline(text) {
    var stash = [];
    function keep(html) {
      stash.push(html);
      return "\u0000" + (stash.length - 1) + "\u0000";
    }
    function restore(s) {
      return s.replace(/\u0000(\d+)\u0000/g, function (m, idx) {
        return restore(stash[+idx]);
      });
    }

    var s = text;

    // Inline code
    s = s.replace(/(`+)([\s\S]*?[^`])\1(?!`)/g, function (m, ticks, body) {
      return keep("<code>" + escapeHtml(body.trim()) + "</code>");
    });

    // Math stays literal: \$, \(...\), \[...\], $$...$$, $...$
    s = s.replace(
      /\\\$|\\\([\s\S]+?\\\)|\\\[[\s\S]+?\\\]|\$\$[\s\S]+?\$\$|\$(?![\s$])[^$\n]*?[^\s$]\$(?!\d)/g,
      function (m) {
        return keep(escapeHtml(m === "\\$" ? "$" : m));
      }
    );

    // Backslash escapes (\* \_ ...)
    s = s.replace(/\\([\\`*_{}\[\]()#+\-.!>~|])/g, function (m, ch) {
      return keep(escapeHtml(ch));
    });

    s = escapeHtml(s);

    // Links: only http(s) and mailto targets become live; others stay text
    s = s.replace(/\[([^\]\n]+)\]\(([^)\s]+)\)/g, function (m, label, url) {
      if (!/^(https?:\/\/|mailto:)/i.test(url) || url.indexOf("\u0000") !== -1) {
        return m;
      }
      return (
        keep('<a href="' + url + '" target="_blank" rel="noopener noreferrer">') +
        label +
        keep("</a>")
      );
    });

    // Emphasis
    s = s.replace(
      /\*\*\*(?=\S)([^*\n]*?[^\s*])\*\*\*/g,
      "<strong><em>$1</em></strong>"
    );
    s = s.replace(/\*\*(?=\S)([\s\S]*?\S)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/(^|[^\w])__(?=\S)([\s\S]*?\S)__(?!\w)/g, "$1<strong>$2</strong>");
    s = s.replace(/\*(?=[^\s*])([^*\n]*?[^\s*])\*/g, "<em>$1</em>");
    s = s.replace(/(^|[^\w])_(?=[^\s_])([^_\n]*?[^\s_])_(?!\w)/g, "$1<em>$2</em>");

    s = s.replace(/\n/g, "<br>");

    return restore(s);
  }

  function indentOf(line) {
    return /^ */.exec(line)[0].length;
  }

  function isOrdered(marker) {
    return /\d/.test(marker);
  }

  function isBlockStart(line, depth) {
    return (
      RE_FENCE.test(line) ||
      RE_HEADING.test(line) ||
      RE_HR.test(line) ||
      RE_BLOCKQUOTE.test(line) ||
      (depth < MAX_DEPTH && isListStart(line))
    );
  }

  function isListStart(line) {
    var m = RE_LIST.exec(line);
    return !!m && m[1].length <= 3;
  }

  /**
   * A quote line inside a blockquote: "exact text" -> clickable quote link.
   * The quote body is kept verbatim (no inline markdown) so it matches the
   * paper text.
   */
  function renderQuoteLine(line) {
    var m = RE_QUOTE_LINE.exec(line);
    if (!m) return null;
    var open = m[2] || m[5];
    var quote = m[3] || m[6];
    var close = m[4] || m[7];
    var rest = m[8];
    var escaped = escapeHtml(quote);
    return (
      "<p>" +
      escapeHtml(open) +
      '<a class="quote-link" data-quote="' +
      escaped +
      '" href="#">' +
      escaped +
      "</a>" +
      escapeHtml(close) +
      (rest ? renderInline(rest) : "") +
      "</p>"
    );
  }

  function renderBlockquote(lines, depth) {
    var html = "";
    var pending = [];
    function flush() {
      if (pending.length) {
        html += renderBlocks(pending, depth + 1);
        pending = [];
      }
    }
    for (var i = 0; i < lines.length; i++) {
      var quoteHtml = renderQuoteLine(lines[i]);
      if (quoteHtml) {
        flush();
        html += quoteHtml;
      } else {
        pending.push(lines[i]);
      }
    }
    flush();
    return "<blockquote>" + html + "</blockquote>";
  }

  /**
   * Parse a list starting at lines[start]. Returns {html, next}.
   */
  function renderList(lines, start, depth) {
    var n = lines.length;
    var first = RE_LIST.exec(lines[start]);
    var base = first[1].length;
    var ordered = isOrdered(first[2]);
    var items = "";
    var i = start;

    function isSibling(line) {
      if (RE_HR.test(line)) return false;
      var m = RE_LIST.exec(line);
      return (
        !!m &&
        m[1].length >= base &&
        m[1].length <= base + 1 &&
        isOrdered(m[2]) === ordered
      );
    }

    while (i < n && isSibling(lines[i])) {
      var m = RE_LIST.exec(lines[i]);
      var contentIndent = m[1].length + m[2].length + Math.min(m[3].length, 4);
      var minIndent = m[1].length + 2;
      var body = [m[4]];
      var tight = true;
      i++;

      while (i < n) {
        var line = lines[i];
        if (RE_BLANK.test(line)) {
          var j = i + 1;
          while (j < n && RE_BLANK.test(lines[j])) j++;
          if (j < n && indentOf(lines[j]) >= minIndent) {
            body.push("");
            tight = false;
            i = j;
            continue;
          }
          break;
        }
        var ind = indentOf(line);
        if (ind < minIndent) break;
        body.push(line.slice(Math.min(ind, contentIndent)));
        i++;
      }

      var inner = renderBlocks(body, depth + 1);
      if (tight && inner.indexOf("<p>") === 0) {
        inner = inner.slice(3).replace("</p>", "");
      }
      items += "<li>" + inner + "</li>";

      // Blank lines between items of the same list do not end it
      var k = i;
      while (k < n && RE_BLANK.test(lines[k])) k++;
      if (k > i) {
        if (k < n && isSibling(lines[k])) {
          i = k;
        } else {
          break;
        }
      }
    }

    var open = "<ul>";
    if (ordered) {
      var startNum = parseInt(first[2], 10);
      open = startNum === 1 ? "<ol>" : '<ol start="' + startNum + '">';
    }
    return { html: open + items + (ordered ? "</ol>" : "</ul>"), next: i };
  }

  function renderBlocks(lines, depth) {
    var out = [];
    var para = [];
    var n = lines.length;
    var i = 0;
    var m;

    function flush() {
      if (para.length) {
        out.push("<p>" + renderInline(para.join("\n")) + "</p>");
        para = [];
      }
    }

    while (i < n) {
      var line = lines[i];

      if (RE_BLANK.test(line)) {
        flush();
        i++;
        continue;
      }

      // Fenced code block
      m = RE_FENCE.exec(line);
      if (m) {
        flush();
        var closing = new RegExp(
          "^ {0,3}" + (m[1].charAt(0) === "`" ? "`" : "~") + "{" + m[1].length + ",}\\s*$"
        );
        var code = [];
        i++;
        while (i < n && !closing.test(lines[i])) code.push(lines[i++]);
        i++;
        out.push("<pre><code>" + escapeHtml(code.join("\n")) + "</code></pre>");
        continue;
      }

      // Multi-line display math: kept verbatim
      m = RE_MATH_OPEN.exec(line);
      if (m) {
        var closer = m[1] === "$$" ? "$$" : "\\]";
        if (line.slice(m[0].length).indexOf(closer) === -1) {
          var end = -1;
          var limit = Math.min(n, i + MATH_BLOCK_MAX_LINES);
          for (var j = i + 1; j < limit; j++) {
            if (lines[j].indexOf(closer) !== -1) {
              end = j;
              break;
            }
          }
          if (end !== -1) {
            flush();
            out.push(
              '<div class="md-math">' +
                escapeHtml(lines.slice(i, end + 1).join("\n")) +
                "</div>"
            );
            i = end + 1;
            continue;
          }
        }
      }

      // Heading. The page already has an h1 (paper title), so # maps to h3.
      m = RE_HEADING.exec(line);
      if (m) {
        flush();
        var level = Math.min(m[1].length + 2, 6);
        out.push("<h" + level + ">" + renderInline(m[2]) + "</h" + level + ">");
        i++;
        continue;
      }

      if (RE_HR.test(line)) {
        flush();
        out.push("<hr>");
        i++;
        continue;
      }

      if (RE_BLOCKQUOTE.test(line) && depth < MAX_DEPTH) {
        flush();
        var quoted = [];
        while (i < n && RE_BLOCKQUOTE.test(lines[i])) {
          quoted.push(lines[i].replace(/^ {0,3}> ?/, ""));
          i++;
        }
        out.push(renderBlockquote(quoted, depth));
        continue;
      }

      if (depth < MAX_DEPTH && isListStart(line)) {
        flush();
        var list = renderList(lines, i, depth);
        out.push(list.html);
        i = list.next;
        continue;
      }

      para.push(line.trim());
      i++;
    }

    flush();
    return out.join("");
  }

  /**
   * Convert markdown text to a safe HTML string.
   */
  function renderMarkdown(text) {
    var lines = String(text == null ? "" : text)
      .replace(/\u0000/g, "")
      .replace(/\r\n?/g, "\n")
      .split("\n")
      .map(function (line) {
        return line.replace(/^\t+/, function (tabs) {
          return new Array(tabs.length + 1).join("    ");
        });
      });
    return renderBlocks(lines, 0);
  }

  var api = { render: renderMarkdown, escapeHtml: escapeHtml };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.ArxivbotMarkdown = api;
    root.renderMarkdown = renderMarkdown;
  }
})(typeof window !== "undefined" ? window : this);
