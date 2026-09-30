"""www.arxivbot.org redirects to the apex domain; every other host passes through."""

import pytest

from arxivbot.services import paper_service

PATH = "/abs/1706.03762?x=1"
APEX_URL = "https://arxivbot.org/abs/1706.03762?x=1"


@pytest.fixture
def metadata_calls(monkeypatch):
    """Stub the arXiv metadata fetch and record whether the /abs handler ran."""
    calls = []

    async def fetch_paper_metadata(paper_id):
        calls.append(paper_id)
        return {"title": "Attention Is All You Need", "authors": [], "abstract": ""}

    monkeypatch.setattr(paper_service, "fetch_paper_metadata", fetch_paper_metadata)
    return calls


def test_www_get_redirects_to_apex_without_running_handler(client, metadata_calls):
    resp = client.get(PATH, headers={"Host": "www.arxivbot.org"}, follow_redirects=False)

    assert resp.status_code == 308
    assert resp.headers["location"] == APEX_URL
    assert metadata_calls == []


@pytest.mark.parametrize("host", ["WWW.ArxivBot.org", "www.arxivbot.org:443"])
def test_www_host_match_ignores_case_and_port(client, metadata_calls, host):
    resp = client.get(PATH, headers={"Host": host}, follow_redirects=False)

    assert resp.status_code == 308
    assert resp.headers["location"] == APEX_URL
    assert metadata_calls == []


def test_www_redirect_without_query_has_no_question_mark(client):
    resp = client.get(
        "/abs/1706.03762", headers={"Host": "www.arxivbot.org"}, follow_redirects=False
    )

    assert resp.status_code == 308
    assert resp.headers["location"] == "https://arxivbot.org/abs/1706.03762"


def test_www_post_redirects_with_308(client):
    resp = client.post(
        "/api/anything?x=1",
        headers={"Host": "www.arxivbot.org"},
        json={"question": "hi"},
        follow_redirects=False,
    )

    assert resp.status_code == 308
    assert resp.headers["location"] == "https://arxivbot.org/api/anything?x=1"


@pytest.mark.parametrize("host", ["arxivbot.org", "arxivbot.fly.dev"])
def test_other_hosts_are_not_redirected(client, metadata_calls, host):
    resp = client.get(PATH, headers={"Host": host}, follow_redirects=False)

    assert resp.status_code == 200
    assert "location" not in resp.headers
    assert metadata_calls == ["1706.03762"]


@pytest.mark.parametrize(
    "host",
    ["arxivbot.org", "arxivbot.fly.dev", "testserver", "localhost:8000", "10.0.0.1:8000"],
)
def test_health_ok_for_non_www_hosts(client, host):
    resp = client.get("/health", headers={"Host": host}, follow_redirects=False)

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "connected"}
