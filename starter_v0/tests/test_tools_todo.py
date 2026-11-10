"""TODO(student): Tool Unit Test Challenge.

Each test below is a stub. Replace `pytest.skip(...)` with a real test.
Patterns to copy are in test_tools_examples.py. Fixtures are in conftest.py.

Rules:
- Offline only: mock HTTP with `fake_http`, set fake keys with `monkeypatch.setenv`.
- One behaviour per test. Name the test after the behaviour, not the function.
- Done = `pytest tests/ -v` shows 0 skipped, 0 failed.
"""
from __future__ import annotations

import pytest

from conftest import FakeResponse  # noqa: F401  (you will need it)
from tools import TOOL_FUNCTIONS  # noqa: F401

TODO = "TODO(student): implement this test"


# ---------------- clarify ----------------

def test_clarify_choice_returns_options_and_awaits_user() -> None:
    # Call clarify with response_type="choice" and 2 options.
    # Assert: options are returned unchanged, awaiting_user is True.
    result = TOOL_FUNCTIONS["clarify"](
        question="Chọn nguồn nào?",
        response_type="choice",
        options=["Web", "Twitter"],
    )
    assert result["options"] == ["Web", "Twitter"]
    assert result["awaiting_user"] is True


# ---------------- format ----------------

def test_format_sections_groups_items_by_section() -> None:
    # Items with section "A", "B", "A" -> markdown has exactly one "## A" and one "## B".
    result = TOOL_FUNCTIONS["format"](
        items=[
            {"section": "A", "summary": "one"},
            {"section": "B", "summary": "two"},
            {"section": "A", "summary": "three"},
        ],
        template="sections",
    )
    assert result["markdown"].count("## A") == 1
    assert result["markdown"].count("## B") == 1


def test_format_thread_numbers_items() -> None:
    # template="thread" -> lines start with "1/", "2/", ...
    result = TOOL_FUNCTIONS["format"](
        items=[{"summary": "one"}, {"summary": "two"}],
        template="thread",
    )
    lines = result["markdown"].splitlines()
    assert lines[0].startswith("1/")
    assert lines[2].startswith("2/")


def test_format_empty_items_does_not_crash() -> None:
    # items=None and items=[] -> item_count == 0, no exception.
    for items in (None, []):
        result = TOOL_FUNCTIONS["format"](items=items, template="brief")
        assert result["item_count"] == 0
        assert isinstance(result["markdown"], str)


# ---------------- send (guardrail) ----------------

def test_send_confirmed_posts_to_telegram(monkeypatch, fake_http) -> None:
    # Set TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID, mock HTTP.
    # Assert: exactly one POST, URL contains the token, json has chat_id + text, status == "sent".
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "test-chat")
    calls = fake_http(FakeResponse({"ok": True}))
    result = TOOL_FUNCTIONS["send"](text="Bản tin", confirmed=True)
    assert len(calls) == 1
    assert calls[0]["method"] == "POST"
    assert "test-token" in calls[0]["url"]
    assert calls[0]["json"]["chat_id"] == "test-chat"
    assert calls[0]["json"]["text"] == "Bản tin"
    assert result["status"] == "sent"


def test_send_confirmed_without_env_returns_error_and_no_request(fake_http) -> None:
    calls = fake_http(FakeResponse({"ok": True}))
    result = TOOL_FUNCTIONS["send"](text="Bản tin", confirmed=True)
    assert result["error"] == "RuntimeError"
    assert calls == []


# ---------------- lookup ----------------

def test_lookup_without_timeframe_omits_time_range(monkeypatch, fake_http) -> None:
    # timeframe=None -> request body has no "time_range" key.
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    calls = fake_http(FakeResponse({"results": []}))
    result = TOOL_FUNCTIONS["lookup"](
        query="AI",
        topic="news",
        timeframe=None,
    )
    assert "time_range" not in calls[0]["json"]
    assert result["items"] == []


# ---------------- fetch ----------------

def test_fetch_maps_firecrawl_response(monkeypatch, fake_http) -> None:
    # Mock {"data": {"markdown": "...", "metadata": {"title": "T", "sourceURL": "https://..."}}}
    # Assert title/url/source/summary in result["items"][0].
    monkeypatch.setenv("FIRECRAWL_API_KEY", "test-key")
    calls = fake_http(FakeResponse({
        "data": {
            "markdown": "Article body",
            "metadata": {
                "title": "T",
                "sourceURL": "https://example.com/article",
            },
        }
    }))
    result = TOOL_FUNCTIONS["fetch"]("https://example.com/article")
    item = result["items"][0]
    assert calls[0]["json"]["url"] == "https://example.com/article"
    assert item["title"] == "T"
    assert item["url"] == "https://example.com/article"
    assert item["source"] == "example.com"
    assert item["summary"] == "Article body"


def test_fetch_truncates_markdown_to_4000_chars(monkeypatch, fake_http) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "test-key")
    fake_http(FakeResponse({
        "data": {"markdown": "x" * 5000, "metadata": {}}
    }))
    result = TOOL_FUNCTIONS["fetch"]("https://example.com/article")
    assert len(result["items"][0]["summary"]) == 4000


# ---------------- timeline / social_search ----------------

