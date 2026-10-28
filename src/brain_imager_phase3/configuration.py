from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from .common import load_json, require

@dataclass(frozen=True)
class Config:
    raw: dict
    root: Path
    work: Path
    phase2: Path
    path: Path

    @property
    def study(self) -> Path:
        return self.work / "pilot"

def load_config(path: str | Path) -> Config:
    p = Path(path).resolve()
    d = load_json(p)
    require(d.get("schema_version") == 1, "Unsupported configuration schema")
    root = (p.parent / d["project_root"]).resolve()
    work = (root / d["workspace"]).resolve()
    require(set(d["decoders"]) <= {"umbrae", "braincap", "mindeye2"} and len(d["decoders"]) > 0,
            "Choose named Phase 2 decoder variants; arbitrary substitutes are not accepted")
    require(len(d["decoders"]) == len(set(d["decoders"])), "Duplicate decoder selection")
    require(1 <= d["pilot_size"] <= d["limits"]["max_pilot_stimuli"] <= 50,
            "Phase 3 is limited to a pilot of at most 50 stimuli")
    require(1 <= d["repeats"] <= 5, "Use 1–5 pilot repeats")
    r = d["retrieval"]
    require(r["method"] == "sqlite_fts5_bm25", "This version implements the frozen lexical BM25 retriever")
    require(1 <= r["top_k"] <= 10 and 16 <= r["context_token_budget"] <= 1000, "Invalid retrieval budget")
    m = d["model"]
    require(m["provider"] == "openai_chat_completions", "Unsupported provider; no silent fallback")
    require(m["base_url"] == "https://api.openai.com/v1", "This audited provider sends only to the official API endpoint")
    require(32 <= m["max_completion_tokens"] <= 2048, "Invalid output token limit")
    require(m["input_usd_per_million"] > 0 and m["output_usd_per_million"] > 0, "Enter nonzero current model prices")
    require(d["limits"]["max_api_attempts"] > 0 and d["limits"]["max_estimated_usd"] > 0, "Set finite positive cost/call limits")
    return Config(d, root, work, work / "phase2", p)

