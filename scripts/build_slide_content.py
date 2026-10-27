"""Build clean lecture knowledge and separate source-provenance records.

No OCR, external API, or automatic summarization. The Vietnamese summaries are
explicitly curated; this script attaches verifiable text evidence and sources.
Python standard library suffices for PPTX; chapter 4's legacy PPT needs olefile.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import struct
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

PROJECT = Path(__file__).resolve().parents[1]
DEST = PROJECT / "data" / "slide_content"
NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def pptx_text(path: Path) -> list[str]:
    """Follow presentation relationships, not lexical slide filename order."""
    with ZipFile(path) as z:
        rels = ET.fromstring(z.read("ppt/_rels/presentation.xml.rels"))
        targets = {r.attrib["Id"]: r.attrib["Target"] for r in rels}
        pres = ET.fromstring(z.read("ppt/presentation.xml"))
        result = []
        for slide in pres.findall("p:sldIdLst/p:sldId", NS):
            target = targets[slide.attrib[f"{{{NS['r']}}}id"]]
            name = (target.lstrip("/") if target.startswith("/")
                    else posixpath.normpath(posixpath.join("ppt", target)))
            root = ET.fromstring(z.read(name))
            paragraphs = ["".join(t.text or "" for t in p.findall(".//a:t", NS))
                          for p in root.findall(".//a:p", NS)]
            result.append("\n".join(p for p in paragraphs if p.strip()))
        return result


def legacy_text(path: Path) -> list[str]:
    """Read text atoms; IDs locate blocks, never imply slide numbers."""
    try:
        import olefile
    except ImportError as exc:
        raise SystemExit("Chapter 4 needs olefile: python -m pip install olefile") from exc
    with olefile.OleFileIO(path) as ole:
        data = ole.openstream("PowerPoint Document").read()
    cursor = 0
    blocks = []
    while cursor + 8 <= len(data):
        version, record_type, size = struct.unpack_from("<HHI", data, cursor)
        if size > len(data) - cursor - 8:
            cursor += 1
            continue
        if record_type in (4000, 4008):
            encoding = "utf-16-le" if record_type == 4000 else "cp1252"
            blocks.append(data[cursor + 8:cursor + 8 + size]
                          .decode(encoding, errors="replace").replace("\r", "\n"))
        cursor += 8 if version & 15 == 15 else 8 + size
    return list(dict.fromkeys(blocks))


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def text_record(card: dict) -> str:
    """Plain-text, YAML-compatible record with exactly the JSONL knowledge fields.

    Emit strings with JSON quoting (valid YAML) so punctuation cannot change types.
    Keep explanations as readable block text; curation paragraphs have no newlines.
    No YAML package is needed to build the dataset.
    """
    lines = ["---"]
    for key, value in card.items():
        if key == "content_vi":
            assert "\n" not in value and "\r" not in value
            lines.extend(["content_vi: |-", "  " + value])
        else:
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def build(source_dir: Path) -> dict[Path, str]:
    seeds = json.loads((DEST / "curation.json").read_text(encoding="utf-8"))["items"]
    assert len({(r[0], r[1]) for r in seeds}) == len(seeds), "Duplicate IDs"
    assert set(r[0] for r in seeds) == set(range(1, 12)), "Missing chapter"
    outputs = {}
    sources = []
    provenance = []
    total = 0
    for chapter in range(1, 12):
        matches = [p for p in source_dir.iterdir()
                   if p.stem.lower() == f"chapter {chapter}" and p.suffix.lower() in (".pptx", ".ppt")]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one source for chapter {chapter}: {matches}")
        source = matches[0]
        is_legacy = source.suffix.lower() == ".ppt"
        texts = legacy_text(source) if is_legacy else pptx_text(source)
        checksum = hashlib.sha256(source.read_bytes()).hexdigest()
        source_ref = source.relative_to(PROJECT.parents[1]).as_posix() if source.is_relative_to(PROJECT.parents[1]) else str(source)
        sources.append({"chapter": chapter, "path": source_ref, "sha256": checksum,
                        "slide_count": None if is_legacy else len(texts),
                        "text_block_count": len(texts) if is_legacy else None})
        cards = []
        for ch, key, title, refs, keywords, content in seeds:
            if ch != chapter:
                continue
            assert refs and len(set(refs)) == len(refs)
            assert title.strip() and content.strip() and keywords
            evidence = []
            for ref in refs:
                index = ref if is_legacy else ref - 1
                assert 0 <= index < len(texts), (chapter, ref)
                original = texts[index]
                assert original.strip(), (chapter, ref, "empty evidence")
                evidence.append({"legacy_text_block" if is_legacy else "slide": ref,
                                 "text": original})
            limits = ["Chỉ chọn nội dung chữ; không OCR hoặc phục dựng cây, sơ đồ và công thức trong hình.",
                      "Nội dung tiếng Việt được biên soạn chọn lọc; không phải bản chép toàn bộ slide."]
            if is_legacy:
                limits.append("PPT cũ: nguồn định vị bằng khối chữ 0-based trong luồng PowerPoint Document; chưa xác định số slide.")
            if key == "vector_weights":
                limits.append("Chỉ diễn giải ý nghĩa PMI/PPMI/cosine; không trích công thức từ ảnh.")
            item_id = f"slide_ch{chapter:02d}_{key}"
            cards.append({"id": item_id, "chapter": chapter,
                          "title": title, "keywords": keywords, "content_vi": content})
            provenance.append({"id": item_id, "source_file": source_ref,
                               "source_sha256": checksum,
                               "source_slides": [] if is_legacy else refs,
                               "legacy_text_blocks": refs if is_legacy else [],
                               "evidence": evidence, "limitations": limits})
        total += len(cards)
        outputs[DEST / f"chapter_{chapter:02d}.jsonl"] = "".join(
            json.dumps(c, ensure_ascii=False) + "\n" for c in cards)
        md = [f"# Chapter {chapter}", ""]
        for card in cards:
            md += [f"## {card['title']}", "", card["content_vi"], ""]
        outputs[DEST / f"chapter_{chapter:02d}.md"] = "\n".join(md) + "\n"
        outputs[PROJECT / "data" / "raw" / f"chapter_{chapter:02d}.txt"] = "\n".join(
            text_record(card) for card in cards)
    outputs[DEST / "provenance.jsonl"] = "".join(
        json.dumps(record, ensure_ascii=False) + "\n" for record in provenance)
    outputs[DEST / "manifest.json"] = dump({
        "schema_version": 2, "chapters": list(range(1, 12)), "item_count": total,
        "counts_by_chapter": dict(sorted(Counter(str(r[0]) for r in seeds).items(), key=lambda x: int(x[0]))),
        "sources": sources, "ocr": False, "chapter_1_included": True,
        "knowledge_fields": ["id", "chapter", "title", "keywords", "content_vi"],
        "provenance_file": "provenance.jsonl",
        "integration_status": "Selected knowledge only; not indexed by the RAG pipeline yet."})
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path,
                        default=PROJECT.parents[1] / "Slide bài giảng-20260904")
    parser.add_argument("--check", action="store_true", help="Compare generated artifacts without writing")
    args = parser.parse_args()
    outputs = build(args.source_dir.resolve())
    mismatches = []
    for path, content in outputs.items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                mismatches.append(path.name)
        else:
            path.write_text(content, encoding="utf-8", newline="\n")
    if mismatches:
        raise SystemExit("Missing/stale artifacts: " + ", ".join(mismatches))
    print(f"{'Checked' if args.check else 'Built'} {len(outputs)} artifacts; "
          f"{json.loads(outputs[DEST / 'manifest.json'])['item_count']} items; chapters 1-11.")


if __name__ == "__main__":
    main()
