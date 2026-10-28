"""CPU-only retrieval diagnostic. No decoded-caption labels or model calls.

Queries are held-out captions from ELIGIBLE DONOR images, not NSD test images.
Their remaining captions define a same-image retrieval proxy, not visual truth.
"""
from __future__ import annotations
import collections
import math
import re
import sqlite3
import tempfile
import time
from pathlib import Path
from .assets import read_ids
from .common import canonical, digest, load_jsonl, require, runtime_info, save_json, save_jsonl, sha_bytes
from .planning import source_code_hash
from .retrieval import match_query, validate_index
from .tokenization import Tokenizer

MODES = ("whole_caption", "whole_caption_metadata", "split_8_words", "image_bundle")

def normalized(text):
    return " ".join(text.lower().split())

def make_units(documents, mode):
    require(mode in MODES, "Unknown audit representation")
    docs = sorted(documents, key=lambda d: (d["image_id"], d["caption_id"]))
    units = []
    def add(image, text, ids, spans):
        units.append({"unit_id": len(units) + 1, "image_id": image, "text": text,
                      "source_caption_ids": ids, "source_spans": spans,
                      "text_sha256": sha_bytes(text.encode("utf-8"))})
    if mode == "image_bundle":
        grouped = collections.defaultdict(list)
        for d in docs:
            grouped[d["image_id"]].append(d)
        for iid, group in sorted(grouped.items()):
            add(iid, "\n".join(d["text"] for d in group), [d["caption_id"] for d in group],
                [{"caption_id": d["caption_id"], "start": 0, "end": len(d["text"])} for d in group])
    else:
        for d in docs:
            spans = [(0, len(d["text"]))]
            if mode == "split_8_words":
                words = list(re.finditer(r"\S+", d["text"]))
                spans = [(words[i].start(), words[min(i+8, len(words))-1].end()) for i in range(0, len(words), 8)]
            for start, end in spans:
                add(d["image_id"], d["text"][start:end], [d["caption_id"]],
                    [{"caption_id": d["caption_id"], "start": start, "end": end}])
    return units

def donor_split(documents, query_images, seed):
    grouped = collections.defaultdict(list)
    for d in documents:
        grouped[d["image_id"]].append(d)
    chosen = sorted(grouped, key=lambda i: digest([seed, "query_image", i]))[:query_images]
    proposed = [min(grouped[i], key=lambda d: digest([seed, "query_caption", d["caption_id"]])) for i in chosen]
    withheld_texts = {normalized(d["text"]) for d in proposed}
    withheld_ids = {d["caption_id"] for d in proposed}
    kept = [d for d in documents if d["caption_id"] not in withheld_ids and normalized(d["text"]) not in withheld_texts]
    represented = {d["image_id"] for d in kept}
    queries = [q for q in proposed if q["image_id"] in represented and match_query(q["text"])]
    exclusions = [{"caption_id": q["caption_id"], "image_id": q["image_id"],
                   "reason": "no_remaining_nonidentical_caption_or_no_query_terms"} for q in proposed if q not in queries]
    return kept, queries, exclusions, withheld_ids, withheld_texts

