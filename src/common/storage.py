from pathlib import Path
import json


def ensure_dir(path: str | Path):
    Path(path).mkdir(parents=True, exist_ok=True)


def save_text_file(path: str | Path, content: str):
    path = Path(path)
    ensure_dir(path.parent)
    path.write_text(content or "", encoding="utf-8")


def save_json_file(path: str | Path, data: dict):
    path = Path(path)
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: str | Path, record: dict):
    path = Path(path)
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
