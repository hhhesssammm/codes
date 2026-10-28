"""Image-grounded human evaluation. No automatic truth labels or invented outcomes."""
from __future__ import annotations
import collections
import csv
import math
import random
from pathlib import Path
from .annotations import load_frozen_pre, validate_review
from .common import digest, load_json, load_jsonl, require, save_json, save_jsonl, sha_file, stable_int, unique
from .planning import load_plan

def make_review(cfg, rater, allow_partial=False):
    require(rater and rater.replace("_", "").replace("-", "").isalnum(), "Use a simple rater ID")
    plan = load_plan(cfg); pre = unique(load_frozen_pre(cfg)["rows"], "row_id")
    outputs = load_jsonl(cfg.study / "outputs.jsonl")
    require({r["job_id"] for r in outputs} == {j["job_id"] for j in plan["jobs"]}, "Outputs do not cover the planned jobs")
    missing = [r for r in outputs if r["status"] != "completed"]
    require(allow_partial or not missing, "Generation is incomplete. Resume it, or use --allow-partial-review to explicitly record attrition.")
    tasks = []; keys = []; grouped = {}
    for out in outputs:
        if out["status"] != "completed":
            continue
        require(digest(out["caption"]) == out["output_sha256"] and out["plan_sha256"] == plan["plan_sha256"], "Output hash/plan mismatch")
        a = pre[out["row_id"]]
        bid = digest(["blind", plan["plan_sha256"], out["row_id"], out["output_sha256"]])[:20]
        if bid in grouped:
            grouped[bid]["job_ids"].append(out["job_id"])
            continue
        tasks.append({"blind_id": bid, "caption": out["caption"], "output_sha256": out["output_sha256"],
                      "crop_filename": a["crop_filename"], "crop_sha256": a["crop_sha256"],
                      "baseline_claims": a["claims"]})
        mapping_row = {"blind_id": bid, "job_ids": [out["job_id"]], "row_id": out["row_id"]}
        keys.append(mapping_row); grouped[bid] = mapping_row
    tasks.sort(key=lambda t: digest(["review_order", t["blind_id"]]))
    task_file = cfg.study / "review_tasks.jsonl"
    key_file = cfg.study / "private" / "review_key.jsonl"
    if task_file.exists():
        require(load_jsonl(task_file) == tasks, "Review tasks are frozen; generation changed. Archive the prior review round before creating a new one.")
    else:
        save_jsonl(task_file, tasks); save_jsonl(key_file, keys)
        save_json(cfg.study / "review_task_receipt.json", {"tasks_sha256": sha_file(task_file), "key_sha256": sha_file(key_file),
            "source_outputs_sha256": sha_file(cfg.study / "outputs.jsonl"), "incomplete_generation_jobs": [r["job_id"] for r in missing],
            "conditions_hidden_from_review_ui": True, "baseline_claims_visible_for_transition_assessment": True,
            "identical_output_policy": "Identical output text for the same baseline row is reviewed once and mapped back to every condition/repeat"})
    path = cfg.study / "annotations" / f"post_{rater}.jsonl"
    if not path.exists():
        rows = []
        for t in tasks:
            rows.append({"blind_id": t["blind_id"], "caption": t["caption"], "output_sha256": t["output_sha256"],
                         "crop_filename": t["crop_filename"], "crop_sha256": t["crop_sha256"], "annotator_id": rater,
                         "review_complete": False, "claims_complete": False, "caption_usable": True,
                         "output_claims": [], "transitions": [{"baseline_claim_id": c["claim_id"], "status": "", "evidence": ""} for c in t["baseline_claims"]], "notes": ""})
        save_jsonl(path, rows)
    return {"review_file": str(path), "tasks": len(tasks), "incomplete_generation_jobs": len(missing), "status": "human review required"}

