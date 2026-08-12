"""tree-sitter parsing: symbol counts, raw import specifiers, and the syntax gate.

Complexity is lizard's job (see metrics/complexity.py). What is left here is what lizard
does not do: which files import which, how many symbols a file declares, and whether the
agent's output still parses.

Traversal is driven by node-type sets rather than the query language. Node type names are
stable across grammar releases, which keeps this working when the language pack updates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from tree_sitter import Node, Parser
from tree_sitter_language_pack import get_parser

from .schema import Lang

_GRAMMAR: dict[Lang, str] = {
    "python": "python",
    "typescript": "tsx",
    "javascript": "javascript",
    "java": "java",
    "go": "go",
    "rust": "rust",
    "c": "c",
    "cpp": "cpp",
    "csharp": "csharp",
    "ruby": "ruby",
    "php": "php",
    "kotlin": "kotlin",
    "swift": "swift",
    "scala": "scala",
}

_FUNCTION_NODES = frozenset(
    {
        "function_definition",
        "function_declaration",
        "function_expression",
        "method_definition",
        "arrow_function",
        "generator_function_declaration",
        "method_declaration",
        "constructor_declaration",
        "function_item",
        "function_declarator",
        "local_function_statement",
        "singleton_method",
        "method",
        "anonymous_function",
        "func_literal",
        "closure_expression",
        "lambda_expression",
        "lambda_literal",
        "init_declaration",
    }
)

_CLASS_NODES = frozenset(
    {
        "class_definition",
        "class_declaration",
        "class_specifier",
        "interface_declaration",
        "enum_declaration",
        "enum_specifier",
        "record_declaration",
        "struct_specifier",
        "struct_item",
        "struct_declaration",
        "trait_item",
        "trait_declaration",
        "trait_definition",
        "impl_item",
        "protocol_declaration",
        "type_declaration",
        "module",
    }
)


@dataclass(frozen=True, slots=True)
class ImportSpec:
    """A raw import as written in the source, before resolution to a file."""

    module: str
    level: int = 0  # leading dots in a Python relative import


@dataclass(slots=True)
class ParsedFile:
    functions: int = 0
    classes: int = 0
    doc_lines: int = 0
    imports: list[ImportSpec] = field(default_factory=list)
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
    out.doc_lines = _doc_lines(tree.root_node, lang)
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
    elif lang in ("java", "kotlin"):
        _java_import(node, src, out)
    elif lang in ("c", "cpp"):
        _include(node, src, out)
    else:
        _js_import(node, src, out)

    for child in node.children:
        _walk(child, src, lang, out)


_DOC_PARENTS = frozenset({"module", "function_definition", "class_definition"})


def _doc_lines(root: Node, lang: Lang) -> int:
    """Python documents with docstrings, not `#`, so a lexical comment count reports zero
    for well-documented files. Docstrings are string expressions in a body's first slot."""
    if lang != "python":
        return 0

    total = 0
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type in _DOC_PARENTS:
            body = node if node.type == "module" else node.child_by_field_name("body")
            literal = _leading_string(body)
            if literal is not None:
                total += literal.end_point[0] - literal.start_point[0] + 1
        stack.extend(node.children)
    return total


def _leading_string(body: Node | None) -> Node | None:
    """The docstring in a body's first slot.

    Current grammars put the literal there directly; older ones wrap it in an
    expression_statement. Both shapes are accepted so a grammar bump cannot silently
    zero out every comment count.
    """
    if body is None or not body.named_child_count:
        return None
    first = body.named_children[0]
    if first.type == "string":
        return first
    if first.type == "expression_statement" and first.named_child_count:
        inner = first.named_children[0]
        return inner if inner.type == "string" else None
    return None


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


def _java_import(node: Node, src: bytes, out: ParsedFile) -> None:
    if node.type not in ("import_declaration", "import_header"):
        return
    text = _text(node, src).strip().rstrip(";")
    text = text.removeprefix("import").strip().removeprefix("static").strip()
    if text:
        out.imports.append(ImportSpec(text))


def _include(node: Node, src: bytes, out: ParsedFile) -> None:
    """`#include "x.h"` names a file; `<x.h>` names a system header, which is external."""
    if node.type != "preproc_include":
        return
    path = node.child_by_field_name("path")
    if path is None:
        return
    text = _text(path, src)
    if text.startswith('"'):
        out.imports.append(ImportSpec(text.strip('"')))


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
