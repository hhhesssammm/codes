import os
import shutil
from pathlib import Path
from .common import require

class Tokenizer:
    def __init__(self, name="o200k_base", cache_dir: Path | None = None):
        bundled = Path(__file__).resolve().parents[2] / "assets" / "tokenizer_cache"
        if cache_dir is None and bundled.is_dir():
            cache_dir = bundled
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)
            if bundled.is_dir() and bundled.resolve() != cache_dir.resolve():
                for item in bundled.iterdir():
                    if item.is_file() and not (cache_dir / item.name).exists():
                        shutil.copyfile(item, cache_dir / item.name)
            os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(cache_dir))
        import tiktoken
        self.enc = tiktoken.get_encoding(name)
        self.name = name

    def encode(self, text):
        return self.enc.encode(text, disallowed_special=())

    def count(self, text):
        return len(self.encode(text))

    def clip(self, text, limit):
        ids = self.encode(text)[:limit]
        while ids:
            try:
                out = b"".join(self.enc.decode_single_token_bytes(i) for i in ids).decode("utf-8")
                if self.count(out) <= limit:
                    return out
            except UnicodeDecodeError:
                pass
            ids.pop()
        return ""

    def matched(self, texts, budget):
        target = min([budget] + [self.count(t) for t in texts])
        while target > 0:
            clipped = [self.clip(t, target) for t in texts]
            counts = [self.count(t) for t in clipped]
            if len(set(counts)) == 1:
                return clipped
            target = min(counts)
        return ["" for _ in texts]
