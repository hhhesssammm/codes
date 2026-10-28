from __future__ import annotations
from contextlib import contextmanager
import json
import os
import sqlite3
from pathlib import Path
from .common import AuditError, canonical, digest, require, runtime_info, save_json, save_jsonl, utc_now
from .planning import load_plan
from .provider import OpenAIProvider, ProviderFailure

@contextmanager
def execution_lock(folder):
    lock = folder / "execution.lock"
    try:
        with lock.open("x", encoding="utf-8") as f:
            f.write(canonical({"pid": os.getpid(), "started_utc": utc_now()}))
    except FileExistsError as exc:
        raise AuditError("Execution lock exists. Stop any active run before removing a stale execution.lock; never run concurrent pilots in one folder.") from exc
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)

class Ledger:
    def __init__(self, path: Path, plan_sha):
        self.con = sqlite3.connect(path)
        self.con.row_factory = sqlite3.Row
        self.con.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT)")
        self.con.execute("CREATE TABLE IF NOT EXISTS requests(request_key TEXT PRIMARY KEY,status TEXT NOT NULL,result TEXT,error TEXT,attempts INTEGER NOT NULL DEFAULT 0)")
        self.con.execute("CREATE TABLE IF NOT EXISTS attempts(attempt_id INTEGER PRIMARY KEY, request_key TEXT, reservation_usd REAL, started_utc TEXT, finished_utc TEXT, status TEXT, actual_usd REAL)")
        old = self.con.execute("SELECT value FROM meta WHERE key='plan_sha256'").fetchone()
        if old is not None and old[0] != plan_sha:
            self.con.close()
            raise AuditError("Ledger belongs to another frozen plan")
        self.con.execute("INSERT OR IGNORE INTO meta VALUES ('plan_sha256',?)", (plan_sha,)); self.con.commit()

    def close(self):
        self.con.close()

    def get(self, key):
        r = self.con.execute("SELECT * FROM requests WHERE request_key=?", (key,)).fetchone()
        return dict(r) if r else None

    def totals(self):
        n, reserve, actual = self.con.execute("SELECT count(*),coalesce(sum(reservation_usd),0),coalesce(sum(actual_usd),0) FROM attempts").fetchone()
        unknown = self.con.execute("SELECT count(*) FROM attempts WHERE actual_usd IS NULL").fetchone()[0]
        return {"api_attempts": n, "reserved_usd_including_failed_attempts": reserve,
                "known_usage_cost_usd": actual, "attempts_with_unknown_actual_cost": unknown}

    def start(self, key, reservation, limits, retry_failed):
        old = self.get(key)
        require(not old or old["status"] != "completed", "Completed requests must be reused")
        require(not old or retry_failed, "A previous attempt failed or has an uncertain outcome. Inspect the ledger/provider usage, then use --retry-failed deliberately.")
        require(not old or old["attempts"] < limits["max_attempts_per_job"], "Per-request attempt limit reached")
        totals = self.totals()
        require(totals["api_attempts"] < limits["max_api_attempts"], "API attempt cap reached")
        require(totals["reserved_usd_including_failed_attempts"] + reservation <= limits["max_estimated_usd"] + 1e-12, "Cost reservation cap reached")
        self.con.execute("INSERT INTO requests(request_key,status,attempts) VALUES (?,'started',1) ON CONFLICT(request_key) DO UPDATE SET status='started',attempts=attempts+1,error=NULL", (key,))
        cur = self.con.execute("INSERT INTO attempts(request_key,reservation_usd,started_utc,status) VALUES (?,?,?,'started')", (key, reservation, utc_now()))
        self.con.commit()  # Reserve BEFORE networking; crash/timeout cannot bypass the cap.
        return cur.lastrowid

    def finish(self, key, attempt_id, result, error, model):
        cost = None
        if result and isinstance(result.get("prompt_tokens"), int) and isinstance(result.get("completion_tokens"), int):
            cost = (result["prompt_tokens"] * model["input_usd_per_million"] + result["completion_tokens"] * model["output_usd_per_million"]) / 1e6
        status = "completed" if result else "failed"
        self.con.execute("UPDATE requests SET status=?,result=?,error=? WHERE request_key=?", (status, canonical(result) if result else None, canonical(error) if error else None, key))
        self.con.execute("UPDATE attempts SET status=?,actual_usd=?,finished_utc=? WHERE attempt_id=?", (status, cost, utc_now(), attempt_id))
        self.con.commit()

