"""Shared pytest fixtures for magic-content tests."""
import json
import sys
from pathlib import Path

import pytest

# Make scripts/ importable in tests
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def tmp_raw_dir(tmp_path):
    """An isolated raw/notebooklm/ root for manifest tests."""
    root = tmp_path / "raw" / "notebooklm"
    root.mkdir(parents=True)
    return root


@pytest.fixture
def sample_websearch_youtube():
    """Sample WebSearch results for `site:youtube.com` query."""
    return [
        {"url": "https://www.youtube.com/watch?v=abc123",
         "title": "Transformer Attention Explained",
         "snippet": "Deep dive on attention mechanism..."},
        {"url": "https://www.youtube.com/watch?v=def456",
         "title": "Self-Attention in Transformers",
         "snippet": "Visual explanation..."},
    ]


@pytest.fixture
def sample_websearch_web():
    return [
        {"url": "https://lilianweng.github.io/posts/attention/",
         "title": "Attention? Attention!",
         "snippet": "A blog post on attention mechanisms..."},
    ]


@pytest.fixture
def sample_websearch_pdf():
    return [
        {"url": "https://arxiv.org/pdf/1706.03762.pdf",
         "title": "Attention Is All You Need",
         "snippet": "The Transformer paper..."},
    ]
