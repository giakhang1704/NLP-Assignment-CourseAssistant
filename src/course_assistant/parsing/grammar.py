"""Load an explicit CFG and a separate, typed domain lexicon."""
from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict
import json
import re
from .tokenizer import tokenize

@dataclass(frozen=True)
class Symbol:
    name: str
    terminal: bool = False

@dataclass(frozen=True)
class Production:
    lhs: str
    rhs: tuple

class Grammar:
    def __init__(self, productions, start="S", lexicon=None):
        self.start = start
        self.productions = tuple(dict.fromkeys(productions))
        self.by_lhs = defaultdict(list)
        for production in self.productions:
            self.by_lhs[production.lhs].append(production)
        self.lexicon = lexicon or {}
        if start not in self.by_lhs:
            raise ValueError(f"Missing start symbol {start}")
        for production in self.productions:
            for symbol in production.rhs:
                if not symbol.terminal and symbol.name not in self.by_lhs:
                    raise ValueError(f"Undefined nonterminal: {symbol.name}")
        self.reachable = set()
        self._check_acyclic(start, set())
        unreachable = set(self.by_lhs) - self.reachable
        if unreachable:
            raise ValueError(f"Unreachable nonterminals: {sorted(unreachable)}")

    def _check_acyclic(self, symbol, active):
        if symbol in active:
            raise ValueError(f"Recursive CFG not supported by bounded generator: {symbol}")
        if symbol in self.reachable:
            return
        self.reachable.add(symbol)
        for production in self.by_lhs[symbol]:
            for child in production.rhs:
                if not child.terminal:
                    self._check_acyclic(child.name, active | {symbol})

    @classmethod
    def load(cls, grammar_path, lexicon_path):
        productions = []
        for number, line in enumerate(Path(grammar_path).read_text(encoding="utf-8-sig").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            lhs, separator, rhs = line.partition(" ->")
            if not separator or not re.fullmatch(r"[A-Z][A-Z0-9_]*", lhs):
                raise ValueError(f"Invalid CFG rule at line {number}: {line}")
            symbols = []
            while rhs.strip():
                rhs = rhs.lstrip()
                if rhs.startswith('"'):
                    phrase, consumed = json.JSONDecoder().raw_decode(rhs)
                    if not isinstance(phrase, str) or not tokenize(phrase):
                        raise ValueError(f"Empty terminal at line {number}")
                    symbols.extend(Symbol(t, True) for t in tokenize(phrase))
                    rhs = rhs[consumed:]
                else:
                    match = re.match(r"[A-Z][A-Z0-9_]*", rhs)
                    if not match:
                        raise ValueError(f"Invalid RHS at line {number}: {rhs}")
                    symbols.append(Symbol(match[0]))
                    rhs = rhs[len(match[0]):]
            productions.append(Production(lhs, tuple(symbols)))
        data = json.loads(Path(lexicon_path).read_text(encoding="utf-8-sig"))
        lexicon = {}
        for category in data["categories"]:
            symbol = category["symbol"]
            mapping = {}
            for entry in category["entries"]:
                for alias in entry["aliases"]:
                    tokens = tokenize(alias)
                    if not tokens:
                        raise ValueError(f"Empty lexical alias: {symbol}")
                    value = {k: v for k, v in entry.items() if k != "aliases"}
                    value["type"] = category["entity_type"]
                    previous = mapping.get(tokens)
                    if previous is not None and previous != value:
                        raise ValueError(f"Conflicting lexical alias: {symbol}, {alias}")
                    mapping[tokens] = value
                    productions.append(Production(symbol, tuple(Symbol(t, True) for t in tokens)))
            lexicon[symbol] = mapping
        return cls(productions, lexicon=lexicon)

    def export(self):
        lines = [
            "# Course Assistant CFG; start symbol: S",
            "# Each line is one production. Quoted items are terminals.",
            "# Empty RHS is epsilon. Includes all expanded lexical productions.",
        ]
        for production in self.productions:
            rhs = " ".join(json.dumps(s.name, ensure_ascii=False) if s.terminal else s.name
                           for s in production.rhs)
            lines.append(f"{production.lhs} -> {rhs}".rstrip())
        return "\n".join(lines) + "\n"
