"""Portable, strict file operations. No shell commands or platform-specific paths."""
from __future__ import annotations
import datetime as dt
import hashlib
import importlib.metadata
import json
import os
import platform
import sqlite3
from pathlib import Path
from typing import Any

class AuditError(Exception):
    """An invariant failed; stop rather than silently replace scientific inputs."""

def require(ok: bool, message: str) -> None:
    if not ok:
        raise AuditError(message)

def strict_loads(text: str) -> Any:
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, f"Duplicate JSON key: {key}")
            out[key] = value
        return out
    try:
        return json.loads(text, object_pairs_hook=pairs,
                          parse_constant=lambda s: (_ for _ in ()).throw(AuditError(f"Invalid JSON number: {s}")))
    except (ValueError, TypeError) as exc:
        raise AuditError(f"Invalid JSON: {exc}") from exc

def load_json(path: Path) -> Any:
    require(path.is_file(), f"Missing file: {path}")
    return strict_loads(path.read_text(encoding="utf-8-sig"))

def load_jsonl(path: Path) -> list[dict]:
    require(path.is_file(), f"Missing file: {path}")
    return [strict_loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]

def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()

def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha_file(path: Path) -> str:
    require(path.is_file(), f"Missing file: {path}")
    h = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()

def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".writing")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)

def save_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")

def save_jsonl(path: Path, rows: list[dict]) -> None:
    atomic_text(path, "".join(canonical(row) + "\n" for row in rows))

def unique(rows: list[dict], key: str) -> dict:
    out = {}
    for row in rows:
        require(key in row and row[key] not in out, f"Missing or duplicate {key}")
        out[row[key]] = row
    return out

def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()

def stable_int(*parts: Any) -> int:
    return int(digest(parts)[:16], 16)

def runtime_info() -> dict:
    versions = {}
    for name in ("httpx", "tiktoken", "Pillow"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not installed"
    return {"python": platform.python_version(), "platform": platform.platform(),
            "sqlite": sqlite3.sqlite_version, "dependencies": versions}

