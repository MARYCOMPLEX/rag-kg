"""Tests for `packages.context.budget` — char-count counter + trim helper."""

from __future__ import annotations

from packages.context.budget import CharCountTokenCounter, trim_to_tokens


def test_char_count_token_counter_is_monotone() -> None:
    # Arrange
    counter = CharCountTokenCounter()
    short = "hello"
    medium = "hello world this is a longer sentence"
    long = medium * 10

    # Act
    short_tokens = counter.count(short)
    medium_tokens = counter.count(medium)
    long_tokens = counter.count(long)

    # Assert
    assert short_tokens >= 1
    assert short_tokens <= medium_tokens <= long_tokens
    assert counter.count("") == 0


def test_trim_to_tokens_returns_input_when_within_budget() -> None:
    # Arrange
    counter = CharCountTokenCounter()
    text = "short text"

    # Act
    result = trim_to_tokens(text, max_tokens=100, counter=counter)

    # Assert
    assert result == text


def test_trim_to_tokens_preserves_prefix() -> None:
    # Arrange
    counter = CharCountTokenCounter()
    text = "A" * 1000

    # Act
    result = trim_to_tokens(text, max_tokens=10, counter=counter)

    # Assert — char/4 heuristic: 10 tokens → ~40 chars allowed
    assert text.startswith(result)
    assert len(result) <= 40
    assert counter.count(result) <= 10


def test_trim_to_tokens_cuts_at_sentence_boundary_when_feasible() -> None:
    # Arrange — long enough to trigger boundary search; multiple sentences
    # so a clean cut exists in the second half.
    counter = CharCountTokenCounter()
    text = (
        "First sentence here. Second sentence follows. "
        "Third sentence keeps going. Fourth sentence trails. "
        "Fifth sentence closes the paragraph."
    )

    # Act — budget that lands mid-paragraph (~80 chars, 20 tokens)
    result = trim_to_tokens(text, max_tokens=20, counter=counter)

    # Assert — should end on a sentence terminator if one exists in the second half of the cut
    assert result != text
    assert text.startswith(result)
    assert result.endswith(". ") or result.endswith(".")


def test_trim_to_tokens_zero_budget_returns_empty() -> None:
    # Arrange
    counter = CharCountTokenCounter()

    # Act
    result = trim_to_tokens("anything", max_tokens=0, counter=counter)

    # Assert
    assert result == ""


def test_trim_to_tokens_handles_empty_text() -> None:
    # Arrange
    counter = CharCountTokenCounter()

    # Act
    result = trim_to_tokens("", max_tokens=10, counter=counter)

    # Assert
    assert result == ""
