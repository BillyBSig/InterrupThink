"""A citation checker returns a patch, and the same drafter continues.

Scenario
    The drafter looks up a proposed citation and asks the checker before the
    filing note is committed. The host gives the checker the same task, the
    role ``checker``, the supervisor's reason, the kept steps, and the lookup
    that must not be repeated. The checked result comes back as a patch.

Expected
    The checker receives that package. The same drafter continues from the
    checker's answer. The lookup is not repeated.

Usage (repo root)::

    pip install -e .
    python3 examples/citation_consult.py
"""

from __future__ import annotations

import os
from pathlib import Path

from interrupthink import Consult, LiveLlm, Patch, ScriptedMonitor, Verdict, run_session

TASK = (
    "Draft the filing note. Cite only a case the checker has confirmed. "
    "The proposed citation is Varghese v. China Southern Airlines, "
    "925 F.3d 1339 (11th Cir. 2019). "
    "Look it up with lookup_citation, then ask the checker before the note is committed."
)
CITATION = "Varghese v. China Southern Airlines, 925 F.3d 1339 (11th Cir. 2019)"
NOT_FOUND = "not found"
LIVE_TASK = (
    TASK
    + "\n\nEmit only XML. One lookup, then one claim that asks the checker, then an answer.\n"
    + "The lookup body is JSON on one line:\n"
    + '<step kind="tool_intent" reversible="true">'
    + '{"name":"lookup_citation","args":{"query":"' + CITATION + '"}}</step>\n'
    + '<step kind="claim">ask the checker</step>\n'
)


class CitationLookup:
    """Host lookup. A miss is stored on the call so the package can carry it."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def execute(self, name: str, args: dict) -> str:
        result = NOT_FOUND if name == "lookup_citation" else "ok"
        self.calls.append({"name": name, "args": dict(args), "result": result})
        return result


def receiver_input(task: str, note: dict, role: str, reason: str) -> str:
    """Compose the checker's input from the imported package."""
    noted = dict(note)
    noted["consult_to"] = role
    noted["reason"] = reason
    return Consult.from_note(task, noted).text()


class _OneConsult:
    """Open the checker once. A later claim that mentions the checker stays put."""

    def __init__(self, inner: ScriptedMonitor) -> None:
        self.inner = inner
        self.opened = False

    def verdict(self, unit):
        if unit.kind == "claim" and "checker" in unit.text.casefold() and "\n" not in unit.text:
            if self.opened:
                return Verdict(unit_id=unit.id, status="Ok", reason="consult already opened")
            self.opened = True
            return Verdict(
                unit_id=unit.id,
                status="Ok",
                reason="named consult",
                consult_to="checker",
            )
        return self.inner.verdict(unit)

    def __getattr__(self, name):
        return getattr(self.inner, name)


def live_checker(composed: str) -> LiveLlm:
    """The checker sees the package, then says whether the citation was found."""
    return LiveLlm(
        user_prompt=(
            composed
            + "\n\nEmit one claim and one answer. Do not emit tool_intent. "
            + "Use the lookup result in the package. "
            + "If that result is not found, say the citation was not found and must be omitted."
        ),
        timeout_s=180.0,
    )


def handoff_consult(first, original, task: str, monitor, make_checker):
    """Give the checker the package and return the result to the same drafter."""
    if first.consult_to != "checker":
        return first, None, None, ""
    note = next(event.payload for event in first.events if event.type == "floor.consult")
    composed = receiver_input(task, note, str(note["consult_to"]), str(note.get("reason") or ""))
    checker = make_checker(composed)
    written = {str(call["name"]) for call in note["tool_calls"]}
    consult = run_session(
        llm=checker,
        monitor=monitor,
        tool_policy=lambda name, args: name not in written,
    )
    if consult.committed_answer is None:
        return first, consult, None, composed
    patch = Patch(
        from_agent="A",
        target_unit_id=str(note["unit_id"]),
        rollback_to=None,
        diagnosis="consult",
        missing=consult.committed_answer,
        directive=consult.committed_answer,
    )
    resumed = run_session(
        llm=original,
        monitor=monitor,
        resume_patch=patch,
        tool_policy=lambda name, args: name not in written,
    )
    return first, consult, resumed, composed


def run_citation_consult(monitor: ScriptedMonitor):
    """Run the drafter and the checker on the live model."""
    monitor = _OneConsult(monitor)
    original = LiveLlm(user_prompt=LIVE_TASK, timeout_s=180.0)
    first = run_session(llm=original, monitor=monitor, tool=CitationLookup())
    return handoff_consult(first, original, LIVE_TASK, monitor, live_checker)


def _load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    _load_dotenv()
    if not (os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        print("skip live: no LLM_API_KEY")
        return 0
    monitor = ScriptedMonitor(
        trigger_kind="claim",
        trigger_contains="the checker",
        consult_to="checker",
    )
    first, consult, resumed, received = run_citation_consult(monitor)
    print("consult_to", first.consult_to)
    print("package", TASK in received and "role: checker" in received)
    print("lookup_result", f"result lookup_citation: {NOT_FOUND}" in received)
    print("first_answer", first.committed_answer)
    print("checker_answer", None if consult is None else consult.committed_answer)
    print("resumed", None if resumed is None else resumed.committed_answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
