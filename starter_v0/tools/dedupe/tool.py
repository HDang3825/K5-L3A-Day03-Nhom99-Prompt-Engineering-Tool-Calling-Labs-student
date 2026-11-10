from __future__ import annotations

from typing import Any


def dedupe(items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Remove duplicate items by URL while preserving original order."""
    if items is None:
        return {
            "tool": "dedupe",
            "error": "ValueError",
            "message": "items must be a list of objects",
        }

    if not isinstance(items, list):
        return {
            "tool": "dedupe",
            "error": "TypeError",
            "message": "items must be a list",
        }

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            return {
                "tool": "dedupe",
                "error": "TypeError",
                "message": f"items[{index}] must be an object",
            }

    unique_items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    removed_count = 0

    for item in items:
        url = item.get("url")

        if not url:
            unique_items.append(item)
            continue

        if not isinstance(url, str):
            return {
                "tool": "dedupe",
                "error": "TypeError",
                "message": "item url must be a string",
            }

        if url in seen_urls:
            removed_count += 1
            continue

        seen_urls.add(url)
        unique_items.append(item)

    return {
        "tool": "dedupe",
        "items": unique_items,
        "removed_count": removed_count,
    }