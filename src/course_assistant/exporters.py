"""UTF-8 file contracts: one parse tree per input line, atomic writes."""
from pathlib import Path
from tempfile import NamedTemporaryFile
import json
import os


def write_lines(path, lines):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            for line in lines:
                stream.write(line.rstrip("\n") + "\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def write_json(path, value):
    write_lines(path, [json.dumps(value, ensure_ascii=False, indent=2)])


def write_jsonl(path, values):
    write_lines(path, (json.dumps(value, ensure_ascii=False) for value in values))


def read_sentences(path):
    # Empty interior lines are actual input and must receive ().
    return Path(path).read_text(encoding="utf-8-sig").splitlines()


def export_parse_results(results, output_dir):
    destination = Path(output_dir)
    write_lines(destination / "parse-results.txt", (r["parse_tree"] for r in results))
    write_jsonl(destination / "parser-api.jsonl", results)
    write_jsonl(destination / "semantic.jsonl", (
        {"sentence": r["sentence"], "status": r["status"], "semantic_frame": r.get("semantic_frame")}
        for r in results))
    write_jsonl(destination / "query.jsonl", (
        {"sentence": r["sentence"], "status": r["status"], "query": r.get("query")}
        for r in results))
