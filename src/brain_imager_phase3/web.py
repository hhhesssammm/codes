"""Localhost-only human annotation UI; no cloud API calls."""
from __future__ import annotations
import json
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse, unquote
from .annotations import crop_registry, validate_pre_record, validate_review, load_frozen_pre
from .common import AuditError, load_jsonl, require, save_jsonl, unique
from .selection import pilot_rows

def make_server(cfg, mode, annotation_file, port=8765):
    require(mode in {"pre", "post"}, "Choose pre or post annotation")
    records = load_jsonl(annotation_file)
    crops = crop_registry(cfg)
    if mode == "pre":
        source = {r["manifest_row_id"]: r for r in pilot_rows(cfg)}
        tasks = None; pre = None; mapping = None; key = "row_id"
        require(set(unique(records, key)) == set(source), "Pre-annotation file does not match pilot")
    else:
        tasks = unique(load_jsonl(cfg.study / "review_tasks.jsonl"), "blind_id")
        mapping = unique(load_jsonl(cfg.study / "private/review_key.jsonl"), "blind_id")
        pre = unique(load_frozen_pre(cfg)["rows"], "row_id")
        source = None; key = "blind_id"
        require(set(unique(records, key)) == set(tasks), "Review file does not match blinded tasks")
    allowed_images = {r["filename"] for r in crops.values()}
    token = secrets.token_urlsafe(24); lock = threading.Lock()
    page = (Path(__file__).parent / "web_ui.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Do not log session URLs or annotation contents.

        def authorize(self):
            supplied = parse_qs(urlparse(self.path).query).get("token", [""])[0] or self.headers.get("X-Session-Token", "")
            return secrets.compare_digest(supplied, token)

        def send(self, code, body, content_type="application/json; charset=utf-8"):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code); self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff"); self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            if not self.authorize():
                return self.send(403, {"error": "Open the exact local URL printed by the annotation command"})
            path = unquote(urlparse(self.path).path)
            if path == "/":
                return self.send(200, page, "text/html; charset=utf-8")
            if path == "/api/state":
                with lock:
                    current = load_jsonl(annotation_file)
                return self.send(200, {"mode": mode, "records": current, "tasks": tasks})
            if path.startswith("/crop/"):
                name = path[len("/crop/"):]
                if name not in allowed_images or Path(name).name != name:
                    return self.send(404, {"error": "Unknown crop"})
                return self.send(200, (cfg.work / "crops" / name).read_bytes(), "image/png")
            return self.send(404, {"error": "Not found"})

        def do_POST(self):
            if not self.authorize() or urlparse(self.path).path != "/api/save":
                return self.send(403, {"error": "Forbidden"})
            origin = self.headers.get("Origin")
            if origin and origin != f"http://127.0.0.1:{self.server.server_port}":
                return self.send(403, {"error": "Only this local annotation page may save"})
            try:
                n = int(self.headers.get("Content-Length", "0"))
                require(0 < n <= 1000000, "Invalid request size")
                data = json.loads(self.rfile.read(n)); new = data["record"]
                with lock:
                    rows = load_jsonl(annotation_file); by = unique(rows, key)
                    require(new[key] in by, "Unknown annotation identity")
                    old = by[new[key]]
                    for field in [key, "caption", "caption_sha256" if mode == "pre" else "output_sha256", "crop_filename", "crop_sha256"]:
                        require(new[field] == old[field], f"Immutable field changed: {field}")
                    if new.get("review_complete"):
                        if mode == "pre":
                            r = source[new[key]]; validate_pre_record(new, r, crops[r["coco_image_id"]])
                        else:
                            validate_review(new, tasks[new[key]], pre[mapping[new[key]]["row_id"]])
                    save_jsonl(annotation_file, [new if r[key] == new[key] else r for r in rows])
                return self.send(200, {"saved": True})
            except (AuditError, KeyError, TypeError, ValueError) as exc:
                return self.send(400, {"error": str(exc)})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    return server, f"http://127.0.0.1:{server.server_port}/?token={token}"

def serve(cfg, mode, annotation_file, port=8765, open_browser=True):
    server, url = make_server(cfg, mode, annotation_file, port)
    print(f"Local annotation interface: {url}\nEdits save only on this laptop. Press Ctrl+C to stop.", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

