"""Audit the public documentation boundary.

Run from the source repository root:

    python3 docs/check_publication.py

The audit is intentionally conservative. It checks ``docs/`` and the
user-facing examples and integration cookbooks without reading internal
research files.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
PUBLIC_SCAN_ROOTS = (
    "README.md",
    "CONTRIBUTING.md",
    "pyproject.toml",
    ".env.example",
    "cases",
    "examples",
    "tests",
    "src/README.md",
    "src/interrupthink/__init__.py",
    "src/interrupthink/parse",
    "src/interrupthink/runtime",
    "src/interrupthink/monitor",
    "src/interrupthink/providers",
)
SKIP_CONTENT_CHECK = {"PUBLICATION_POLICY.md", "check_publication.py"}
SKIP_PUBLIC_MARKER_PREFIXES = ("test_eval_",)
FORBIDDEN_PATH_PARTS = {
    ".env",
    "plan",
    "runs",
    "tmp",
    "raw",
    "__pycache__",
}
INTERNAL_MARKERS = re.compile(
    r"\b(?:T\d+(?:\.\d+)?|EXP-G\d+(?:\.\d+)?|ADR-\d{4}|G[0-5]|"
    r"C\d+|B\d+|A\d+(?:\.\d+)?|P\d+|Q\d+|FI)\b|"
    r"\bS-[A-Z0-9-]+\b"
)
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\b(?:OPENAI|ANTHROPIC|AWS|GITHUB)_[A-Z0-9_]*\s*=\s*\S+"),
)
LOCAL_LINK = re.compile(r"\]\((?!https?://|mailto:)([^)#]+)")
FORBIDDEN_LINK_MARKERS = ("/plan/", "plan/", "STATUS.md", "AGENTS.md")


def _forbidden_link(target: str) -> bool:
    normalized = target.replace("\\", "/")
    return any(marker in normalized for marker in FORBIDDEN_LINK_MARKERS)


def audit_paths() -> list[str]:
    errors: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in FORBIDDEN_PATH_PARTS for part in relative.parts):
            errors.append(f"forbidden path: {relative}")
    return errors


def audit_contents() -> list[str]:
    errors: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.name in SKIP_CONTENT_CHECK:
            continue
        text = path.read_text(encoding="utf-8")
        if INTERNAL_MARKERS.search(text):
            errors.append(f"internal marker: {path.relative_to(ROOT)}")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"secret-like value: {path.relative_to(ROOT)}")
    return errors


def _public_files() -> list[Path]:
    files: list[Path] = []
    for relative in PUBLIC_SCAN_ROOTS:
        path = REPO_ROOT / relative
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(candidate for candidate in path.rglob("*") if candidate.is_file())
    return files


def _text_to_scan(path: Path, text: str) -> str:
    if path.parent.name != "tests" or path.suffix != ".py":
        return text
    if text.startswith('"""'):
        end = text.find('"""', 3)
        if end != -1:
            return text[3:end]
    if text.startswith("'''"):
        end = text.find("'''", 3)
        if end != -1:
            return text[3:end]
    return ""


def audit_public_boundary() -> list[str]:
    """Reject internal lab labels from user-facing Markdown and docstrings."""
    errors: list[str] = []
    for path in _public_files():
        if path.name in SKIP_CONTENT_CHECK or any(
            part in FORBIDDEN_PATH_PARTS for part in path.relative_to(REPO_ROOT).parts
        ):
            continue
        if path.name.startswith(SKIP_PUBLIC_MARKER_PREFIXES):
            continue
        text = path.read_text(encoding="utf-8")
        if INTERNAL_MARKERS.search(_text_to_scan(path, text)):
            errors.append(f"internal public marker: {path.relative_to(REPO_ROOT)}")
    return errors


TEST_FILE = re.compile(r"tests/test_[a-z0-9_]+\.py")


def _cited_tests(path: Path) -> set[str]:
    return set(TEST_FILE.findall(path.read_text(encoding="utf-8")))


def audit_results_commands() -> list[str]:
    """Every test file cited in results.md must appear in a public command block."""
    results = ROOT / "results.md"
    commands = _cited_tests(ROOT / "evaluation.md") | _cited_tests(ROOT / "reproducibility.md")
    missing = sorted(_cited_tests(results) - commands)
    return [f"results test missing from reproduction commands: {name}" for name in missing]


def audit_links() -> list[str]:
    errors: list[str] = []
    for path in ROOT.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for target in LOCAL_LINK.findall(text):
            if path.name not in SKIP_CONTENT_CHECK and _forbidden_link(target):
                errors.append(
                    f"unpublished lab link: {path.relative_to(ROOT)} -> {target}"
                )
            target_path = (path.parent / target).resolve()
            if not target_path.exists():
                errors.append(
                    f"missing local link: {path.relative_to(ROOT)} -> {target}"
                )
    return errors


