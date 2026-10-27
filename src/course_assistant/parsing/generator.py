"""Deterministic, lazy enumeration from CFG derivations, with fair sampling."""
from functools import lru_cache
from .tokenizer import detokenize

MAX_SAMPLES = 10_000

class SentenceGenerator:
    def __init__(self, grammar):
        self.grammar = grammar

    @lru_cache(maxsize=None)
    def count(self, symbol):
        """Count derivations, not unique strings (ambiguous CFGs can differ)."""
        result = 0
        for rule in self.grammar.by_lhs[symbol]:
            count = 1
            for child in rule.rhs:
                if not child.terminal:
                    count *= self.count(child.name)
            result += count
        return result

    def unrank(self, symbol, rank):
        """Decode an index without materializing the Cartesian product."""
        for rule in self.grammar.by_lhs[symbol]:
            radices = [1 if s.terminal else self.count(s.name) for s in rule.rhs]
            block = 1
            for radix in radices:
                block *= radix
            if rank >= block:
                rank -= block
                continue
            indices = [0] * len(radices)
            for i in reversed(range(len(radices))):
                indices[i] = rank % radices[i]
                rank //= radices[i]
            result = []
            for child, index in zip(rule.rhs, indices):
                result.extend((child.name,) if child.terminal else self.unrank(child.name, index))
            return tuple(result)
        raise IndexError("Derivation index outside grammar")

    def _fair_derivations(self, symbol):
        """Visit every production, even when the first one has many aliases."""
        streams = []
        for rule in self.grammar.by_lhs[symbol]:
            radices = [1 if s.terminal else self.count(s.name) for s in rule.rhs]
            total = 1
            for radix in radices:
                total *= radix
            streams.append([rule, radices, total, 0])
        while streams:
            for stream in list(streams):
                rule, radices, total, rank = stream
                value = rank
                indices = [0] * len(radices)
                for i in reversed(range(len(radices))):
                    indices[i] = value % radices[i]
                    value //= radices[i]
                result = []
                for child, index in zip(rule.rhs, indices):
                    result.extend((child.name,) if child.terminal else self.unrank(child.name, index))
                yield tuple(result)
                stream[3] += 1
                if stream[3] >= total:
                    streams.remove(stream)

    def generate(self, limit=MAX_SAMPLES):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_SAMPLES:
            raise ValueError("limit must be an integer in [1, 10000]")
        seen = set()
        for tokens in self._fair_derivations("QUESTION"):
            # Canonical production: S -> PREFIX QUESTION END, PREFIX -> epsilon,
            # END -> "?". The grammar loader checks these invariants in API setup.
            sentence = detokenize(tokens + ("?",))
            if sentence in seen:
                continue
            seen.add(sentence)
            yield sentence
            if len(seen) >= limit:
                break
