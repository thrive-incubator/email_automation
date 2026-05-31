"""Read/write access to the markdown 'Brain' files.

Layout:
    brain/guardrails.md          global safety rules applied to every reply
    brain/voices/<name>.md       tone/voice presets, selectable per rule
    brain/knowledge/<name>.md    Q&A knowledge the answerer draws from
"""

from pathlib import Path

from .config import BRAIN_DIR

VOICES_DIR = BRAIN_DIR / "voices"
KNOWLEDGE_DIR = BRAIN_DIR / "knowledge"
GUARDRAILS_FILE = BRAIN_DIR / "guardrails.md"


def _safe_name(name: str) -> str:
    """Prevent path traversal; keep a plain filename."""
    cleaned = Path(name).name
    if not cleaned.endswith(".md"):
        cleaned += ".md"
    return cleaned


def _ensure_dirs() -> None:
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)


def list_voices() -> list[str]:
    _ensure_dirs()
    return sorted(p.name for p in VOICES_DIR.glob("*.md"))


def list_knowledge() -> list[str]:
    _ensure_dirs()
    return sorted(p.name for p in KNOWLEDGE_DIR.glob("*.md"))


def read_voice(name: str) -> str:
    p = VOICES_DIR / _safe_name(name)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def read_knowledge(name: str) -> str:
    p = KNOWLEDGE_DIR / _safe_name(name)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def read_guardrails() -> str:
    return GUARDRAILS_FILE.read_text(encoding="utf-8") if GUARDRAILS_FILE.exists() else ""


def read_all_knowledge(names: list[str] | None = None) -> str:
    """Concatenate the named knowledge files.

    - `names=None`  → return every knowledge file (explicit "give me everything").
    - `names=[]`    → return nothing (rule said it needs no knowledge — do not leak).
    - `names=[...]` → return exactly those files (and only those).

    The `None` vs `[]` distinction matters: a rule with empty `knowledge_files`
    must NOT silently get the entire knowledge base in its prompt.
    """
    _ensure_dirs()
    if names is None:
        files = list_knowledge()
    else:
        files = [_safe_name(n) for n in names]
    chunks: list[str] = []
    for fname in files:
        p = KNOWLEDGE_DIR / fname
        if p.exists():
            chunks.append(f"# Source: {fname}\n\n{p.read_text(encoding='utf-8')}")
    return "\n\n---\n\n".join(chunks)


def get_file(kind: str, name: str) -> str:
    if kind == "guardrails":
        return read_guardrails()
    if kind == "voice":
        return read_voice(name)
    if kind == "knowledge":
        return read_knowledge(name)
    raise ValueError(f"unknown brain kind: {kind}")


def write_file(kind: str, name: str, content: str) -> None:
    _ensure_dirs()
    if kind == "guardrails":
        GUARDRAILS_FILE.write_text(content, encoding="utf-8")
    elif kind == "voice":
        (VOICES_DIR / _safe_name(name)).write_text(content, encoding="utf-8")
    elif kind == "knowledge":
        (KNOWLEDGE_DIR / _safe_name(name)).write_text(content, encoding="utf-8")
    else:
        raise ValueError(f"unknown brain kind: {kind}")


def append_knowledge(name: str, question: str, answer: str) -> None:
    """Append a corrected Q&A pair — the learning loop from the review UI."""
    _ensure_dirs()
    p = KNOWLEDGE_DIR / _safe_name(name)
    existing = p.read_text(encoding="utf-8") if p.exists() else f"# {name}\n"
    entry = f"\n\n## Q: {question.strip()}\n\n{answer.strip()}\n"
    p.write_text(existing + entry, encoding="utf-8")
