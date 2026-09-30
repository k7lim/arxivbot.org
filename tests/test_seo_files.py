"""robots.txt, sitemap.xml and llms.txt."""

import xml.etree.ElementTree as ET

from arxivbot import config

SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def test_robots_txt(client):
    resp = client.get("/robots.txt")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    lines = resp.text.splitlines()
    assert "User-agent: *" in lines
    assert "Disallow: /api/" in lines
    assert "Disallow: /ar5iv/" in lines
    assert "Sitemap: https://arxivbot.org/sitemap.xml" in lines


def test_sitemap_xml_lists_only_the_home_page(client):
    resp = client.get("/sitemap.xml")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/xml")
    root = ET.fromstring(resp.content)
    assert root.tag == f"{SITEMAP_NS}urlset"
    locs = [el.text for el in root.iter(f"{SITEMAP_NS}loc")]
    assert locs == ["https://arxivbot.org/"]


def test_llms_txt(client):
    resp = client.get("/llms.txt")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert resp.text.startswith("# ArxivBot\n")
    assert 'Add "bot" after "arxiv" in a paper URL.' in resp.text
    for form in ("/abs/", "/pdf/", "/html/", "/chat/"):
        assert form in resp.text


def test_site_url_setting_is_used(client, monkeypatch):
    monkeypatch.setattr(config.get_settings(), "site_url", "https://example.test/")

    assert "Sitemap: https://example.test/sitemap.xml" in client.get("/robots.txt").text
    root = ET.fromstring(client.get("/sitemap.xml").content)
    assert [el.text for el in root.iter(f"{SITEMAP_NS}loc")] == ["https://example.test/"]


def test_site_url_env_var_overrides_default(monkeypatch):
    monkeypatch.setenv("SITE_URL", "https://staging.example.test")

    assert config.Settings(_env_file=None).site_url == "https://staging.example.test"


def test_seo_files_are_served_on_www_via_redirect_only(client):
    resp = client.get(
        "/robots.txt", headers={"Host": "www.arxivbot.org"}, follow_redirects=False
    )

    assert resp.status_code == 308
    assert resp.headers["location"] == "https://arxivbot.org/robots.txt"
