"""Parser API with explicit status, source mentions and semantic handoff."""
from functools import lru_cache
from pathlib import Path
import json
from ..config import PROJECT_ROOT, DEFAULT_GRAMMAR_PATH, DEFAULT_LEXICON_PATH, DEFAULT_SCHEMA_PATH
from .grammar import Grammar
from .parser import EarleyParser
from .tokenizer import tokenize, detokenize
from ..semantics.entities import extract_mentions, unique_entities
from ..semantics.interpreter import interpret
from ..semantics.query_builder import build_query, build_fallback_query

ROOT = PROJECT_ROOT  # Compatibility with the original Part I API.


class CourseParser:
    def __init__(self, grammar_path=None, lexicon_path=None, schema_path=None, max_tokens=128):
        self.grammar = Grammar.load(grammar_path or DEFAULT_GRAMMAR_PATH,
                                    lexicon_path or DEFAULT_LEXICON_PATH)
        self.schema = json.loads(Path(schema_path or DEFAULT_SCHEMA_PATH).read_text(encoding="utf-8-sig"))
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
            raise ValueError("max_tokens must be a positive integer")
        self.earley = EarleyParser(self.grammar)
        self.max_tokens = max_tokens
        expected = {("S", ("PREFIX", "QUESTION", "END")), ("PREFIX", ()), ("END", ("?",))}
        actual = {(p.lhs, tuple(s.name for s in p.rhs)) for p in self.grammar.productions}
        if not expected <= actual:
            raise ValueError("CFG must contain the canonical generator wrapper")
        labels = {p.lhs for p in self.grammar.productions if p.lhs.startswith("QUERY_")}
        if labels != set(self.schema["queries"]):
            raise ValueError("Intent schema and CFG query labels disagree")

    def parse(self, sentence):
        tokens = tokenize(sentence)
        base = {"sentence": sentence, "normalized_sentence": detokenize(tokens),
                "is_valid": False, "status": "unsupported_form", "parse_tree": "()",
                "intent_type": "UNKNOWN", "entities": [], "mentions": [],
                "needs_context": False, "ambiguity": False, "candidate_intents": [],
                "error": None, "semantic_frame": None, "query": None}
        if not tokens:
            base.update(status="empty_input", error="empty_input")
            return base
        if len(tokens) > self.max_tokens:
            base.update(status="input_too_long", error="input_too_long")
            return base
        tree, completed_queries = self.earley.parse_tokens(tokens)
        if tree is None:
            base["error"] = "not_in_grammar"
            base["query"] = build_fallback_query(sentence)
            return base
        query_nodes = [node for node in tree.walk() if node.label in self.schema["queries"]]
        if len(query_nodes) != 1:
            raise RuntimeError("Expected exactly one QUERY node in parse tree")
        node = query_nodes[0]
        spec = self.schema["queries"][node.label]
        mentions = extract_mentions(tree, self.grammar, sentence)
        entities = unique_entities(mentions)
        for entity in spec.get("implicit_entities", []):
            if not any((e["type"], e["id"]) == (entity["type"], entity["id"]) for e in entities):
                entities.append({**entity, "surface": None, "implicit": True})
        if not any(entity["type"] == "course" for entity in entities):
            entities.append({"type": "course", "id": "CO3085", "value": "CO3085",
                             "surface": None, "implicit": True})
        needs_context = bool(spec.get("needs_context") or any(e["type"] == "reference" for e in entities))
        origin = len(tuple(tree.children[0].terminals()))
        end = len(tokens) - len(tuple(tree.children[-1].terminals()))
        candidates = sorted({self.schema["queries"][label]["intent"]
                             for label, begin, finish in completed_queries
                             if begin == origin and finish == end})
        base.update(is_valid=True, status="needs_context" if needs_context else "parsed",
                    parse_tree=tree.bracketed(), intent_type=spec["intent"], entities=entities,
                    mentions=mentions, needs_context=needs_context,
                    ambiguity=len(candidates) > 1, candidate_intents=candidates)
        frame = interpret(node, base, spec)
        base["semantic_frame"] = frame
        base["query"] = build_query(frame, sentence)
        return base

    def analyze(self, sentence):
        return self.parse(sentence)


@lru_cache(maxsize=1)
def get_default_parser():
    return CourseParser()


def parse(sentence):
    return get_default_parser().parse(sentence)


def analyze(sentence):
    return get_default_parser().analyze(sentence)
