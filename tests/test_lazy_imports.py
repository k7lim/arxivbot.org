"""Cold boot must not import the heavy LLM and PDF libraries."""

import subprocess
import sys


def test_importing_app_does_not_import_litellm_or_pypdf():
    code = (
        "import sys\n"
        "import arxivbot.main\n"
        "loaded = [m for m in ('litellm', 'pypdf') if m in sys.modules]\n"
        "assert not loaded, loaded\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