def export_outputs(cfg, plan, ledger):
    rows = []
    for job in plan["jobs"]:
        result = None; status = "not_run"; error = None
        if job["condition"] == "decoded":
            result = {"caption": job["source_caption"], "returned_model": "unchanged_decoder_cache", "response_id": None}
            status = "completed"
        else:
            cached = ledger.get(job["request_key"])
            if cached:
                status = cached["status"]
                result = json.loads(cached["result"]) if cached["result"] else None
                error = json.loads(cached["error"]) if cached["error"] else None
        rows.append({k: job[k] for k in ["job_id", "row_id", "condition", "repeat", "subject", "decoder", "decoder_variant", "coco_image_id", "nsd_id_zero_based", "sample_key", "cluster_id", "request_key", "context_sha256", "original_caption_sha256"]} |
                    {"plan_sha256": plan["plan_sha256"], "status": status,
                     "caption": result["caption"] if result else None,
                     "output_sha256": digest(result["caption"]) if result else None,
                     "model_metadata": {k: result.get(k) for k in ["returned_model", "response_id", "system_fingerprint", "http_request_id", "usage"]} if result else None,
                     "error": error})
    save_jsonl(cfg.study / "outputs.jsonl", rows)
    receipt = dict(ledger.totals(), plan_sha256=plan["plan_sha256"], planned_outputs=len(rows),
                   execution_runtime=runtime_info(),
                   completed_outputs=sum(r["status"] == "completed" for r in rows),
                   incomplete_outputs=sum(r["status"] != "completed" for r in rows),
                   note="Client-side cost reservations are estimates, not provider-enforced billing limits. Cached-input discounts are not assumed.")
    save_json(cfg.study / "execution_receipt.json", receipt)
    return receipt

def execute_plan(cfg, execute=False, retry_failed=False, max_calls=None, provider_factory=OpenAIProvider):
    plan = load_plan(cfg)
    if not execute:
        return {"mode": "preview_only", "unique_requests": plan["unique_api_requests"],
                "estimated_reservation_usd": plan["estimated_reservation_usd"], "api_calls_made": 0,
                "next": "Use run --execute on your own machine only after reviewing the frozen plan and cost estimate"}
    if max_calls is not None:
        require(max_calls > 0, "max-calls must be positive")
    provider = provider_factory(cfg.raw["model"])
    try:
        with execution_lock(cfg.study):
            ledger = Ledger(cfg.study / "run.sqlite3", plan["plan_sha256"])
            calls = 0; seen = set()
            try:
                for job in plan["jobs"]:
                    key = job["request_key"]
                    if key is None or key in seen:
                        continue
                    seen.add(key)
                    old = ledger.get(key)
                    if old and old["status"] == "completed":
                        continue
                    if max_calls is not None and calls >= max_calls:
                        break
                    attempt_id = ledger.start(key, job["reservation"]["reserved_usd"], cfg.raw["limits"], retry_failed)
                    request_id = digest([plan["plan_sha256"], key, attempt_id])[:40]
                    save_json(cfg.study / "requests" / f"{key}.json", {"request_key": key, "body": job["request_body"], "plan_sha256": plan["plan_sha256"]})
                    calls += 1
                    try:
                        result = provider.generate(job["request_body"], request_id)
                    except ProviderFailure as exc:
                        ledger.finish(key, attempt_id, None, {"code": exc.code, "http_status": exc.http_status}, cfg.raw["model"])
                        if exc.raw is not None:
                            save_json(cfg.study / "responses" / f"{key}_attempt{attempt_id}_invalid.json", exc.raw)
                        # Stop on transport/schema failure; do not silently switch models or replace outputs.
                        raise AuditError(f"API attempt stopped: {exc.code} (HTTP {exc.http_status}). Inspect execution_receipt.json and the ledger; no automatic retry was made.") from exc
                    ledger.finish(key, attempt_id, result, None, cfg.raw["model"])
                    save_json(cfg.study / "responses" / f"{key}_attempt{attempt_id}.json", result)
            finally:
                receipt = export_outputs(cfg, plan, ledger)
                ledger.close()
    finally:
        provider.close()
    return dict(receipt, api_calls_this_invocation=calls)
