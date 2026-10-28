from __future__ import annotations
import argparse
import importlib.metadata
import json
import os
import platform
import sqlite3
import struct
import sys
from pathlib import Path
from .common import AuditError, load_json, require
from .configuration import load_config

def doctor(cfg):
    versions = {}
    for name in ["brain-imager-phase3", "httpx", "tiktoken", "Pillow", "pytest"]:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not installed"
    with sqlite3.connect(":memory:") as c:
        c.execute("CREATE VIRTUAL TABLE check_fts USING fts5(text)")
    return {"python": platform.python_version(), "platform": platform.platform(), "bits": struct.calcsize("P") * 8,
            "sqlite": sqlite3.sqlite_version, "fts5_available": True, "dependencies": versions,
            "phase2_zip_exists": (cfg.root / cfg.raw["phase2_zip"]).is_file(),
            "api_key_present": bool(os.environ.get(cfg.raw["model"]["api_key_env"])),
            "api_called": False, "GPU_required": False,
            "project_root": str(cfg.root), "workspace": str(cfg.work)}

def main(argv=None):
    parser = argparse.ArgumentParser(description="Brain-Imager Phase 3 pilot. Generation is opt-in and human annotations are required.")
    parser.add_argument("--config", default="config/pilot.json", help="JSON config; relative asset paths resolve from project_root")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["doctor", "init", "validate", "pilot", "index", "plan"]:
        sub.add_parser(name)
    fetch = sub.add_parser("fetch"); fetch.add_argument("--what", choices=["captions", "coco", "crops", "all"], required=True)
    pre = sub.add_parser("make-pre"); pre.add_argument("--rater", default="R1")
    freeze = sub.add_parser("freeze-inputs"); freeze.add_argument("--annotations", required=True)
    freeze.add_argument("--annotation-policy", required=True, choices=["single_rater_pilot", "adjudicated_pilot"])
    web = sub.add_parser("annotate"); web.add_argument("--mode", choices=["pre", "post"], required=True)
    web.add_argument("--file", required=True); web.add_argument("--port", type=int, default=8765); web.add_argument("--no-browser", action="store_true")
    run = sub.add_parser("run"); run.add_argument("--execute", action="store_true"); run.add_argument("--retry-failed", action="store_true")
    run.add_argument("--max-calls", type=int)
    review = sub.add_parser("make-review"); review.add_argument("--rater", default="R1"); review.add_argument("--allow-partial-review", action="store_true")
    ev = sub.add_parser("evaluate"); ev.add_argument("--review", required=True); ev.add_argument("--bootstrap", type=int, default=2000)
    compare = sub.add_parser("compare-raters"); compare.add_argument("--a", required=True); compare.add_argument("--b", required=True)
    args = parser.parse_args(argv)
    try:
        cfg = load_config(args.config)
        from . import assets, annotations, evaluation, execution, planning, retrieval, selection
        if args.command == "doctor": result = doctor(cfg)
        elif args.command == "init": result = assets.initialize(cfg)
        elif args.command == "validate":
            result = {"phase2": assets.validate_phase2(cfg), "captions": assets.validate_captions(cfg)}
            if (cfg.work / "corpus.sqlite3").exists(): result["index"] = retrieval.validate_index(cfg)
            if (cfg.study / "crop_receipts.json").exists(): result["official_crops_verified"] = len(annotations.crop_registry(cfg))
        elif args.command == "fetch":
            result = {}
            if args.what in {"captions", "all"}: result["captions"] = assets.fetch_captions(cfg)
            if args.what in {"coco", "all"}: result["coco"] = assets.fetch_coco(cfg)
            if args.what in {"crops", "all"}:
                if not (cfg.study / "selection.json").exists(): selection.create_selection(cfg)
                result["crops"] = assets.fetch_crops(cfg)
        elif args.command == "pilot":
            result = selection.create_selection(cfg)
            result = {k: v for k, v in result.items() if k != "reserved_coco_image_ids"}
        elif args.command == "index": result = retrieval.build_index(cfg)
        elif args.command == "make-pre": result = annotations.create_pre_templates(cfg, args.rater)
        elif args.command == "freeze-inputs": result = annotations.freeze_pre(cfg, Path(args.annotations).resolve(), args.annotation_policy)
        elif args.command == "plan": result = planning.create_plan(cfg)
        elif args.command == "annotate":
            from .web import serve
            serve(cfg, args.mode, Path(args.file).resolve(), args.port, not args.no_browser)
            return 0
        elif args.command == "run": result = execution.execute_plan(cfg, args.execute, args.retry_failed, args.max_calls)
        elif args.command == "make-review": result = evaluation.make_review(cfg, args.rater, args.allow_partial_review)
        elif args.command == "evaluate": result = evaluation.evaluate(cfg, Path(args.review).resolve(), args.bootstrap)
        elif args.command == "compare-raters": result = evaluation.compare_reviewers(cfg, Path(args.a).resolve(), Path(args.b).resolve())
        else: raise AuditError("Unknown command")
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
        return 0
    except (AuditError, FileNotFoundError, KeyError, ValueError, sqlite3.Error) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2

