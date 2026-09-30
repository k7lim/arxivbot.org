"""LLM Router: primary model plus free-tier and paid fallbacks."""

from litellm import Router

from arxivbot import config
from arxivbot.services import paper_service


def make_settings(monkeypatch, **kwargs):
    kwargs.setdefault("gemini_api_key_paid", None)  # ignore any key in the environment
    settings = config.Settings(_env_file=None, gemini_api_key="free-key", **kwargs)
    monkeypatch.setattr(config, "_settings", settings)
    return settings


def models(router):
    return [(m["model_name"], m["litellm_params"]["model"]) for m in router.model_list]


def test_default_chain_order(monkeypatch):
    make_settings(monkeypatch)
    router = paper_service._create_router()
    assert models(router) == [
        ("gemini-primary", "gemini/gemini-3.8-flash"),
        ("gemini-free-1", "gemini/gemini-3.7-flash"),
        ("gemini-free-2", "gemini/gemini-3.6-flash"),
        ("gemini-free-3", "gemini/gemini-3.5-flash"),
        ("gemini-free-4", "gemini/gemini-3-flash-preview"),
        ("gemini-free-5", "gemini/gemini-3.5-flash-lite"),
        ("gemini-free-6", "gemini/gemini-3.1-flash-lite"),
    ]
    assert router.fallbacks == [
        {"gemini-primary": [f"gemini-free-{i}" for i in range(1, 7)]}
    ]


def test_paid_key_is_last_fallback(monkeypatch):
    make_settings(monkeypatch, gemini_api_key_paid="paid-key")
    router = paper_service._create_router()
    assert router.fallbacks[0]["gemini-primary"][-1] == "gemini-fallback"
    paid = router.model_list[-1]["litellm_params"]
    assert paid["api_key"] == "paid-key"
    assert paid["model"] == "gemini/gemini-2.5-flash-lite"


def test_env_overrides_and_empty_chain(monkeypatch):
    make_settings(
        monkeypatch,
        llm_model="gemini/gemini-3.5-flash",
        llm_free_fallback_models=" gemini/gemini-3.5-flash , ,gemini/gemini-3.1-flash-lite",
    )
    # Blanks and the primary itself are dropped
    assert models(paper_service._create_router()) == [
        ("gemini-primary", "gemini/gemini-3.5-flash"),
        ("gemini-free-1", "gemini/gemini-3.1-flash-lite"),
    ]

    make_settings(monkeypatch, llm_free_fallback_models="")
    router = paper_service._create_router()
    assert len(router.model_list) == 1
    assert not router.fallbacks


def test_flash_lite_gets_higher_rpm(monkeypatch):
    make_settings(monkeypatch)
    rpm = {
        m["litellm_params"]["model"]: m["litellm_params"]["rpm"]
        for m in paper_service._create_router().model_list
    }
    assert rpm["gemini/gemini-3.8-flash"] == 5
    assert rpm["gemini/gemini-3.5-flash-lite"] == 15


def test_rate_limited_primary_falls_back(monkeypatch):
    """A rate-limited primary is answered by the next model in the chain."""
    import asyncio

    router = Router(
        model_list=[
            {
                "model_name": "gemini-primary",
                "litellm_params": {
                    "model": "gemini/gemini-3.8-flash",
                    "api_key": "k",
                    "mock_response": "litellm.RateLimitError",
                },
            },
            {
                "model_name": "gemini-free-1",
                "litellm_params": {
                    "model": "gemini/gemini-3.7-flash",
                    "api_key": "k",
                    "mock_response": "answer from fallback",
                },
            },
        ],
        fallbacks=[{"gemini-primary": ["gemini-free-1"]}],
        num_retries=0,
    )
    monkeypatch.setattr(paper_service, "_router", router)
    monkeypatch.setattr(paper_service, "LLM_NUM_RETRIES", 0)

    async def fetch_paper_content(paper_id):
        return "paper text"

    monkeypatch.setattr(paper_service, "fetch_paper_content", fetch_paper_content)

    async def run():
        result = await paper_service.query_paper("1706.03762", "hi")
        chunks = [c async for c in paper_service.query_paper_stream("1706.03762", "hi")]
        return result["answer"], "".join(chunks)

    answer, streamed = asyncio.run(run())
    assert answer == "answer from fallback"
    assert streamed == "answer from fallback"