def audit_sync_monitor() -> list[str]:
    """Public docs must not claim overlapping generate+monitor."""
    errors: list[str] = []
    claim = re.compile(r"asynchronous\s+verdicts", re.I)
    for rel in ("README.md", "README.id.md"):
        path = REPO_ROOT / rel
        if path.is_file() and claim.search(path.read_text(encoding="utf-8")):
            errors.append(f"async overlap claim: {rel}")
    for path in ROOT.rglob("*.md"):
        if path.name in SKIP_CONTENT_CHECK:
            continue
        if claim.search(path.read_text(encoding="utf-8")):
            errors.append(f"async overlap claim: {path.relative_to(ROOT)}")
    monitor = (REPO_ROOT / "src" / "interrupthink" / "monitor" / "llm.py").read_text(encoding="utf-8")
    if "urlopen" not in monitor:
        errors.append("live monitor is not blocking HTTP")
    if re.search(r"\b(asyncio|threading\.Thread|concurrent\.futures)\b", monitor):
        errors.append("live monitor added concurrent runtime")
    return errors


def audit_live_background() -> list[str]:
    """Live specialist must not request background continuation."""
    errors: list[str] = []
    live = (REPO_ROOT / "src" / "interrupthink" / "providers" / "live.py").read_text(encoding="utf-8")
    fn = re.search(r"def _responses_request\([\s\S]+?\n\ndef ", live)
    body = fn.group(0) if fn else ""
    if re.search(r'"background"\s*:\s*(stream|True|true)\b', body):
        errors.append("live request enables background continuation")
    if '"background": False' not in body:
        errors.append("live request does not lock background false")
    concepts = (ROOT / "concepts.md").read_text(encoding="utf-8")
    if "does not continue in the background" not in concepts:
        errors.append("concepts dropped no-background generation claim")
    id_concepts = (ROOT / "id" / "concepts.md").read_text(encoding="utf-8")
    if "latar belakang" not in id_concepts:
        errors.append("id concepts dropped no-background generation claim")
    return errors


def audit_tool_policy_docs() -> list[str]:
    """User-facing docs must state omit-policy is allow-if-Ok, not production auth."""
    errors: list[str] = []
    concepts = (ROOT / "concepts.md").read_text(encoding="utf-8")
    if "tool_policy=None" not in concepts:
        errors.append("concepts omitted tool_policy=None")
    if "allow-if-Ok" not in concepts:
        errors.append("concepts omitted allow-if-Ok default")
    id_concepts = (ROOT / "id" / "concepts.md").read_text(encoding="utf-8")
    if "tool_policy=None" not in id_concepts or "allow-if-Ok" not in id_concepts:
        errors.append("id concepts omitted tool_policy allow-if-Ok")
    limitations = (ROOT / "limitations.md").read_text(encoding="utf-8")
    if "tool_policy=None" not in limitations or "allow-if-Ok" not in limitations:
        errors.append("limitations omitted tool_policy allow-if-Ok")
    id_lim = (ROOT / "id" / "limitations.md").read_text(encoding="utf-8")
    if "tool_policy=None" not in id_lim or "allow-if-Ok" not in id_lim:
        errors.append("id limitations omitted tool_policy allow-if-Ok")
    return errors


def audit_core_live_llm() -> list[str]:
    """Mock live-provider tests must run in core CI without credentials."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "core.yml").read_text(
        encoding="utf-8"
    )
    errors: list[str] = []
    if "tests/test_live_llm.py" not in workflow:
        errors.append("core CI omits tests/test_live_llm.py")
    if 'OPENAI_API_KEY: ""' not in workflow or 'LLM_API_KEY: ""' not in workflow:
        errors.append("core CI does not blank live API keys")
    return errors


def audit_unknown_commit() -> list[str]:
    """Public diagrams must not treat Unknown as an unconditional commit permit."""
    errors: list[str] = []
    claim = re.compile(r"Unknown\s+(or|atau)\s+Ok", re.I)
    for rel in ("README.md", "README.id.md"):
        path = REPO_ROOT / rel
        if path.is_file() and claim.search(path.read_text(encoding="utf-8")):
            errors.append(f"Unknown routed with Ok to commit: {rel}")
    for path in ROOT.rglob("*.md"):
        if path.name in SKIP_CONTENT_CHECK:
            continue
        if claim.search(path.read_text(encoding="utf-8")):
            errors.append(f"Unknown routed with Ok to commit: {path.relative_to(ROOT)}")
    live = (REPO_ROOT / "src" / "interrupthink" / "providers" / "live.py").read_text(encoding="utf-8")
    fn = re.search(r"def _cancel_response\([\s\S]+?\n\ndef ", live)
    body = fn.group(0) if fn else ""
    if body.count("urlopen") != 1:
        errors.append("live cancel has duplicate urlopen")
    return errors


def main() -> int:
    errors = (
        audit_paths()
        + audit_contents()
        + audit_links()
        + audit_public_boundary()
        + audit_results_commands()
        + audit_sync_monitor()
        + audit_unknown_commit()
        + audit_live_background()
        + audit_core_live_llm()
        + audit_tool_policy_docs()
    )
    if errors:
        print("Publication audit failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"Publication audit passed: {len(list(ROOT.rglob('*')))} paths checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
