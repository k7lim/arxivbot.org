"""static/markdown.js: the client-side renderer for assistant messages.

The renderer is a pure text -> HTML function, so it is exercised with node.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from arxivbot.services import paper_service

STATIC = Path(__file__).resolve().parent.parent / "static"
MARKDOWN_JS = STATIC / "markdown.js"

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")

_SCRIPT = """
const md = require(process.argv[1]);
const inputs = JSON.parse(require('fs').readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(inputs.map((t) => md.render(t))));
"""


def render_all(texts):
    result = subprocess.run(
        [NODE, "-e", _SCRIPT, str(MARKDOWN_JS)],
        input=json.dumps(texts),
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return json.loads(result.stdout)


def render(text):
    return render_all([text])[0]


@needs_node
def test_headings_are_demoted_below_the_page_h1():
    html = render("# Title\n\n### Overview\nBody text")
    assert "<h3>Title</h3>" in html
    assert "<h5>Overview</h5>" in html
    assert "<p>Body text</p>" in html
    assert "<h1" not in html and "<h2" not in html
    assert "#" not in html


@needs_node
def test_bold_italic_and_inline_code():
    html = render("**Structured questions** and *emphasis* and `x_1 * y`")
    assert "<strong>Structured questions</strong>" in html
    assert "<em>emphasis</em>" in html
    assert "<code>x_1 * y</code>" in html


@needs_node
def test_lists():
    html = render("Points:\n- one\n- **two**\n  - nested\n\n1. first\n2. second")
    assert "<p>Points:</p>" in html
    assert (
        "<ul><li>one</li><li><strong>two</strong><ul><li>nested</li></ul></li></ul>"
        in html
    )
    assert "<ol><li>first</li><li>second</li></ol>" in html


@needs_node
def test_code_block_is_verbatim_and_escaped():
    html = render("```python\nif a < b and c:\n    **not bold**\n```\nafter")
    assert "<pre><code>if a &lt; b and c:\n    **not bold**</code></pre>" in html
    assert "<p>after</p>" in html


@needs_node
def test_paragraphs_and_line_breaks():
    assert render("one\ntwo\n\nthree") == "<p>one<br>two</p><p>three</p>"


@needs_node
def test_plain_blockquote():
    assert render("> just a remark") == "<blockquote><p>just a remark</p></blockquote>"


@needs_node
def test_raw_html_is_escaped():
    payloads = [
        "<script>alert(1)</script>",
        '<img src=x onerror="alert(1)">',
        "**<img src=x onerror=alert(1)>**",
        "# <script>alert(1)</script>",
        "- <iframe src=javascript:alert(1)>",
        '> "<img src=x onerror=alert(1)>"',
        "`<script>`",
        "```\n</code></pre><script>alert(1)</script>\n```",
        '[a](https://e.com/"onmouseover="alert(1))',
        "[<img src=x onerror=alert(1)>](https://e.com)",
        "$<script>alert(1)</script>$",
        "\u00001\u0000 <b>x</b>",
    ]
    for html in render_all(payloads):
        assert "<script" not in html
        assert "<img" not in html
        assert "<iframe" not in html
        assert "<b>" not in html
        assert 'onmouseover="' not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in render(payloads[0])
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in render(payloads[1])


@needs_node
def test_only_safe_link_schemes_become_links():
    outputs = render_all(
        [
            "[x](javascript:alert(1))",
            "[x](JaVaScRiPt:alert(1))",
            "[x](data:text/html,hi)",
            "[x](vbscript:msgbox)",
            "[paper](https://arxiv.org/abs/1706.03762)",
        ]
    )
    for html in outputs[:4]:
        assert "<a" not in html
        assert "href" not in html
    assert (
        '<a href="https://arxiv.org/abs/1706.03762" target="_blank" '
        'rel="noopener noreferrer">paper</a>' in outputs[4]
    )


@needs_node
def test_quote_lines_become_quote_links():
    text = (
        "As stated in the paper:\n"
        '> "our method achieves 95% accuracy on the benchmark"\n'
        "This is an improvement."
    )
    html = render(text)
    assert "<p>As stated in the paper:</p>" in html
    assert (
        '<blockquote><p>&quot;<a class="quote-link" '
        'data-quote="our method achieves 95% accuracy on the benchmark" href="#">'
        "our method achieves 95% accuracy on the benchmark</a>&quot;</p></blockquote>"
    ) in html
    assert "<p>This is an improvement.</p>" in html


@needs_node
def test_curly_quote_lines_become_quote_links():
    html = render("> \u201cattention is all you need\u201d")
    assert (
        '\u201c<a class="quote-link" data-quote="attention is all you need" href="#">'
        "attention is all you need</a>\u201d"
    ) in html


@needs_node
def test_quote_text_is_kept_verbatim():
    html = render('> "loss $L_i$ & a *b* <c> of_the_model"')
    assert 'data-quote="loss $L_i$ &amp; a *b* &lt;c&gt; of_the_model"' in html
    assert "<em>" not in html


@needs_node
def test_math_is_left_as_literal_text():
    html = render("We have $a_b$ and $x_i + y_i$ with $n = 1922$ samples.")
    assert html == "<p>We have $a_b$ and $x_i + y_i$ with $n = 1922$ samples.</p>"

    html = render("Inline \\(a_i * b_i * c\\) and $$E_x = m_x*c*2$$ and $\\{a\\}_b*c*$")
    assert "\\(a_i * b_i * c\\)" in html
    assert "$$E_x = m_x*c*2$$" in html
    assert "$\\{a\\}_b*c*$" in html
    assert "<em>" not in html

    html = render("$$\n- a_i *b* c_i\n# x\n$$\nafter")
    assert '<div class="md-math">$$\n- a_i *b* c_i\n# x\n$$</div>' in html
    assert "<li>" not in html and "<em>" not in html
    assert "<p>after</p>" in html


@needs_node
def test_underscores_in_words_and_prices_are_not_mangled():
    html = render("Use snake_case_name for it. It costs $5 and $10 *really*.")
    assert "snake_case_name" in html
    assert "$5 and $10" in html
    assert "<em>really</em>" in html


@needs_node
def test_pathological_input_does_not_hang_or_throw():
    outputs = render_all(
        [">" * 5000 + " x", "- " * 3000 + "x", "*" * 5000, "`" * 5000, "$" * 5000, ""]
    )
    assert outputs[-1] == ""
    assert all("<script" not in html for html in outputs)


def test_quote_highlighter_uses_the_renderer():
    source = (STATIC / "quote-highlighter.js").read_text()
    assert "window.renderMarkdown(contentEl.textContent)" in source


def test_chat_page_loads_markdown_script(client, monkeypatch):
    async def fetch_paper_metadata(paper_id):
        return {"title": "Attention Is All You Need", "authors": [], "abstract": ""}

    monkeypatch.setattr(paper_service, "fetch_paper_metadata", fetch_paper_metadata)
    resp = client.get("/abs/1706.03762")
    assert resp.status_code == 200
    assert re.search(r'<script src="/static/markdown.js\?v=[0-9a-f]+"></script>', resp.text)
    # The renderer must be defined before quote-highlighter.js runs
    assert resp.text.index("/static/markdown.js") < resp.text.index(
        "/static/quote-highlighter.js"
    )
    served = client.get("/static/markdown.js")
    assert served.status_code == 200
    assert "renderMarkdown" in served.text
