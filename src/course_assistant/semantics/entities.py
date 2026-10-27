"""Entity mentions tied to the original input and the accepted parse tree."""
import unicodedata
from ..parsing.tokenizer import _TOKEN, tokenize


def token_spans(text):
    """Return normalized tokens with half-open Python character offsets.

    Normalization is performed by base/combining-mark clusters so NFC and
    casefold expansions still point back to the original text, including NFD.
    """
    normalized, positions = [], []
    cursor = 0
    while cursor < len(text):
        end = cursor + 1
        while end < len(text) and unicodedata.combining(text[end]):
            end += 1
        value = unicodedata.normalize("NFC", text[cursor:end]).casefold()
        value = value.translate(str.maketrans({"–": "-", "—": "-", "‑": "-"}))
        normalized.extend(value)
        positions.extend([(cursor, end)] * len(value))
        cursor = end
    value = "".join(normalized)
    spans = [(match.group(), positions[match.start()][0], positions[match.end() - 1][1])
             for match in _TOKEN.finditer(value)]
    if tuple(token for token, _, _ in spans) != tokenize(text):
        # Do not invent source offsets for an unusual normalization boundary.
        return [(token, None, None) for token in tokenize(text)]
    return spans


def unique_entities(mentions):
    result = []
    for mention in mentions:
        if not any((e["type"], e["id"]) == (mention["type"], mention["id"])
                   for e in result):
            result.append({k: v for k, v in mention.items()
                           if k not in {"start", "end", "token_start", "token_end", "role"}})
    return result


def extract_mentions(tree, grammar, sentence):
    """Use lexical constituents rather than searching aliases in raw text."""
    spans = token_spans(sentence)
    mentions = []

    def visit(node, offset):
        terminals = tuple(node.terminals())
        mapping = grammar.lexicon.get(node.label)
        if mapping is not None:
            value = mapping[terminals]
            first, last = spans[offset], spans[offset + len(terminals) - 1]
            begin, end = first[1], last[2]
            mentions.append({**value, "surface": sentence[begin:end] if begin is not None else None,
                             "start": begin, "end": end,
                             "token_start": offset, "token_end": offset + len(terminals)})
            return offset + len(terminals)
        for child in node.children:
            if hasattr(child, "label"):
                offset = visit(child, offset)
            else:
                offset += 1
        return offset

    visit(tree, 0)
    # The original grammar has a few deictic constructions made of terminals
    # instead of E_REFERENCE. Keep these explicit until that grammar is extended.
    tokens = tuple(token for token, _, _ in spans)
    references = [(('môn', 'này'), 'LAST_COURSE'),
                  (('chương', 'sau'), 'NEXT_CHAPTER'),
                  (('yêu', 'cầu', 'của', 'nó'), 'LAST_ASSIGNMENT')]
    for phrase, entity_id in references:
        for index in range(len(tokens) - len(phrase) + 1):
            if tokens[index:index + len(phrase)] != phrase:
                continue
            if any(m["type"] == "reference" and m["token_start"] < index + len(phrase)
                   and m["token_end"] > index for m in mentions):
                continue
            begin, end = spans[index][1], spans[index + len(phrase) - 1][2]
            mentions.append({"type": "reference", "id": entity_id, "value": entity_id,
                             "surface": sentence[begin:end] if begin is not None else None,
                             "start": begin, "end": end, "token_start": index,
                             "token_end": index + len(phrase)})
    return sorted(mentions, key=lambda mention: mention["token_start"])
