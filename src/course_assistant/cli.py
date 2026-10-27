"""CLI for independently reviewable Part I outputs."""
import argparse
import json
from pathlib import Path
import unittest
import sys
from .config import PROJECT_ROOT, load_config, resource_path
from .exporters import read_sentences, write_lines, write_jsonl
from .pipeline import run_part1, verify_samples
from .parsing.generator import SentenceGenerator


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    cli = argparse.ArgumentParser(description="CO3085 Course Assistant — CFG, Earley and semantic handoff")
    cli.add_argument("--config", type=Path)
    commands = cli.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Produce and verify Part I outputs")
    run.add_argument("--input", type=Path)
    run.add_argument("--output-dir", type=Path)
    run.add_argument("--limit", type=int)
    run.add_argument("--skip-sample-verification", action="store_true")
    inspect = commands.add_parser("inspect", help="Inspect parse tree, frame and retrieval query (no QA)")
    inspect.add_argument("sentence")
    parse = commands.add_parser("parse", help="One bracketed tree or () per input line")
    parse.add_argument("--input", type=Path)
    parse.add_argument("--output", type=Path)
    parse.add_argument("--api-output", type=Path)
    generate = commands.add_parser("generate")
    generate.add_argument("--limit", type=int)
    generate.add_argument("--output", type=Path)
    grammar = commands.add_parser("grammar")
    grammar.add_argument("--output", type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("--samples", type=Path)
    commands.add_parser("test", help="Run local regression tests; no API/network calls")
    args = cli.parse_args(argv)
    try:
        if args.command == "test":
            suite = unittest.defaultTestLoader.discover(str(PROJECT_ROOT / "tests"))
            return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
        config = load_config(args.config)
        # Validate limits before writing or loading any generated output.
        limit = getattr(args, "limit", None)
        limit = config["sample_limit"] if limit is None else limit
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 10000:
            raise ValueError("limit must be an integer in [1, 10000]")
        from .parsing.api import CourseParser
        parser = CourseParser(resource_path(config["grammar"]), resource_path(config["lexicon"]),
                              resource_path(config["intent_schema"]), max_tokens=config["max_tokens"])
        output_dir = resource_path(config["output"])
        if args.command == "run":
            report = run_part1(parser, args.input or resource_path(config["input"]),
                               args.output_dir or output_dir, limit,
                               resource_path(config["evaluation"]),
                               PROJECT_ROOT / "data/evaluation/legacy_queries.txt",
                               PROJECT_ROOT / "data/evaluation/independent_cases.jsonl",
                               verify=not args.skip_sample_verification)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 1 if report["sample_verification"]["failures"] else 0
        if args.command == "inspect":
            print(json.dumps(parser.parse(args.sentence), ensure_ascii=False, indent=2))
        elif args.command == "parse":
            results = [parser.parse(s) for s in read_sentences(args.input or resource_path(config["input"]))]
            write_lines(args.output or output_dir / "parse-results.txt", (r["parse_tree"] for r in results))
            if args.api_output:
                write_jsonl(args.api_output, results)
            print(json.dumps({"sentences": len(results), "parsed": sum(r["is_valid"] for r in results)}))
        elif args.command == "generate":
            write_lines(args.output or output_dir / "samples.txt", SentenceGenerator(parser.grammar).generate(limit))
        elif args.command == "grammar":
            write_lines(args.output or output_dir / "grammar.txt", parser.grammar.export().splitlines())
        elif args.command == "verify":
            result = verify_samples(parser, read_sentences(args.samples or output_dir / "samples.txt"))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1 if result["failures"] else 0
    except (ValueError, OSError, RuntimeError) as error:
        cli.exit(1, f"Error: {error}\n")
    return 0
