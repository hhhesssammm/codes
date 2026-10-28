"""CPU-only, image-deduplicated SQLite FTS5 BM25 retrieval."""
from __future__ import annotations
import collections
import json
import random
import re
import sqlite3
import zipfile
from pathlib import Path
from .assets import read_ids, validate_phase2
from .common import load_json, load_jsonl, require, save_json, sha_file, digest

STOP = set("a an the is are was were be been being this that these those it its there and or of".split())

def match_query(text: str) -> str:
    words = list(dict.fromkeys(w.lower() for w in re.findall(r"\w+", text, flags=re.UNICODE) if w.lower() not in STOP))
    return " OR ".join('"' + w + '"' for w in words[:80])

def build_index(cfg):
    validate_phase2(cfg)
    asset = next(a for a in load_json(cfg.phase2 / "frozen_assets.json") if a["id"] == "coco_annotations")
    source = cfg.work / "downloads" / asset["filename"]
    require(sha_file(source) == asset["sha256"], "COCO annotation ZIP failed the Phase 2 hash")
    eligible = read_ids(cfg.phase2 / "results/eligible_coco_image_ids.txt")
    eligible_caps = read_ids(cfg.phase2 / "results/eligible_coco_caption_ids.txt")
    excluded = {r["coco_image_id"] for r in load_jsonl(cfg.phase2 / "results/retrieval_exclusions.jsonl")}
    db = cfg.work / "corpus.sqlite3"
    if db.exists():
        return validate_index(cfg)
    tmp = db.with_suffix(".building")
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(tmp)
    try:
        conn.execute("CREATE TABLE documents(caption_id INTEGER PRIMARY KEY, image_id INTEGER NOT NULL, text TEXT NOT NULL)")
        conn.execute("CREATE INDEX document_image ON documents(image_id)")
        conn.execute("CREATE VIRTUAL TABLE fts USING fts5(text, content='documents', content_rowid='caption_id', tokenize='porter unicode61')")
        seen_ids = set(); seen_images = set(); batch = []
        with zipfile.ZipFile(source) as z:
            for split in ["train2017", "val2017"]:
                member = f"annotations/captions_{split}.json"
                annotations = json.loads(z.read(member))["annotations"]
                for a in annotations:
                    if a["image_id"] not in eligible:
                        continue
                    require(a["image_id"] not in excluded, "Excluded image reached indexing")
                    require(a["id"] in eligible_caps and a["id"] not in seen_ids, "Caption eligibility/uniqueness mismatch")
                    require(isinstance(a["caption"], str) and a["caption"].strip(), "Empty COCO caption")
                    seen_ids.add(a["id"]); seen_images.add(a["image_id"])
                    batch.append((a["id"], a["image_id"], a["caption"]))
                    if len(batch) >= 10000:
                        conn.executemany("INSERT INTO documents VALUES (?,?,?)", batch); batch.clear()
                del annotations
        conn.executemany("INSERT INTO documents VALUES (?,?,?)", batch)
        require(seen_ids == eligible_caps and seen_images == eligible, "Corpus build did not reproduce every approved eligible identity")
        conn.execute("INSERT INTO fts(fts) VALUES ('rebuild')")
        conn.execute("INSERT INTO fts(fts) VALUES ('integrity-check')")
        conn.commit()
        require(conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "SQLite integrity failure")
    finally:
        conn.close()
    tmp.replace(db)
    manifest = {"schema_version": 1, "database_sha256": sha_file(db),
                "source_annotation_zip_sha256": asset["sha256"], "caption_count": len(seen_ids),
                "image_count": len(seen_images), "excluded_images": len(excluded),
                "retriever": "SQLite FTS5 BM25; porter unicode61; ascending score then caption_id",
                "sqlite_version": sqlite3.sqlite_version,
                "eligibility_files": {n: sha_file(cfg.phase2 / "results" / n) for n in ["eligible_coco_image_ids.txt", "eligible_coco_caption_ids.txt", "retrieval_exclusions.jsonl"]}}
    save_json(cfg.work / "corpus_manifest.json", manifest)
    return manifest

def validate_index(cfg):
    validate_phase2(cfg)
    m = load_json(cfg.work / "corpus_manifest.json")
    require(sha_file(cfg.work / "corpus.sqlite3") == m["database_sha256"], "Retrieval database changed after sealing")
    for name, h in m["eligibility_files"].items():
        require(sha_file(cfg.phase2 / "results" / name) == h, "Index used different eligibility files")
    with sqlite3.connect((cfg.work / "corpus.sqlite3").resolve().as_uri() + "?mode=ro", uri=True) as con:
        n, images = con.execute("SELECT count(*), count(DISTINCT image_id) FROM documents").fetchone()
    require((n, images) == (611349, 122204), "Indexed corpus counts differ from the approved pool")
    return m

class Retriever:
    def __init__(self, db: Path, eligible_images: set[int], excluded_images: set[int]):
        self.conn = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row
        self.eligible = eligible_images
        self.excluded = excluded_images
        self.ids = [r[0] for r in self.conn.execute("SELECT caption_id FROM documents ORDER BY caption_id")]

    def close(self):
        self.conn.close()

    def check(self, doc):
        require(doc["image_id"] in self.eligible and doc["image_id"] not in self.excluded, "Retrieval leakage detected")

    def search(self, query: str, top_k: int) -> list[dict]:
        q = match_query(query)
        if not q:
            return []
        rows = self.conn.execute("SELECT d.caption_id,d.image_id,d.text,bm25(fts) AS score FROM fts JOIN documents d ON d.caption_id=fts.rowid WHERE fts MATCH ? ORDER BY score ASC,d.caption_id ASC LIMIT ?", (q, max(100, top_k * 100)))
        chosen = []; image_seen = set(); text_seen = set()
        for r in rows:
            doc = dict(r); self.check(doc)
            norm = " ".join(doc["text"].lower().split())
            if doc["image_id"] in image_seen or norm in text_seen:
                continue
            chosen.append(doc); image_seen.add(doc["image_id"]); text_seen.add(norm)
            if len(chosen) == top_k:
                break
        return chosen

    def random_context(self, top_k, rng: random.Random, minimum_tokens, tokenizer):
        # Rejection sampling conditional on context length; no target truth enters here.
        if top_k == 0 or minimum_tokens == 0:
            return []
        for _ in range(1000):
            docs = []; images = set(); texts = set()
            for cid in rng.sample(self.ids, min(len(self.ids), top_k * 8)):
                doc = dict(self.conn.execute("SELECT caption_id,image_id,text FROM documents WHERE caption_id=?", (cid,)).fetchone())
                self.check(doc)
                norm = " ".join(doc["text"].lower().split())
                if doc["image_id"] in images or norm in texts:
                    continue
                doc["score"] = None; docs.append(doc); images.add(doc["image_id"]); texts.add(norm)
                if len(docs) == top_k:
                    break
            if len(docs) == top_k and tokenizer.count(render_context(docs)[0]) >= minimum_tokens:
                return docs
        raise ValueError("Could not construct a length-matched random context; reduce context budget before freezing a new pilot plan")

def render_context(docs):
    text = ""; spans = []
    for i, doc in enumerate(docs, 1):
        text += ("\n" if text else "") + f"Example {i}: "
        start = len(text); clean = " ".join(doc["text"].split())
        text += clean
        spans.append(dict(caption_id=doc["caption_id"], image_id=doc["image_id"], start=start, end=len(text)))
    return text, spans

