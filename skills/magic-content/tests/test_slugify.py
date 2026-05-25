"""Tests for slugify.py — topic to filesystem-safe slug."""
import pytest

from slugify import slugify


def test_simple_lowercase():
    assert slugify("Transformer Attention") == "transformer-attention"


def test_strips_punctuation():
    assert slugify("RLHF: A Deep Dive!") == "rlhf-a-deep-dive"


def test_collapses_whitespace():
    assert slugify("  multi   space   topic  ") == "multi-space-topic"


def test_unicode_to_ascii():
    assert slugify("Café résumé naïve") == "cafe-resume-naive"


def test_strips_emoji():
    assert slugify("Topic 🚀 launch") == "topic-launch"


def test_max_60_chars():
    long = "a " * 100
    out = slugify(long)
    assert len(out) <= 60
    assert not out.endswith("-")


def test_empty_input_raises():
    with pytest.raises(ValueError):
        slugify("")


def test_only_symbols_raises():
    with pytest.raises(ValueError):
        slugify("!!!@@@###")


def test_idempotent():
    s = slugify("Some Topic")
    assert slugify(s) == s