def validated_reviews(cfg, path):
    receipt = load_json(cfg.study / "review_task_receipt.json")
    for name, key in [("review_tasks.jsonl", "tasks_sha256"), ("private/review_key.jsonl", "key_sha256"), ("outputs.jsonl", "source_outputs_sha256")]:
        require(sha_file(cfg.study / name) == receipt[key], f"Review source changed: {name}")
    tasks = unique(load_jsonl(cfg.study / "review_tasks.jsonl"), "blind_id")
    mapping = unique(load_jsonl(cfg.study / "private/review_key.jsonl"), "blind_id")
    pre = unique(load_frozen_pre(cfg)["rows"], "row_id")
    reviews = unique(load_jsonl(path), "blind_id")
    require(set(reviews) == set(tasks), "Review must cover every task exactly once")
    for bid, a in reviews.items():
        validate_review(a, tasks[bid], pre[mapping[bid]["row_id"]])
    return reviews, mapping, pre

def claim_metrics(review, pre):
    transitions = {t["baseline_claim_id"]: t["status"] for t in review["transitions"]}
    false = [c for c in pre["claims"] if c["label"] == "contradicted"]
    true = [c for c in pre["claims"] if c["label"] == "supported"]
    out = review["output_claims"]
    def ratio(n, d): return n / d if d else None
    persisted = sum(transitions[c["claim_id"]] == "persisted" for c in false)
    unknown = sum(transitions[c["claim_id"]] == "unverifiable" for c in false)
    focal = transitions.get(pre.get("focal_claim_id"))
    return {
        "focal_error_persistence": None if focal in {None, "unverifiable"} else float(focal == "persisted"),
        "focal_persistence_lower": None if focal is None else float(focal == "persisted"),
        "focal_persistence_upper": None if focal is None else float(focal in {"persisted", "unverifiable"}),
        "focal_transition_unverifiable": None if focal is None else float(focal == "unverifiable"),
        "baseline_false_claims": len(false), "baseline_supported_claims": len(true),
        "false_persistence_lower": ratio(persisted, len(false)),
        "false_persistence_upper": ratio(persisted + unknown, len(false)),
        "explicit_correction_rate": ratio(sum(transitions[c["claim_id"]] == "corrected" for c in false), len(false)),
        "false_claim_omission_rate": ratio(sum(transitions[c["claim_id"]] == "omitted" for c in false), len(false)),
        "correct_claim_retention": ratio(sum(transitions[c["claim_id"]] == "retained" for c in true), len(true)),
        "correct_claim_corruption_rate": ratio(sum(transitions[c["claim_id"]] == "contradicted" for c in true), len(true)),
        "supported_transition_unverifiable": ratio(sum(transitions[c["claim_id"]] == "unverifiable" for c in true), len(true)),
        "new_false_claims": sum(c["origin"] in {"new", "correction"} and c["label"] == "contradicted" for c in out),
        "new_unverifiable_claims": sum(c["origin"] in {"new", "correction"} and c["label"] == "unverifiable" for c in out),
        "output_supported_claims": sum(c["label"] == "supported" for c in out),
        "output_contradicted_claims": sum(c["label"] == "contradicted" for c in out),
        "output_unverifiable_claims": sum(c["label"] == "unverifiable" for c in out),
        "output_claim_count": len(out), "output_word_count": len(review["caption"].split()),
        "caption_usable": int(review["caption_usable"]),
    }

def quantile(values, q):
    v = sorted(values); idx = (len(v) - 1) * q; lo = int(idx); hi = math.ceil(idx)
    return v[lo] * (hi - idx) + v[hi] * (idx - lo) if hi != lo else v[lo]

