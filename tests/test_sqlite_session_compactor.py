from __future__ import annotations

from core.ai.utils.sqlite_session_compactor import compact_sqlite_session_items


def _mk(role: str, text: str) -> dict:
    return {"role": role, "content": text, "type": "message"}


def test_compactor_noop_when_within_budget() -> None:
    items = [_mk("user", "hello"), _mk("assistant", "hi there")]
    result, stats = compact_sqlite_session_items(items, encoding=None, target_tokens=10_000)

    assert result == items
    assert stats.did_compact is False
    assert stats.original_items == 2
    assert stats.result_items == 2


def test_compactor_adds_summary_and_keeps_recent_tail() -> None:
    items = []
    for idx in range(20):
        items.append(_mk("user", f"User message {idx}: " + ("x" * 400)))
        items.append(_mk("assistant", f"Assistant message {idx}: " + ("y" * 400)))

    result, stats = compact_sqlite_session_items(
        items,
        encoding=None,
        target_tokens=800,  # force compaction
        summary_budget_tokens=200,
        recent_budget_ratio=0.7,
    )

    assert stats.did_compact is True
    assert stats.original_items == len(items)
    assert stats.result_items == len(result)
    assert stats.result_tokens <= stats.target_tokens

    # Preserve most recent item (possibly shrunk, but same role)
    assert isinstance(result[-1], dict)
    assert result[-1].get("role") == items[-1].get("role")


def test_compactor_shrinks_single_huge_tail_item() -> None:
    huge = _mk("assistant", "Z" * 10_000)
    items = [_mk("user", "short"), huge]

    result, stats = compact_sqlite_session_items(
        items,
        encoding=None,
        target_tokens=200,
        summary_budget_tokens=0,
        recent_budget_ratio=0.9,
    )

    assert stats.did_compact is True
    assert stats.result_tokens <= stats.target_tokens
    assert isinstance(result[-1], dict)
    assert len(str(result[-1].get("content", ""))) < len(str(huge.get("content", "")))