def rank_units(units, queries, mode, tokenizer, db_path):
    started = time.perf_counter()
    con = sqlite3.connect(db_path)
    try:
        con.execute("CREATE TABLE units(unit_id INTEGER PRIMARY KEY,image_id INTEGER,text TEXT,metadata TEXT)")
        for u in units:
            meta = canonical({k: u[k] for k in ("image_id", "source_caption_ids", "source_spans", "text_sha256")})
            con.execute("INSERT INTO units VALUES (?,?,?,?)", (u["unit_id"], u["image_id"], u["text"], meta))
        fields = "text,metadata UNINDEXED" if mode == "whole_caption_metadata" else "text"
        con.execute(f"CREATE VIRTUAL TABLE fts USING fts5({fields},content='units',content_rowid='unit_id',tokenize='porter unicode61')")
        con.execute("INSERT INTO fts(fts) VALUES ('rebuild')")
        con.execute("INSERT INTO fts(fts,rank) VALUES ('integrity-check',1)")
        con.commit()
        build_seconds = time.perf_counter() - started
        by_id = {u["unit_id"]: u for u in units}; output = []; latencies = []
        for q in queries:
            before = time.perf_counter()
            # Complete ranking, then identical parent/text deduplication for every mode.
            cursor = con.execute("SELECT u.unit_id,u.image_id,u.text,bm25(fts) AS score FROM fts JOIN units u ON u.unit_id=fts.rowid WHERE fts MATCH ? ORDER BY score ASC,u.unit_id ASC", (match_query(q["text"]),))
            selected = []; images = set(); texts = set()
            for uid, iid, text, score in cursor:
                norm = normalized(text)
                if iid in images or norm in texts:
                    continue
                images.add(iid); texts.add(norm)
                selected.append(dict(by_id[uid], score=score))
                if len(selected) == 10:
                    break
            cursor.close(); latencies.append(time.perf_counter() - before)
            ids = [u["image_id"] for u in selected]
            rank = ids.index(q["image_id"]) + 1 if q["image_id"] in ids else None
            output.append({"representation": mode, "query_caption_id": q["caption_id"], "query_image_id": q["image_id"],
                "rank_at_10": rank, "reciprocal_rank_at_10": 1/rank if rank else 0,
                "hits_at_1": int(rank is not None and rank <= 1), "hits_at_3": int(rank is not None and rank <= 3),
                "hits_at_10": int(rank is not None),
                "top3_raw_context_tokens": tokenizer.count("\n".join("Example %d: %s" % (i+1, " ".join(u["text"].split())) for i,u in enumerate(selected[:3]))),
                "ranking": [{k:u[k] for k in ("unit_id", "image_id", "source_caption_ids", "text_sha256", "score")} for u in selected]})
        summary = {"representation": mode, "indexed_units": len(units), "queries": len(queries),
            "build_seconds": build_seconds, "mean_query_seconds": sum(latencies)/len(latencies) if latencies else None}
        for metric in ("hits_at_1", "hits_at_3", "hits_at_10", "reciprocal_rank_at_10", "top3_raw_context_tokens"):
            summary[metric] = sum(r[metric] for r in output)/len(output) if output else None
        return summary, output
    finally:
        con.close()

def length_summary(histogram):
    n = sum(histogram.values())
    def percentile(q):
        target = max(1, math.ceil(n*q)); total = 0
        for length, count in sorted(histogram.items()):
            total += count
            if total >= target:
                return length
    return {"captions": n, "mean": sum(k*v for k,v in histogram.items())/n if n else None,
            "p50": percentile(.5), "p95": percentile(.95), "p99": percentile(.99),
            "max": max(histogram) if histogram else None,
            "fraction_at_most_32_tokens": sum(v for k,v in histogram.items() if k<=32)/n if n else None}