def paired_contrast(rows, condition_a, condition_b, metric, seed, bootstrap=2000):
    # B minus A, matched on exact row and repeat. Average repeats within each stimulus;
    # resample whole Phase 2 similarity groups. Never treat 3 decoder files as 3 subjects.
    by = {(r["row_id"], r["repeat"], r["condition"]): r for r in rows}
    row_deltas = collections.defaultdict(list); clusters = {}
    candidate_pairs = {(r["row_id"], r["repeat"]) for r in rows if r["condition"] in {condition_a, condition_b}}
    for rid, rep in sorted(candidate_pairs):
        a = by.get((rid, rep, condition_a)); b = by.get((rid, rep, condition_b))
        if a and b and a.get(metric) is not None and b.get(metric) is not None:
            row_deltas[rid].append(b[metric] - a[metric]); clusters[rid] = a["cluster_id"]
    grouped = collections.defaultdict(list)
    for rid, vals in row_deltas.items():
        grouped[clusters[rid]].append(sum(vals) / len(vals))
    result = {"contrast": f"{condition_b} minus {condition_a}", "metric": metric,
              "paired_stimulus_rows": len(row_deltas), "independent_similarity_clusters": len(grouped),
              "paired_replicates": sum(map(len, row_deltas.values())), "mean_difference": None, "ci95": None,
              "interpretation": "exploratory pilot estimate; no confirmatory inference"}
    if not row_deltas:
        result["reason"] = "No complete, adjudicable pairs for this metric"
        return result
    values = [v for group in grouped.values() for v in group]
    result["mean_difference"] = sum(values) / len(values)
    if len(grouped) < 5:
        result["reason"] = "Fewer than 5 independent clusters; interval withheld"
        return result
    rng = random.Random(seed); keys = sorted(grouped); boot = []
    for _ in range(bootstrap):
        sample = [v for _ in keys for v in grouped[rng.choice(keys)]]
        boot.append(sum(sample) / len(sample))
    result["ci95"] = [quantile(boot, .025), quantile(boot, .975)]
    return result

def evaluate(cfg, review_path, bootstrap=2000):
    require(100 <= bootstrap <= 10000, "Use 100–10000 bootstrap replicates")
    plan = load_plan(cfg); reviews, mapping, pre = validated_reviews(cfg, review_path)
    outputs = unique(load_jsonl(cfg.study / "outputs.jsonl"), "job_id")
    rows = []; baseline_issues = []
    for bid, review in reviews.items():
        for job_id in mapping[bid]["job_ids"]:
            out = outputs[job_id]
            if out["condition"] == "decoded":
                truth = {c["claim_id"]: c["label"] for c in pre[out["row_id"]]["claims"]}
                expected = {"supported": {"retained"}, "contradicted": {"persisted"}, "unverifiable": {"retained", "unverifiable"}}
                for transition in review["transitions"]:
                    if transition["status"] not in expected[truth[transition["baseline_claim_id"]]]:
                        baseline_issues.append({"blind_id": bid, "row_id": out["row_id"], "claim_id": transition["baseline_claim_id"], "transition": transition["status"]})
            rows.append({k: out[k] for k in ["job_id", "row_id", "decoder", "condition", "repeat", "coco_image_id", "cluster_id"]} |
                        claim_metrics(review, pre[out["row_id"]]))
    if baseline_issues:
        save_json(cfg.study / "evaluation" / "baseline_annotation_disagreements.json", baseline_issues)
        save_json(cfg.study / "evaluation" / "pilot_summary.json", {
            "status": "blocked_baseline_annotation_disagreement", "review_sha256": sha_file(review_path),
            "issues_file": "baseline_annotation_disagreements.json", "older_row_metric_files_are_not_current": True})
        require(False, "Unchanged-baseline review disagrees with frozen input truth. Adjudicate the evidence; do not force labels to agree. Analysis is blocked until resolved.")
    metrics = [k for k in rows[0] if k not in {"job_id", "row_id", "decoder", "condition", "repeat", "coco_image_id", "cluster_id"}] if rows else []
    per_condition = []
    for decoder in cfg.raw["decoders"]:
        for condition in plan["conditions"]:
            selected = [r for r in rows if r["decoder"] == decoder and r["condition"] == condition]
            if not selected:
                continue
            entry = {"decoder": decoder, "condition": condition, "reviewed_outputs": len(selected), "metrics": {}}
            for metric in metrics:
                by_row = collections.defaultdict(list)
                for r in selected:
                    if r[metric] is not None:
                        by_row[r["row_id"]].append(r[metric])
                vals = [sum(v) / len(v) for v in by_row.values()]
                entry["metrics"][metric] = {"mean_over_stimuli": sum(vals) / len(vals) if vals else None, "stimuli_with_defined_metric": len(vals)}
            per_condition.append(entry)
    contrasts = []
    pairs = [("rewrite_only", "rag_original"), ("rag_original", "rag_query_repaired"),
             ("rag_original", "random_context"), ("rag_original", "rag_caption_repaired"),
             ("rag_query_repaired", "rag_both_repaired")]
    contrast_metrics = ["focal_error_persistence", "focal_persistence_lower", "focal_persistence_upper",
                        "false_persistence_lower", "explicit_correction_rate", "false_claim_omission_rate",
                        "correct_claim_retention", "new_false_claims", "new_unverifiable_claims", "output_word_count"]
    for decoder in cfg.raw["decoders"]:
        for a, b in pairs:
            for metric in contrast_metrics:
                result = paired_contrast([r for r in rows if r["decoder"] == decoder], a, b, metric,
                                         stable_int(cfg.raw["run_seed"], decoder, a, b, metric), bootstrap)
                contrasts.append(dict(result, decoder=decoder))
    report = {"scope": "Phase 3 pilot only; no scientific conclusion is generated", "plan_sha256": plan["plan_sha256"],
              "review_sha256": sha_file(review_path), "raters_in_file": sorted({r["annotator_id"] for r in reviews.values()}),
              "planned_outputs": len(plan["jobs"]), "reviewed_outputs": len(rows),
              "generation_status_counts": dict(collections.Counter(o["status"] for o in outputs.values())),
              "diagnostic_focal_error_rows": sum(a["diagnostic_eligible"] for a in pre.values()),
              "per_condition": per_condition, "paired_contrasts": contrasts,
              "warnings": ["Single-subject cached benchmark", "Oracle repairs use privileged visual information",
                           "Unverifiable claims are not automatically false", "Omission is distinct from explicit correction",
                           "Intervals are exploratory; complete-case comparisons can be affected by attrition",
                           "All rates retain their explicit stimulus/claim denominators; repeated generations are not independent stimuli"]}
    outdir = cfg.study / "evaluation"; outdir.mkdir(exist_ok=True)
    save_json(outdir / "pilot_summary.json", report); save_jsonl(outdir / "row_metrics.jsonl", rows)
    if rows:
        with (outdir / "row_metrics.csv").open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    return {"summary": str(outdir / "pilot_summary.json"), "reviewed_outputs": len(rows), "diagnostic_focal_error_rows": report["diagnostic_focal_error_rows"]}

