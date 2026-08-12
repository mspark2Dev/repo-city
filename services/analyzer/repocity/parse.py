"""tree-sitter parsing: symbol counts and raw import specifiers.

Traversal is driven by node-type sets rather than the query language. Node type names are
stable across grammar releases, which keeps this working when the language pack updates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from tree_sitter import Node, Parser
from tree_sitter_language_pack import get_parser

from .metrics.complexity import ComplexityResult, complexity
from .schema import Lang

_GRAMMAR: dict[Lang, str] = {
    "python": "python",
    "typescript": "tsx",
    "javascript": "javascript",
}

_FUNCTION_NODES = frozenset(
    {
        "function_definition",
        "function_declaration",
        "function_expression",
        "method_definition",
        "arrow_function",
        "generator_function_declaration",
    }
)

_CLASS_NODES = frozenset({"class_definition", "class_declaration"})


@dataclass(frozen=True, slots=True)
class ImportSpec:
    """A raw import as written in the source, before resolution to a file."""

    module: str
    level: int = 0  # leading dots in a Python relative import


@dataclass(slots=True)
class ParsedFile:
    functions: int = 0
    classes: int = 0
    imports: list[ImportSpec] = field(default_factory=list)
    cc: ComplexityResult = field(
        default_factory=lambda: ComplexityResult(max_cc=0, avg_cc=0.0, total_cc=0, function_count=0)
    )
    ok: bool = True

    @property
    def symbols(self) -> int:
        return self.functions + self.classes


@lru_cache(maxsize=8)
def _parser_for(lang: Lang) -> Parser | None:
    grammar = _GRAMMAR.get(lang)
    return get_parser(grammar) if grammar else None


def parse_source(source: bytes, lang: Lang) -> ParsedFile:
    parser = _parser_for(lang)
    if parser is None:
        return ParsedFile(ok=True)

    tree = parser.parse(source)
    out = ParsedFile()
    _walk(tree.root_node, source, lang, out)
    out.cc = complexity(tree.root_node, source, _GRAMMAR[lang])
    out.ok = not tree.root_node.has_error
    return out


def is_parsable(source: bytes, lang: Lang) -> bool:
    """Syntax gate for agent output — the parser is already here, so the check is free."""
    parser = _parser_for(lang)
    if parser is None:
        return True
    return not parser.parse(source).root_node.has_error


def _walk(node: Node, src: bytes, lang: Lang, out: ParsedFile) -> None:
    kind = node.type
    if kind in _FUNCTION_NODES:
        out.functions += 1
    elif kind in _CLASS_NODES:
        out.classes += 1
    elif lang == "python":
        _python_import(node, src, out)
    else:
        _js_import(node, src, out)

    for child in node.children:
        _walk(child, src, lang, out)


def _text(node: Node, src: bytes) -> str:
    return src[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _python_import(node: Node, src: bytes, out: ParsedFile) -> None:
    if node.type == "import_statement":
        for child in node.named_children:
            if child.type == "dotted_name":
                out.imports.append(ImportSpec(_text(child, src)))
            elif child.type == "aliased_import":
                name = child.child_by_field_name("name")
                if name is not None:
                    out.imports.append(ImportSpec(_text(name, src)))

    elif node.type == "import_from_statement":
        module = node.child_by_field_name("module_name")
        if module is None:
            return
        if module.type == "relative_import":
            prefix = module.child(0)
            level = len(_text(prefix, src)) if prefix is not None else 1
            dotted = next((c for c in module.named_children if c.type == "dotted_name"), None)
            out.imports.append(ImportSpec(_text(dotted, src) if dotted else "", level))
        else:
            out.imports.append(ImportSpec(_text(module, src)))


def _js_import(node: Node, src: bytes, out: ParsedFile) -> None:
    if node.type in ("import_statement", "export_statement"):
        source = node.child_by_field_name("source")
        if source is not None:
            out.imports.append(ImportSpec(_text(source, src).strip("'\"")))

    elif node.type == "call_expression":
        fn = node.child_by_field_name("function")
        if fn is None or _text(fn, src) not in ("require", "import"):
            return
        args = node.child_by_field_name("arguments")
        if args is None:
            return
        literal = next((c for c in args.named_children if c.type == "string"), None)
        if literal is not None:
            out.imports.append(ImportSpec(_text(literal, src).strip("'\"")))