def run_audit(cfg, output_dir, candidate_images=10000, query_images=100, seed=20261028):
    implementation_sha = source_code_hash()
    require(type(candidate_images) is int and 10 <= candidate_images <= 20000, "Use 10–20000 donor candidate images")
    require(type(query_images) is int and 1 <= query_images <= min(200, candidate_images), "Use 1–200 donor query images")
    out = Path(output_dir).resolve()
    require(not out.exists() or not any(out.iterdir()), "Audit output directory is not empty; choose a new output path")
    index = validate_index(cfg)
    eligible = read_ids(cfg.phase2/'results/eligible_coco_image_ids.txt')
    excluded = {r['coco_image_id'] for r in load_jsonl(cfg.phase2/'results/retrieval_exclusions.jsonl')}
    require(not eligible & excluded, "Excluded images reached donor diagnostic")
    selected = set(sorted(eligible, key=lambda i: digest([seed, "candidate_image", i]))[:candidate_images])
    tokenizer = Tokenizer(cache_dir=cfg.work/'tokenizer_cache')
    docs = []; histogram = collections.Counter(); all_images = set()
    with sqlite3.connect((cfg.work/'corpus.sqlite3').resolve().as_uri()+'?mode=ro', uri=True) as con:
        for cid, iid, text in con.execute('SELECT caption_id,image_id,text FROM documents ORDER BY caption_id'):
            require(iid in eligible and iid not in excluded, "Ineligible donor in diagnostic")
            histogram[tokenizer.count(text)] += 1; all_images.add(iid)
            if iid in selected:
                docs.append({'caption_id': cid, 'image_id': iid, 'text': text})
    kept, queries, dropped, withheld_ids, withheld_texts = donor_split(docs, query_images, seed)
    require(queries, "No usable held-out donor queries; report exclusions rather than fabricate labels")
    require(not any(d['caption_id'] in withheld_ids or normalized(d['text']) in withheld_texts for d in kept), "Query annotation leakage into donor diagnostic")
    out.mkdir(parents=True, exist_ok=True)
    results = []; rankings = []; metadata_exact = None; reference = None
    with tempfile.TemporaryDirectory(prefix='indexes_', dir=out) as temp:
        for mode in MODES:
            units = make_units(kept, mode)
            require(all(u['image_id'] in selected and not set(u['source_caption_ids']) & withheld_ids for u in units), "Chunk provenance/leakage failure")
            summary, rows = rank_units(units, queries, mode, tokenizer, Path(temp)/(mode+'.sqlite3'))
            signature = [{k:v for k,v in r.items() if k != 'representation'} for r in rows]
            if mode == 'whole_caption':
                reference = signature
            if mode == 'whole_caption_metadata':
                metadata_exact = signature == reference
                require(metadata_exact, "Unindexed metadata unexpectedly changed rankings or scores")
            results.append(summary); rankings.extend(rows)
    report = {'scope':'Offline donor-caption retrieval proxy; not a brain-caption factuality experiment',
        'seed':seed, 'candidate_images_requested':candidate_images, 'candidate_images_after_holdout':len({d['image_id'] for d in kept}),
        'candidate_captions_before_holdout':len(docs), 'candidate_captions_after_holdout':len(kept),
        'query_images_requested':query_images, 'queries_evaluated':len(queries), 'excluded_queries':dropped,
        'corpus_caption_length_tokens':length_summary(histogram), 'tokenizer':'o200k_base',
        'metadata_rankings_and_scores_identical':metadata_exact,
        'source_index_sha256':index['database_sha256'], 'source_annotation_zip_sha256':index['source_annotation_zip_sha256'],
        'eligibility_files':index['eligibility_files'], 'runtime':runtime_info(),
        'source_code_sha256':implementation_sha,
        'candidate_image_ids':sorted(selected), 'query_caption_ids':[q['caption_id'] for q in queries],
        'candidate_rows_sha256':digest(kept), 'api_calls':0, 'results':results,
        'limitations':['Caption-to-caption same-image proxy, not decoded-caption retrieval relevance or visual factuality',
                       'Sampled donor corpus, not the full candidate pool in the production pilot',
                       'Image bundles expose more text and alter BM25 document lengths; not a token-matched generation comparison',
                       'Short fragment chunks are an explicit ablation, not a recommended new default',
                       'Timings are environment-specific observations, not a Windows benchmark']}
    save_json(out/'audit_report.json',report);save_jsonl(out/'rankings.jsonl',rankings)
    save_jsonl(out/'queries.jsonl',queries)
    return {'report':str(out/'audit_report.json'), 'queries_evaluated':len(queries), 'metadata_rankings_and_scores_identical':metadata_exact,
            'corpus_caption_length_tokens':report['corpus_caption_length_tokens'], 'results':results, 'api_calls':0}
