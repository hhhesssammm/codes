from __future__ import annotations
import random
from pathlib import Path
from .annotations import load_frozen_pre
from .assets import read_ids
from .common import canonical, digest, load_json, load_jsonl, require, runtime_info, save_json, save_jsonl, sha_file, stable_int, unique
from .selection import pilot_rows, load_selection
from .retrieval import Retriever, render_context, validate_index
from .tokenization import Tokenizer
from .prompts import request_body, SYSTEM_PROMPT

CONDITIONS = {
    "decoded": "Unchanged decoded caption; no model call",
    "rewrite_only": "Original caption, no retrieved context",
    "rag_original": "Original caption, context from original query",
    "rag_query_repaired": "Original caption, context from human-repaired query (primary query-only intervention)",
    "rag_caption_repaired": "Human-repaired caption, context from original query (oracle input control)",
    "rag_both_repaired": "Human-repaired caption and query (oracle combined control)",
    "random_context": "Original caption, length-matched random other-image context",
}

def source_code_hash():
    root = Path(__file__).parent
    return digest({p.name: sha_file(p) for p in sorted(root.iterdir()) if p.suffix in {".py", ".html"}})

def cost_reservation(body, model):
    # UTF-8 bytes plus overhead intentionally overestimates normal text input tokens.
    # This is a client-side estimate, not a provider-enforced dollar cap.
    input_bound = len(canonical({"messages": body["messages"], "response_format": body["response_format"]}).encode()) + 512
    output_bound = model["max_completion_tokens"]
    return {"input_token_reservation": input_bound, "output_token_reservation": output_bound,
            "reserved_usd": (input_bound * model["input_usd_per_million"] + output_bound * model["output_usd_per_million"]) / 1e6}

def context_record(docs, text, tokenizer):
    original, spans = render_context(docs)
    require(original.startswith(text), "Context clipping must preserve an actual retrieved prefix")
    visible = []
    for s in spans:
        excerpt = text[s["start"]:min(s["end"], len(text))]
        if excerpt:
            visible.append(dict(s, displayed_excerpt=excerpt, fully_displayed=len(excerpt) == s["end"] - s["start"]))
    return {"retrieved_documents": docs, "displayed_documents": visible,
            "context_text": text, "context_sha256": digest(text), "context_tokens": tokenizer.count(text),
            "unclipped_context_tokens": tokenizer.count(original), "truncated": text != original,
            "partial_caption_count": sum(not d["fully_displayed"] for d in visible),
            "retrieved_but_not_displayed": len(docs) - len(visible)}

