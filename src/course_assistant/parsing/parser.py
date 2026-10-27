"""Earley recognizer with backpointers for a complete bracketed parse tree.

An item is (production, dot, origin). Each chart column deduplicates items,
so prediction/completion terminates. One witness is retained per item.
Different QUERY labels stay separate; API reports syntactic intent ambiguity.
"""
from dataclasses import dataclass
from collections import deque, defaultdict
import json
from .grammar import Production, Symbol

@dataclass(frozen=True)
class Tree:
    label: str
    children: tuple = ()

    def terminals(self):
        for child in self.children:
            if isinstance(child, Tree):
                yield from child.terminals()
            else:
                yield child

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Tree):
                yield from child.walk()

    def bracketed(self):
        items = [child.bracketed() if isinstance(child, Tree)
                 else json.dumps(child, ensure_ascii=False) for child in self.children]
        return "(" + self.label + (" " + " ".join(items) if items else "") + ")"

@dataclass(frozen=True)
class Item:
    production: Production
    dot: int
    origin: int

    @property
    def complete(self):
        return self.dot == len(self.production.rhs)

    @property
    def next_symbol(self):
        return None if self.complete else self.production.rhs[self.dot]

class EarleyParser:
    def __init__(self, grammar):
        self.grammar = grammar

    def parse_tokens(self, tokens, start=None):
        start = start or self.grammar.start
        augmented = Production("__ROOT__", (Symbol(start),))
        charts = [dict() for _ in range(len(tokens) + 1)]
        agendas = [deque() for _ in charts]
        waiting = [defaultdict(list) for _ in charts]
        nullable = [dict() for _ in charts]

        def add(column, item, children):
            if item not in charts[column]:
                charts[column][item] = children
                agendas[column].append(item)
                symbol = item.next_symbol
                if symbol and not symbol.terminal:
                    waiting[column][symbol.name].append((item, children))

        add(0, Item(augmented, 0, 0), ())
        for column in range(len(charts)):
            while agendas[column]:
                item = agendas[column].popleft()
                children = charts[column][item]
                if item.complete:
                    tree = Tree(item.production.lhs, children)
                    if item.origin == column:
                        nullable[column].setdefault(tree.label, tree)
                    # Completion visits only waiting items for this constituent.
                    for parent, prefix in tuple(waiting[item.origin][tree.label]):
                        add(column, Item(parent.production, parent.dot + 1, parent.origin),
                            prefix + (tree,))
                else:
                    symbol = item.next_symbol
                    if symbol.terminal:
                        if column < len(tokens) and tokens[column] == symbol.name:
                            add(column + 1, Item(item.production, item.dot + 1, item.origin),
                                children + (tokens[column],))
                    else:
                        for production in self.grammar.by_lhs[symbol.name]:
                            add(column, Item(production, 0, column), ())
                        # A nullable constituent might have finished before this item.
                        if symbol.name in nullable[column]:
                            add(column, Item(item.production, item.dot + 1, item.origin),
                                children + (nullable[column][symbol.name],))
        result = charts[-1].get(Item(augmented, 1, 0))
        tree = result[0] if result else None
        completed_queries = [
            (item.production.lhs, item.origin, column)
            for column, chart in enumerate(charts) for item in chart
            if item.complete and item.production.lhs.startswith("QUERY_")
        ]
        return tree, completed_queries