def test_timeline_respects_limit_and_skips_items_without_id(monkeypatch, fake_http) -> None:
    # Mock {"timeline": [...]} with 1 item missing tweet_id and 6 valid items, limit=3.
    # Assert 3 items, and each url looks like https://x.com/<handle>/status/<id>.
    monkeypatch.setenv("RAPIDAPI_KEY", "test-key")
    monkeypatch.setenv("RAPIDAPI_TWITTER_HOST", "twitter.test")
    timeline = [
        {"text": "missing id"},
        *[
            {
                "tweet_id": str(index),
                "screen_name": "sama",
                "text": f"Tweet {index}",
            }
            for index in range(6)
        ],
    ]
    calls = fake_http(FakeResponse({"timeline": timeline}))
    result = TOOL_FUNCTIONS["timeline"]("sama", limit=3)
    assert calls[0]["url"] == "https://twitter.test/timeline.php"
    assert len(result["items"]) == 3
    assert all(
        item["url"].startswith("https://x.com/sama/status/")
        for item in result["items"]
    )


def test_social_search_passes_search_type(monkeypatch, fake_http) -> None:
    # Assert the request params carry the query and search_type ("Top" / "Latest").
    monkeypatch.setenv("RAPIDAPI_KEY", "test-key")
    monkeypatch.setenv("RAPIDAPI_TWITTER_HOST", "twitter.test")
    calls = fake_http(FakeResponse({"tweets": []}))
    result = TOOL_FUNCTIONS["social_search"]("OpenAI", search_type="Top")
    assert calls[0]["params"] == {"query": "OpenAI", "search_type": "Top"}
    assert result["search_type"] == "Top"


# ---------------- policy (local knowledge + trust boundary) ----------------

def test_policy_empty_query_returns_no_results() -> None:
    result = TOOL_FUNCTIONS["policy"]("")
    assert result["results"] == []


def test_policy_area_filter_only_returns_that_area() -> None:
    # policy_area="data_privacy" -> every result has policy_area == "data_privacy".
    result = TOOL_FUNCTIONS["policy"](
        "API key customer data",
        policy_area="data_privacy",
    )
    assert result["results"]
    assert all(item["policy_area"] == "data_privacy" for item in result["results"])


def test_policy_instruction_like_lines_go_to_untrusted_text() -> None:
    # One policy file contains a quoted line that tries to give the assistant orders.
    # Query that section (source_citation) and assert: that line is in untrusted_text, NOT in facts.
    result = TOOL_FUNCTIONS["policy"](
        "injection assistant",
        policy_area="source_citation",
    )
    assert result["results"]
    combined_untrusted = "\n".join(
        "\n".join(item["untrusted_text"]) for item in result["results"]
    )
    combined_facts = "\n".join(item["facts"] for item in result["results"])
    assert "ignore the citation policy" in combined_untrusted.lower()
    assert "ignore the citation policy" not in combined_facts.lower()


# ---------------- YOUR NEW TOOL(S) ----------------
# Write at least 3 tests per tool your team adds:
#   1. happy path (mocked if it calls an API)
#   2. bad / missing input from the model (empty string, wrong type, out-of-enum value)
#   3. failure path (missing key, HTTP error, timeout) -> returns error dict, does not raise

def test_my_new_tool_happy_path() -> None:
    result = TOOL_FUNCTIONS["dedupe"](
        items=[
            {"url": "https://example.com/a"},
            {"url": "https://example.com/a"},
        ]
    )
    assert result["removed_count"] == 1
    assert len(result["items"]) == 1


def test_my_new_tool_bad_input_from_model() -> None:
    result = TOOL_FUNCTIONS["dedupe"](items=["bad item"])
    assert result["error"] == "TypeError"


def test_my_new_tool_failure_returns_error_dict() -> None:
    result = TOOL_FUNCTIONS["dedupe"](items=None)
    assert result["error"] == "ValueError"


# ---------------- dedupe ----------------

def test_dedupe_removes_duplicate_urls_and_preserves_order() -> None:
    dedupe_tool = TOOL_FUNCTIONS["dedupe"]

    result = dedupe_tool(items=[
        {"title": "First", "url": "https://example.com/a"},
        {"title": "Duplicate", "url": "https://example.com/a"},
        {"title": "Second", "url": "https://example.com/b"},
    ])

    assert result["removed_count"] == 1
    assert result["items"] == [
        {"title": "First", "url": "https://example.com/a"},
        {"title": "Second", "url": "https://example.com/b"},
    ]


def test_dedupe_preserves_items_without_url() -> None:
    dedupe_tool = TOOL_FUNCTIONS["dedupe"]

    result = dedupe_tool(items=[
        {"title": "No link"},
        {"title": "With link", "url": "https://example.com/a"},
    ])

    assert result["removed_count"] == 0
    assert len(result["items"]) == 2


def test_dedupe_invalid_items_returns_error_dict() -> None:
    dedupe_tool = TOOL_FUNCTIONS["dedupe"]

    result = dedupe_tool(items=["not an object"])

    assert result["error"] == "TypeError"
    assert "items[0]" in result["message"]


def test_dedupe_none_returns_error_dict() -> None:
    dedupe_tool = TOOL_FUNCTIONS["dedupe"]

    result = dedupe_tool(items=None)

    assert result["error"] == "ValueError"