def create_plan(cfg):
    pre = load_frozen_pre(cfg); index = validate_index(cfg)
    tokenizer = Tokenizer(cfg.raw["retrieval"]["tokenizer"], cfg.work / "tokenizer_cache")
    eligible = read_ids(cfg.phase2 / "results/eligible_coco_image_ids.txt")
    excluded = {r["coco_image_id"] for r in load_jsonl(cfg.phase2 / "results/retrieval_exclusions.jsonl")}
    ann = unique(pre["rows"], "row_id")
    retriever = Retriever(cfg.work / "corpus.sqlite3", eligible, excluded)
    jobs = []; contexts = []; diagnostics = []; model = cfg.raw["model"]; settings = cfg.raw["retrieval"]
    groups = load_json(cfg.phase2 / "results/target_similarity_groups.json")["components"]
    cluster = {i: min(g) for g in groups for i in g}
    try:
        for row in pilot_rows(cfg):
            rid = row["manifest_row_id"]; a = ann[rid]; c0 = row["caption"]; c1 = a["repaired_query"]
            raw_docs = retriever.search(c0, settings["top_k"])
            raw_search = dict(retriever.last_search_stats)
            fixed_docs = retriever.search(c1, settings["top_k"]) if a["diagnostic_eligible"] else raw_docs
            fixed_search = dict(retriever.last_search_stats) if a["diagnostic_eligible"] else dict(raw_search)
            raw_text = render_context(raw_docs)[0]; fixed_text = render_context(fixed_docs)[0]
            both_nonempty = bool(raw_text and fixed_text)
            if settings["match_original_corrected_context_lengths"] and both_nonempty:
                raw_text, fixed_text = tokenizer.matched([raw_text, fixed_text], settings["context_token_budget"])
            else:
                raw_text = tokenizer.clip(raw_text, settings["context_token_budget"])
                fixed_text = tokenizer.clip(fixed_text, settings["context_token_budget"])
            raw_context = context_record(raw_docs, raw_text, tokenizer)
            fixed_context = context_record(fixed_docs, fixed_text, tokenizer)
            raw_context["search"] = raw_search; fixed_context["search"] = fixed_search
            raw_set = {d["image_id"] for d in raw_docs}; fixed_set = {d["image_id"] for d in fixed_docs}
            diagnostics.append({"row_id": rid, "diagnostic_eligible": a["diagnostic_eligible"],
                "retrieved_image_jaccard": len(raw_set & fixed_set) / len(raw_set | fixed_set) if raw_set | fixed_set else None,
                "context_changed": raw_text != fixed_text, "matched_context_lengths": tokenizer.count(raw_text) == tokenizer.count(fixed_text),
                "original_zero_hits": not raw_docs, "repaired_zero_hits": not fixed_docs,
                "original_partial_captions": raw_context["partial_caption_count"],
                "repaired_partial_captions": fixed_context["partial_caption_count"],
                "original_tokens": tokenizer.count(raw_text), "repaired_tokens": tokenizer.count(fixed_text)})
            for name, query, context in [("original", c0, raw_context), ("repaired", c1, fixed_context)]:
                contexts.append(dict(context, row_id=rid, query_variant=name, query=query, repeat=None))
            for repeat in range(cfg.raw["repeats"]):
                rng = random.Random(stable_int(cfg.raw["run_seed"], rid, repeat, "random_context"))
                random_docs = retriever.random_context(len(raw_docs), rng, tokenizer.count(raw_text), tokenizer)
                random_full = render_context(random_docs)[0]
                random_text = tokenizer.clip(random_full, tokenizer.count(raw_text))
                # Rare Unicode boundary differences are recorded, never silently padded with invented content.
                random_record = context_record(random_docs, random_text, tokenizer)
                random_record["length_matched_to_original"] = tokenizer.count(random_text) == tokenizer.count(raw_text)
                require(random_record["length_matched_to_original"], "Random context token matching failed; no generation plan was created")
                contexts.append(dict(random_record, row_id=rid, query_variant="random", query=None, repeat=repeat))
                variants = [("decoded", c0, ""), ("rewrite_only", c0, ""),
                            ("rag_original", c0, raw_text), ("random_context", c0, random_text)]
                if a["diagnostic_eligible"]:
                    variants.extend([("rag_query_repaired", c0, fixed_text),
                                     ("rag_caption_repaired", c1, raw_text), ("rag_both_repaired", c1, fixed_text)])
                for condition, source, context in variants:
                    body = None if condition == "decoded" else request_body(model, source, context)
                    request_key = digest([rid, repeat, body]) if body else None
                    job = {"row_id": rid, "condition": condition, "repeat": repeat,
                           "subject": row["subject"], "decoder": row["decoder"], "decoder_variant": row["decoder_variant"],
                           "coco_image_id": row["coco_image_id"], "nsd_id_zero_based": row["nsd_id_zero_based"],
                           "sample_key": row["sample_key"], "cluster_id": cluster[row["coco_image_id"]],
                           "caption_file_sha256": row["caption_file_sha256"], "source_caption": source,
                           "original_caption_sha256": row["caption_utf8_sha256"],
                           "context_sha256": digest(context), "request_body": body, "request_key": request_key,
                           "reservation": cost_reservation(body, model) if body else None}
                    job["job_id"] = digest([rid, condition, repeat, job["request_key"]])[:24]
                    jobs.append(job)
    finally:
        retriever.close()
    jobs.sort(key=lambda j: digest([cfg.raw["run_seed"], j["job_id"]]))
    requests = {j["request_key"]: j for j in jobs if j["request_key"]}
    dollars = sum(j["reservation"]["reserved_usd"] for j in requests.values())
    require(len(requests) <= cfg.raw["limits"]["max_api_attempts"], "Planned unique calls exceed configured attempt cap")
    require(dollars <= cfg.raw["limits"]["max_estimated_usd"], "Plan exceeds configured cost reservation; no API calls made")
    plan = {"schema_version": 1, "scope": "Phase 3 exploratory pilot only", "config": cfg.raw,
            "planning_runtime": runtime_info(),
            "selection_sha256": load_selection(cfg)["selection_sha256"], "pre_annotations_sha256": pre["frozen_sha256"],
            "corpus_database_sha256": index["database_sha256"], "source_code_sha256": source_code_hash(),
            "prompt_sha256": digest(SYSTEM_PROMPT), "conditions": CONDITIONS,
            "unique_api_requests": len(requests), "estimated_reservation_usd": dollars,
            "jobs": jobs, "contexts": contexts, "retrieval_diagnostics": diagnostics}
    plan["plan_sha256"] = digest(plan)
    path = cfg.study / "plan.json"
    if path.exists():
        require(load_json(path) == plan, "Existing plan is frozen; inputs/config/code changed. Do not mix runs.")
    else:
        save_json(path, plan)
        save_jsonl(cfg.study / "retrieval_contexts.jsonl", contexts)
        save_jsonl(cfg.study / "retrieval_diagnostics.jsonl", diagnostics)
    return {"plan_file": str(path), "planned_outputs": len(jobs), "unique_api_requests": len(requests),
            "estimated_reservation_usd": dollars, "paid_calls_made": 0, "diagnostic_rows": sum(a["diagnostic_eligible"] for a in pre["rows"])}

def load_plan(cfg, verify_inputs=True):
    plan = load_json(cfg.study / "plan.json")
    require(plan["plan_sha256"] == digest({k: v for k, v in plan.items() if k != "plan_sha256"}), "Plan hash mismatch")
    require(plan["config"] == cfg.raw, "Config changed after plan freeze")
    require(plan["source_code_sha256"] == source_code_hash(), "Pipeline code changed after planning")
    unique(plan["jobs"], "job_id")
    if verify_inputs:
        pre = load_frozen_pre(cfg); index = validate_index(cfg)
        require(plan["pre_annotations_sha256"] == pre["frozen_sha256"], "Annotations changed after planning")
        require(plan["corpus_database_sha256"] == index["database_sha256"], "Corpus changed after planning")
    return plan
