"""Bound entry-point growth and check active local links, not historical references."""
import re
from pathlib import Path
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name, max_words", [("AGENTS.md", 700), ("docs/backlog.md", 1000)])
def test_entry_docs_stay_bounded(name, max_words):
    words = len((ROOT / name).read_text().split())
    assert words <= max_words, (
        f"{name}: {words} words exceeds {max_words}. "
        "Move dated evidence to sessions and requirements to their contract, rather than raising the limit."
    )


def test_active_local_document_links_resolve():
    paths = [ROOT / name for name in ("README.md", "AGENTS.md", "data/README.md")]
    paths.extend((ROOT / "docs").glob("*.md"))
    missing = []
    for path in paths:
        for link in re.findall(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", path.read_text()):
            target = link.split("#")[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            if not (path.parent / unquote(target)).exists():
                missing.append(f"{path.relative_to(ROOT)} -> {target}")
    assert not missing, "\n".join(missing)
