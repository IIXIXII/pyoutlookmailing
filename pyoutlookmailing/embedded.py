#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

"""Read configuration from leading Markdown variable comments."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import unquote, urlsplit

import mistune
import yaml
from pymdtools.instruction import get_vars_from_md_text, unescape_var_value

_LEADING = r"(?:[ \t]*\r?\n)* {0,3}"
_COMMENT = re.compile(_LEADING + r"<!--(?P<body>.*?)-->", re.DOTALL)
_CONFIG = re.compile(
    r"\s*var\(conf(?P<path>/[^)]*)?\)\s*=\s*(?P<value>.*)", re.DOTALL
)
_CONFIG_PREFIX = re.compile(r"\s*var\(conf(?:/|\))")
_CONFIG_START = re.compile(_LEADING + r"<!--\s*var\(conf(?:/|\))")
_KEY = r"[A-Za-z_][A-Za-z0-9:_-]*"
_PATH = re.compile(rf"{_KEY}(?:/(?:{_KEY}|0|[1-9][0-9]*))*")
_STRING = re.compile(
    r"""(?P<quote>['"])(?P<value>(?:\\.|(?!(?P=quote)).)*)(?P=quote)""",
    re.DOTALL,
)
_LITERAL = re.compile(
    r"true|false|null|\[\]|\{\}|-?(?:0|[1-9][0-9]*)"
    r"(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?"
)
_RECIPIENT_SECTIONS = ("to", "cc", "bcc", "Bcc", "not_to")
_RECIPIENT_LISTS = {f"{section}/list" for section in _RECIPIENT_SECTIONS}
_APPEND_LISTS = (
    _RECIPIENT_LISTS
    | {f"{section}/excel_column_name" for section in _RECIPIENT_SECTIONS}
    | {"email/attachments", "paths/includes", "paths/base_search"}
)
_LINK_MARKDOWN = mistune.create_markdown(renderer="ast")


# -----------------------------------------------------------------------------
def _read_value(payload: str, path: str) -> Any:
    """Parse a quoted pymdtools string or an allowed JSON-style literal.

    Allowed unquoted values are booleans, null, numbers, [] and {}. Nonempty
    collections are expressed through configuration paths instead. Invalid
    syntax raises ValueError with the configuration path in the message.
    """
    if quoted := _STRING.fullmatch(payload):
        return unescape_var_value(quoted["value"])
    if _LITERAL.fullmatch(payload):
        return json.loads(payload)
    raise ValueError(
        f"Valeur invalide pour var(conf/{path}) : "
        "utiliser une chaîne entre guillemets, "
        "true, false, un nombre, null, [] ou {}"
    )


# -----------------------------------------------------------------------------
def _recipient_value(value: str, path: str) -> str:
    """Extract one mailto target, or return a trimmed plain email string.

    Markdown must contain exactly one mailto link. Query parameters, fragments,
    empty targets, whitespace, and control characters in mailto URLs are
    rejected. Address syntax and duplicates are checked later by
    core._addresses.
    """
    value = value.strip()
    url = value
    if value.startswith("["):
        tokens = _LINK_MARKDOWN(value)
        if not isinstance(tokens, list):
            raise TypeError(
                "Le parseur Markdown doit produire une liste de jetons"
            )
        children = tokens[0].get("children", []) if len(tokens) == 1 else []
        if len(children) != 1 or children[0]["type"] != "link":
            raise ValueError(
                f"var(conf/{path}) attend une adresse "
                "ou un seul lien Markdown mailto"
            )
        url = children[0]["attrs"]["url"]
    elif not value.lower().startswith("mailto:"):
        return value
    target = urlsplit(url)
    if (
        target.scheme.lower() != "mailto"
        or target.netloc
        or target.query
        or target.fragment
        or not target.path
    ):
        raise ValueError(
            f"var(conf/{path}) attend un lien mailto "
            "contenant uniquement une adresse"
        )
    address = unquote(target.path, errors="strict")
    if any(
        char.isspace() or ord(char) < 32 or ord(char) == 127
        for char in url + address
    ):
        raise ValueError(
            f"var(conf/{path}) attend une adresse mailto "
            "sans espaces ni contrôles"
        )
    return address


# -----------------------------------------------------------------------------
def _add_variable(variables: dict[str, Any], path: str, value: Any) -> None:
    """Add a parsed variable in place, applying recipient and list conventions.

    Known list paths append strings in document order; [] appends nothing. Other
    paths are unique. Indexed and nested-path conflicts are detected by _expand.
    Raise ValueError for invalid list values or duplicate scalar declarations.
    """
    parent, _, index = path.rpartition("/")
    if isinstance(value, str) and (
        path in _RECIPIENT_LISTS
        or (parent in _RECIPIENT_LISTS and index.isdecimal())
    ):
        value = _recipient_value(value, path)
    if path in _APPEND_LISTS:
        if not isinstance(value, str) and value != []:
            raise ValueError(
                f"var(conf/{path}) attend un élément entre guillemets ou []"
            )
        items = variables.setdefault(path, [])
        if isinstance(value, str):
            items.append(value)
    else:
        if path in variables:
            raise ValueError(
                f"La variable var(conf/{path}) est définie plusieurs fois"
            )
        variables[path] = value


# -----------------------------------------------------------------------------
def _expand(variables: dict[str, Any], path: str = "conf") -> Any:
    """Expand flat slash-separated paths into nested mappings and lists.

    Numeric children must form contiguous indices starting at zero. Raise
    ValueError for gaps, mixed numeric/named children, or overlapping leaf
    paths. The input mapping is not modified.
    """
    if "" in variables:
        if len(variables) != 1:
            raise ValueError(
                f"Conflit : var({path}) et ses sous-chemins "
                "sont définis ensemble"
            )
        return variables[""]
    children: dict[str, dict[str, Any]] = {}
    for name, value in variables.items():
        key, _, rest = name.partition("/")
        children.setdefault(key, {})[rest] = value
    if any(key.isdecimal() for key in children):
        if set(children) != {str(i) for i in range(len(children))}:
            raise ValueError(
                f"var({path}) : les indices de liste "
                "doivent être consécutifs depuis 0"
            )
        return [
            _expand(children[str(i)], f"{path}/{i}")
            for i in range(len(children))
        ]
    return {
        key: _expand(child, f"{path}/{key}") for key, child in children.items()
    }


# -----------------------------------------------------------------------------
def split_configuration(
    text: str, *, required: bool = False
) -> tuple[dict[str, Any] | None, str]:
    """Extract configuration from leading Markdown comments and return the body.

    Args:
        text: Markdown with optional var(conf/path) declarations at the start. A
            leading UTF-8 BOM, blank lines, and ordinary comments are accepted.
        required: Raise ValueError if no configuration declaration is found.

    Returns:
        A (configuration, body) pair. Configuration is None when optional and
        absent. Only configuration comments in the leading header are removed;
        ordinary variables, later comments, and fenced examples remain in the
        body.

    Raises:
        ValueError: Declarations are malformed, conflicting, duplicated where
            only one value is allowed, or mix legacy var(conf) YAML with path
            syntax.
        yaml.YAMLError: A legacy YAML block has invalid YAML syntax.

    Known list fields append repeated values. Numeric path components support
    indexed lists. This function does not read includes or files, resolve paths,
    render HTML, or validate the complete delivery configuration.
    """
    text = text.removeprefix("\ufeff")
    position = 0
    legacy = None
    variables: dict[str, Any] = {}
    body = []
    retained = 0
    while match := _COMMENT.match(text, position):
        if variable := _CONFIG.fullmatch(match["body"]):
            payload = variable["value"].strip()
            if variable["path"] is not None:
                path = variable["path"][1:]
                if not _PATH.fullmatch(path):
                    raise ValueError(f"Chemin invalide dans var(conf/{path})")
                _add_variable(variables, path, _read_value(payload, path))
            else:
                if legacy is not None:
                    raise ValueError(
                        "Un seul bloc var(conf) est autorisé "
                        "en tête du Markdown"
                    )
                if payload.startswith(('"', "'")):
                    quoted = get_vars_from_md_text(match.group())
                    if "conf" not in quoted:
                        raise ValueError(
                            "La variable var(conf) entre guillemets "
                            "est mal formée"
                        )
                    payload = quoted["conf"]
                legacy = yaml.safe_load(payload)
                if not isinstance(legacy, dict):
                    raise ValueError("var(conf) doit contenir un objet YAML")
            if legacy is not None and variables:
                raise ValueError(
                    "var(conf) et var(conf/…) ne peuvent pas être mélangés"
                )
            body.append(text[retained : match.start()])
            retained = match.end()
        elif _CONFIG_PREFIX.match(match["body"]):
            raise ValueError(
                "Commentaire de configuration mal formé : "
                "<!-- var(conf/chemin) = valeur -->"
            )
        position = match.end()
    if _CONFIG_START.match(text, position):
        raise ValueError(
            "Le commentaire var(conf/…) ou var(conf) doit être fermé par -->"
        )
    if legacy is None and not variables:
        if required:
            raise ValueError(
                "Le Markdown doit commencer par des commentaires var(conf/…) "
                "(ou un ancien bloc var(conf))"
            )
        return None, text
    body.append(text[retained:])
    return legacy if legacy is not None else _expand(variables), "".join(body)
