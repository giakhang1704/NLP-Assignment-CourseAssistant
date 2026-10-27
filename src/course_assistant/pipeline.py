"""Part I pipeline; emits semantic handoff but never fabricates QA answers."""
from pathlib import Path
from collections import Counter
import hashlib
import time
from .parsing.generator import SentenceGenerator
from .parsing.tokenizer import tokenize
from .exporters import read_sentences, write_lines, write_json, write_jsonl, export_parse_results
from .evaluation.runner import evaluate_queries, summarize, evaluate_cases


def verify_samples(parser, samples):
    count = 0
    failures = []
    for count, sentence in enumerate(samples, 1):
        tokens = tokenize(sentence)
        tree, _ = parser.earley.parse_tokens(tokens)
        if tree is None or tuple(tree.terminals()) != tokens:
            failures.append({"line": count, "sentence": sentence})
    return {"count": count, "failures": failures}


def run_part1(parser, input_path, output_dir, limit=10000, evaluation_path=None,
              legacy_path=None, cases_path=None, verify=True):
    started = time.perf_counter()
    destination = Path(output_dir)
    generator = SentenceGenerator(parser.grammar)
    samples = list(generator.generate(limit))
    sentences = read_sentences(input_path)
    results = [parser.parse(sentence) for sentence in sentences]
    write_lines(destination / "grammar.txt", parser.grammar.export().splitlines())
    write_lines(destination / "samples.txt", samples)
    export_parse_results(results, destination)
    verification = verify_samples(parser, samples) if verify else {"count": None, "failures": None}
    report = {
        "scope": "Part I grammar/generation/parser + semantic handoff; no retrieval or answer accuracy",
        "algorithm": "Earley", "productions": len(parser.grammar.productions),
        "nonterminals": len(parser.grammar.by_lhs), "derivations": generator.count("S"),
        "generated_count": len(samples), "unique_generated_count": len(set(samples)),
        "sample_verification": verification,
        "input_count": len(results), "valid_input_count": sum(r["is_valid"] for r in results),
        "input_statuses": dict(Counter(r["status"] for r in results)),
        "input_sha256": hashlib.sha256(Path(input_path).read_bytes()).hexdigest(),
        "grammar_sha256": hashlib.sha256(parser.grammar.export().encode("utf-8")).hexdigest(),
        "limits": [
            "Finite domain grammar, not general Vietnamese understanding.",
            "Provided queries are development coverage checks, not a held-out QA benchmark.",
            "A failed parse is unsupported syntax, not proof of an out-of-domain question.",
            "Context references are recognized, not yet resolved from a conversation.",
            "No retrieval, LLM answer, groundedness or end-to-end QA measurement is implemented.",
        ],
    }
    for name, path, check_entities in (("current_queries", evaluation_path, False),
                                        ("legacy_queries", legacy_path, True)):
        if path and Path(path).is_file():
            rows = evaluate_queries(parser, path, entity_annotations=check_entities)
            report[name] = summarize(rows)
            write_jsonl(destination / f"{name}.jsonl", rows)
    if cases_path and Path(cases_path).is_file():
        summary, rows = evaluate_cases(parser, cases_path)
        report["independent_cases"] = summary
        write_jsonl(destination / "independent_cases.jsonl", rows)
    report["seconds"] = round(time.perf_counter() - started, 3)
    write_json(destination / "part1-evaluation.json", report)
    lines = [
        "PART I EVALUATION — not end-to-end QA accuracy",
        f"Algorithm: Earley; productions: {report['productions']}",
        f"Generated: {len(samples)}; unique: {len(set(samples))}",
        f"Generated parsing checked: {verification['count']}; failures: {verification['failures']}",
        f"Input: {len(results)}; parsed: {report['valid_input_count']}",
    ]
    for name in ("current_queries", "legacy_queries"):
        if name in report:
            summary = report[name]
            lines.extend([
                f"{name}: total {summary['total']}; correct validity+intent(+entity if labeled): {summary['correct']}",
                f"  In-domain parsed {summary['in_scope_parsed']}/{summary['in_scope_count']}; OOD test rejection {summary['out_of_scope_rejected']}/{summary['out_of_scope_cases']}",
            ])
            for row in summary["failures"]:
                lines.append(f"  ERROR {row['id']}: {row['sentence']} | expected {row['expected_intent']} | observed {row['actual_intent']} ({row['status']})")
    if "independent_cases" in report:
        summary = report["independent_cases"]
        lines.append(f"Independent semantic/negative cases: {summary['correct']}/{summary['total']}")
        for row in summary["failures"]:
            lines.append(f"  ERROR: {row['sentence']} | checks: {row['failed_checks']}")
    lines.extend(["", "LIMITATIONS"] + report["limits"])
    write_lines(destination / "evaluation.txt", lines)
    return report
