"""Evaluate labeled questions without using labels to parse or infer semantics."""
from pathlib import Path

TOPIC_INTENTS = {"DEFINITION_QUERY", "PROCESS_QUERY", "COMPARISON_QUERY"}


def normalize_intent(intent):
    return "GET_TOPIC" if intent in TOPIC_INTENTS else intent


def read_labeled_queries(path):
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.startswith("Q") or " | " not in line:
            continue
        columns = [column.strip() for column in line.split(" | ")]
        if len(columns) != 4:
            raise ValueError(f"Invalid labeled query at line {number}: expected 4 fields")
        query_id, sentence, intent, annotation = columns
        rows.append({"id": query_id, "sentence": sentence, "expected_intent": intent,
                     "source_annotation": annotation})
    return rows


def evaluate_queries(parser, path, entity_annotations=False):
    results = []
    for row in read_labeled_queries(path):
        actual = parser.parse(row["sentence"])
        expected = normalize_intent(row["expected_intent"])
        valid_expected = expected != "UNKNOWN"
        frame = actual.get("semantic_frame") or {}
        observed = frame.get("intent", normalize_intent(actual["intent_type"]))
        # Current source annotations are topic/category labels, not canonical IDs.
        entity_ok = None
        if entity_annotations and valid_expected and expected != "CONTEXT_DEPENDENT":
            entity_ok = row["source_annotation"] in {e["id"] for e in actual["entities"]}
        results.append({
            **row, "expected_valid": valid_expected, "is_valid": actual["is_valid"],
            "status": actual["status"], "actual_intent": observed,
            "raw_parser_intent": actual["intent_type"], "needs_context": actual["needs_context"],
            "actual_entities": actual["entities"], "attribute": frame.get("attribute"),
            "validity_correct": actual["is_valid"] == valid_expected,
            "intent_correct": observed == expected, "entity_correct": entity_ok,
            "correct": actual["is_valid"] == valid_expected and observed == expected and entity_ok is not False,
        })
    return results


def summarize(rows):
    in_scope = [r for r in rows if r["expected_valid"]]
    ood = [r for r in rows if not r["expected_valid"]]
    return {
        "total": len(rows), "in_scope_count": len(in_scope),
        "in_scope_parsed": sum(r["is_valid"] for r in in_scope),
        "in_scope_parse_coverage": sum(r["is_valid"] for r in in_scope) / len(in_scope) if in_scope else None,
        "out_of_scope_cases": len(ood), "out_of_scope_rejected": sum(not r["is_valid"] for r in ood),
        "validity_correct": sum(r["validity_correct"] for r in rows),
        "intent_correct": sum(r["intent_correct"] for r in rows),
        "correct": sum(r["correct"] for r in rows),
        "accuracy": sum(r["correct"] for r in rows) / len(rows) if rows else None,
        "entity_evaluated": sum(r["entity_correct"] is not None for r in rows),
        "entity_correct": sum(r["entity_correct"] is True for r in rows),
        "failures": [r for r in rows if not r["correct"]],
    }


def evaluate_cases(parser, path):
    """Check independently authored semantic slots and negative cases."""
    import json
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected = json.loads(line)
        actual = parser.parse(expected["sentence"])
        frame = actual.get("semantic_frame") or {}
        failures = []
        if actual["is_valid"] != expected["is_valid"]:
            failures.append("validity")
        for key in ("intent", "attribute", "question_type", "needs_context"):
            if key in expected:
                value = actual.get(key) if key == "needs_context" else frame.get(key)
                if value != expected[key]:
                    failures.append(key)
        for entity_id in expected.get("entity_ids", []):
            if entity_id not in {e["id"] for e in actual["entities"]}:
                failures.append("entity:" + entity_id)
        rows.append({**expected, "correct": not failures, "failed_checks": failures,
                     "actual_status": actual["status"], "actual_frame": frame})
    return {"total": len(rows), "correct": sum(r["correct"] for r in rows),
            "failures": [r for r in rows if not r["correct"]]}, rows
