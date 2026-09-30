/**
 * followups.js
 *
 * Splits the "Ask next:" block the model ends each answer with (see
 * paper_service._build_messages) off the answer text, so the questions can be
 * shown as buttons instead of a markdown list.
 *
 * splitFollowUps(text) -> { body, questions }
 *   body: the answer without the block (trailing whitespace trimmed)
 *   questions: the bullet texts after the heading, in order (may be empty)
 *
 * The heading is cut from the body as soon as it appears, so a half-streamed
 * answer never flashes the raw list. Loads in the browser
 * (window.splitFollowUps) and in node (module.exports).
 */
(function (root) {
  "use strict";

  var HEADING = /^\s*(?:\*\*|__)?\s*ask next\s*:?\s*(?:\*\*|__)?\s*:?\s*$/i;
  var BULLET = /^\s*(?:[-*+]|\d+[.)])\s+(.+?)\s*$/;

  function splitFollowUps(text) {
    var lines = String(text || "").split("\n");
    var at = -1;
    for (var i = lines.length - 1; i >= 0; i--) {
      if (HEADING.test(lines[i])) {
        at = i;
        break;
      }
    }
    if (at < 0) {
      return { body: String(text || ""), questions: [] };
    }
    var questions = [];
    for (var j = at + 1; j < lines.length; j++) {
      var m = BULLET.exec(lines[j]);
      if (m) questions.push(m[1].replace(/^\*\*(.*)\*\*$/, "$1"));
    }
    return {
      body: lines.slice(0, at).join("\n").replace(/\s+$/, ""),
      questions: questions.slice(0, 3),
    };
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { splitFollowUps: splitFollowUps };
  } else {
    root.splitFollowUps = splitFollowUps;
  }
})(typeof window !== "undefined" ? window : this);