def compare_reviewers(cfg, path_a, path_b):
    a, _, _ = validated_reviews(cfg, path_a); b, _, _ = validated_reviews(cfg, path_b)
    require(set(a) == set(b), "Rater task sets differ")
    labels_a = []; labels_b = []; disagreements = []
    for bid in sorted(a):
        ta = {t["baseline_claim_id"]: t["status"] for t in a[bid]["transitions"]}
        tb = {t["baseline_claim_id"]: t["status"] for t in b[bid]["transitions"]}
        require(set(ta) == set(tb), "Raters must assess the same predeclared baseline claims")
        for cid in sorted(ta):
            labels_a.append(ta[cid]); labels_b.append(tb[cid])
            if ta[cid] != tb[cid]:
                disagreements.append({"blind_id": bid, "baseline_claim_id": cid, "rater_a": ta[cid], "rater_b": tb[cid]})
    n = len(labels_a); ca = collections.Counter(labels_a); cb = collections.Counter(labels_b)
    observed = sum(x == y for x, y in zip(labels_a, labels_b)) / n if n else None
    chance = sum(ca[k] * cb[k] for k in ca.keys() | cb.keys()) / n**2 if n else None
    kappa = (observed - chance) / (1 - chance) if chance is not None and chance < 1 else None
    result = {"transition_decisions": n, "raw_agreement": observed, "cohen_kappa": kappa,
              "disagreements": disagreements, "scope": "Baseline-claim transitions only; independently segmented output claims are not presumed aligned"}
    save_json(cfg.study / "evaluation" / "rater_agreement.json", result)
    return {k: v for k, v in result.items() if k != "disagreements"}
