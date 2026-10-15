"""Append-only audit trail at output/audit_trail.json.

The file is one JSON array. Each append reads the array, adds the entry and
atomically replaces the file, so it is valid JSON after every step and earlier
entries are never changed or dropped. If the file can't be read as a JSON array
we refuse to write rather than risk wiping it.
"""

import json
import os
import threading

from backend.llm import PROJECT_ROOT
from backend.models import AuditEntry

AUDIT_PATH = PROJECT_ROOT / "output" / "audit_trail.json"
RESULT_CHARS = 200

_lock = threading.Lock()


def short(value: object, limit: int = RESULT_CHARS) -> str:
    """A one-line summary of a tool result or answer, truncated to `limit` characters."""
    text = value if isinstance(value, str) else json.dumps(value, default=str, separators=(",", ":"))
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def read_audit() -> list[dict]:
    """All entries so far ([] if the file doesn't exist yet or is empty)."""
    if not AUDIT_PATH.exists():
        return []
    text = AUDIT_PATH.read_text()
    if not text.strip():
        return []
    entries = json.loads(text)
    if not isinstance(entries, list):
        raise ValueError(f"{AUDIT_PATH} is not a JSON array; refusing to overwrite it.")
    return entries


def append_audit(entry: AuditEntry) -> None:
    """Add one entry to the end of the trail."""
    with _lock:
        entries = read_audit()
        entries.append(entry.model_dump(mode="json"))
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = AUDIT_PATH.with_name(AUDIT_PATH.name + ".tmp")
        tmp.write_text(json.dumps(entries, indent=2) + "\n")
        os.replace(tmp, AUDIT_PATH)
