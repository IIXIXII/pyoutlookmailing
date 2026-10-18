#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

"""Prepare configuration and HTML independently of Outlook delivery."""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from markupsafe import Markup
from pymdtools import common
from pymdtools.instruction import get_vars_from_md_text

from . import genenv, renderer
from .embedded import split_configuration
from .files import find_file
from .preferences import read_preferences

Configuration = dict[str, Any]
MARKDOWN_EXTENSIONS = {".md", ".markdown", ".mailmd"}
logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
def _merge(
    base: Mapping, override: Mapping, *, concatenate_lists: bool = True
) -> Configuration:
    """Return a deep merge of two mappings without changing either input.

    Nested mappings are merged recursively. Lists are concatenated in base-then-
    override order; other values from override replace the corresponding base
    value. Set concatenate_lists=False when applying user defaults or profiles;
    in that case an override list replaces the inherited list.
    """
    result = deepcopy(dict(base))
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, Mapping):
            result[key] = _merge(
                result[key], value, concatenate_lists=concatenate_lists
            )
        elif (
            concatenate_lists
            and isinstance(result.get(key), list)
            and isinstance(value, list)
        ):
            result[key].extend(deepcopy(value))
        else:
            result[key] = deepcopy(value)
    return result


# -----------------------------------------------------------------------------
def path(*paths: str | os.PathLike) -> str:
    """Join path components in the legacy leaf-first order.

    Args:
        *paths: Leaf name followed by its parent directories. An absolute
            component stops the search; any later components are ignored.

    Returns:
        A normalized path string, which may still be relative and need not
        exist.

    Example:
        ``path("image.png", "img", "/project")`` produces
        ``/project/img/image.png`` on POSIX systems.
    """
    result = Path()
    for part in paths:
        result = Path(part) / result
        if result.is_absolute():
            break
    return os.path.normpath(result)


# -----------------------------------------------------------------------------
def expand_paths(data: Configuration, root: str | os.PathLike) -> Configuration:
    """Return a copy of a paths mapping with absolute path values.

    Args:
        data: Paths mapping whose optional root is relative to the supplied
            root. Nested mappings can define their own roots. Lists contain path
            values.
        root: Base directory for this mapping.

    Returns:
        A new mapping with an absolute root and expanded strings and lists.

    Raises:
        ValueError: A value is neither a path, a list, nor a nested mapping.

    Paths are resolved without checking that the target files exist.
    """
    result = deepcopy(data)
    base = Path(path(result.get("root", "."), root)).resolve()
    result["root"] = str(base)
    for key, value in result.items():
        if isinstance(value, dict):
            result[key] = expand_paths(value, base)
        elif isinstance(value, list):
            result[key] = [
                str(Path(path(item, base)).resolve()) for item in value
            ]
        elif isinstance(value, (str, os.PathLike)):
            result[key] = str(Path(path(value, base)).resolve())
        else:
            raise ValueError(
                f"paths.{key} doit être un chemin ou une liste de chemins"
            )
    return result


# -----------------------------------------------------------------------------
def expand_preferences_paths(
    data: Configuration, root: str | os.PathLike
) -> Configuration:
    """Resolve common paths and each profile's paths without changing inputs.

    Global paths use the preference file's directory and optional paths.root.
    Profile paths inherit that global root unless they specify their own root,
    relative to the preference file. Changing a profile root does not relocate
    paths already defined by the global settings. This also preserves resource
    locations when preferences are imported into a different user directory.
    """
    result = deepcopy(data)
    if "paths" in result:
        result["paths"] = expand_paths(result["paths"], root)
    global_root = result.get("paths", {}).get("root", str(root))
    for profile in result.get("profiles", {}).values():
        if "paths" in profile:
            profile["paths"] = expand_paths(
                {"root": global_root, **profile["paths"]}, root
            )
    return result


# -----------------------------------------------------------------------------
def _read_yaml(filename: Path, active: tuple[Path, ...] = ()) -> Configuration:
    """Load one configuration file and recursively merge its includes.

    The active path stack detects include cycles. Includes are relative to the
    including file, whereas other paths use that file's optional paths.root.
    Markdown extensions require embedded configuration. This helper does not
    load local overrides; read_yaml applies the top-level override afterwards.
    """
    filename = filename.resolve()
    if filename in active:
        raise ValueError(f"Cycle dans les inclusions YAML : {filename}")
    if filename.suffix.lower() in MARKDOWN_EXTENSIONS:
        text = common.get_file_content(filename, encoding="utf-8-sig")
        data, _ = split_configuration(text, required=True)
    else:
        with filename.open(encoding="utf-8-sig") as stream:
            data = yaml.safe_load(stream)
    if not isinstance(data, dict):
        raise ValueError(
            f"La configuration doit être un objet YAML : {filename}"
        )
    paths = data.get("paths", {})
    if not isinstance(paths, dict):
        raise ValueError(f"paths doit être un objet YAML : {filename}")
    includes = paths.get("includes", [])
    if not isinstance(includes, list) or not all(
        isinstance(p, str) for p in includes
    ):
        raise ValueError("paths.includes doit être une liste de fichiers")
    result: Configuration = {}
    for name in includes:
        result = _merge(
            result, _read_yaml(filename.parent / name, (*active, filename))
        )
    if paths:
        own_paths = {k: v for k, v in paths.items() if k != "includes"}
        data["paths"] = expand_paths(own_paths, filename.parent)
    result = _merge(result, data)
    result.setdefault("paths", {})["conf_folder"] = str(filename.parent)
    result["paths"]["conf_filename"] = str(filename)
    return result


# -----------------------------------------------------------------------------
def read_yaml(
    filename: str | os.PathLike,
    *,
    preferences: str | os.PathLike | None = None,
    use_preferences: bool = True,
    profile: str | None = None,
) -> Configuration:
    """Load a configuration, its includes, and its adjacent local override.

    Args:
        filename: YAML file or a .md, .markdown, or .mailmd file with embedded
            configuration. Text is read as UTF-8, accepting an optional BOM.
        preferences: Optional user-preferences file overriding platform lookup
            and PYOUTLOOKMAILING_PREFERENCES. Relative paths use the current
            working directory.
        use_preferences: Load common user defaults when true. False skips both
            preferences and the campaign's profile selector.
        profile: Explicit profile overriding the campaign's top-level profile.

    Returns:
        A new configuration mapping with resolved paths and source metadata.
        Markdown sources use their own body when email.content is omitted.

    Raises:
        ValueError: Configuration is malformed, an include cycle exists, or a
            required embedded configuration is missing.
        OSError: A configuration file cannot be read.
        yaml.YAMLError: YAML syntax is invalid.

    User defaults and an optional profile have lower priority than includes,
    the main file, and its local override. Campaign lists replace common lists;
    lists within the campaign still append. For campaign.conf and campaign.md,
    the override is
    campaign.local.conf. The email body and Excel recipient lists are read later
    by compute_conf.
    """
    filename = Path(filename).resolve()
    result = _read_yaml(filename)
    # A Markdown source shares the existing .local.conf override convention.
    local = filename.with_suffix(
        ".local.conf"
        if filename.suffix.lower() in MARKDOWN_EXTENSIONS
        else ".local" + filename.suffix
    )
    if local.is_file():
        result = _merge(result, _read_yaml(local))
    if not use_preferences and (preferences is not None or profile is not None):
        raise ValueError(
            "Les préférences désactivées ne peuvent pas sélectionner "
            "un fichier ou un profil"
        )
    if use_preferences:
        store, common = read_preferences(preferences)
        common = expand_preferences_paths(common, store.path.parent)
        profiles = common.pop("profiles", {})
        selected = profile if profile is not None else result.get("profile")
        if selected is not None:
            if not isinstance(selected, str) or not selected.strip():
                raise ValueError("profile doit être un nom de profil non vide")
            if selected not in profiles:
                raise ValueError(
                    f"Profil upref inconnu : {selected!r} ({store.path})"
                )
            common = _merge(common, profiles[selected], concatenate_lists=False)
        if common:
            logger.info("Préférences communes : %s", store.path)
            if selected is not None:
                logger.info("Profil : %s", selected)
            result = _merge(common, result, concatenate_lists=False)
    paths = result.setdefault("paths", {})
    paths["conf_folder"] = str(filename.parent)
    paths["conf_filename"] = str(filename)
    paths.setdefault("root", str(filename.parent))
    paths.setdefault("base_search", [str(filename.parent), paths["root"]])
    paths.setdefault("img", str(filename.parent))
    if filename.suffix.lower() in MARKDOWN_EXTENSIONS:
        email = result.setdefault("email", {})
        if not isinstance(email, dict):
            raise ValueError("La section email doit être un objet YAML")
        if "content" not in email or email["content"] == {}:
            email["content"] = {"filename": str(filename)}
    return result


# -----------------------------------------------------------------------------
def load_conf(
    filename: str | os.PathLike,
    folder: str | os.PathLike = ".",
    *,
    preferences: str | os.PathLike | None = None,
    use_preferences: bool = True,
    profile: str | None = None,
) -> Configuration:
    """Find and read a YAML or embedded Markdown configuration.

    Args:
        filename: Absolute filename or a name relative to the search
            directories.
        folder: Additional search directory after the current working directory.
        preferences: Optional common preferences file; see read_yaml.
        use_preferences: Whether to load user defaults and campaign profiles.
        profile: Optional explicit profile taking priority over the campaign.

    Returns:
        The configuration returned by read_yaml, ready for compute_conf.

    Raises:
        FileNotFoundError: No file exists in either root or its conf/mails
            folders.

    Parsing and include errors from read_yaml propagate to the caller.
    """
    return read_yaml(
        find_file(filename, [Path.cwd(), folder], ("", "conf", "mails")),
        preferences=preferences,
        use_preferences=use_preferences,
        profile=profile,
    )


# -----------------------------------------------------------------------------
def default_conf() -> Configuration:
    """Return a fresh copy of the packaged sample configuration.

    The sample can be rendered immediately, uses draft mode, and has no
    recipients. Add recipients before passing a prepared copy to send_email. It
    is not automatically merged into configurations loaded with load_conf.
    """
    return read_yaml(
        Path(__file__).with_name("default.conf"), use_preferences=False
    )


# -----------------------------------------------------------------------------
def _addresses(values: Any, field: str) -> list[str]:
    """Validate, lowercase, trim, and deduplicate a list of email addresses.

    None becomes an empty list. First-occurrence order is preserved. The field
    name is used in ValueError messages; this checks basic syntax, not
    deliverability.
    """
    if values is None:
        return []
    if not isinstance(values, list) or not all(
        isinstance(v, str) for v in values
    ):
        raise ValueError(f"{field}.list doit être une liste d’adresses")
    result = []
    for value in values:
        address = value.strip().lower()
        if not re.fullmatch(r"[^@\s;,<>]+@[^@\s;,<>]+", address):
            raise ValueError(f"Adresse invalide dans {field}.list")
        if address not in result:
            result.append(address)
    return result


# -----------------------------------------------------------------------------
def email_excel_list(xl_filename, xl_column, folders=None) -> list[str]:
    """Read normalized email addresses from the first worksheet of an Excel
    file.

    Args:
        xl_filename: Workbook filename, resolved with find_file.
        xl_column: One column name or a nonempty list of column names.
        folders: Search roots; a missing or empty value uses the working
            directory.

    Returns:
        Unique lowercase addresses in column order, then row order. Blank cells
        and non-string values are ignored.

    Raises:
        FileNotFoundError: The workbook is absent from the roots and excel/xl
            folders.
        ValueError: No columns are selected, a column is missing, or an address
            is invalid.

    Workbook parsing errors from pandas propagate. pandas is imported on demand.
    """
    # Keep pandas unloaded when no Excel recipient source is used.
    # pylint: disable-next=import-outside-toplevel
    import pandas as pd

    filename = find_file(
        xl_filename, folders or [Path.cwd()], ("", "excel", "xl")
    )
    table = pd.read_excel(filename)
    columns = [xl_column] if isinstance(xl_column, str) else xl_column
    if not isinstance(columns, list) or not columns:
        raise ValueError("excel_column_name doit désigner au moins une colonne")
    result = []
    for column in columns:
        if column not in table:
            raise ValueError(f"Colonne Excel introuvable : {column}")
        result.extend(
            v for v in table[column] if isinstance(v, str) and v.strip()
        )
    return _addresses(result, "excel")


# -----------------------------------------------------------------------------
def read_excel_list(conf: Configuration) -> Configuration:
    """Merge Excel addresses into configuration sections in place.

    Each section with excel_file uses excel_column_name and its existing list.
    Manual addresses come first; imported duplicates are removed. Consumed Excel
    keys are deleted after a successful import. Without a column selector, a
    nonempty manual list is used alone; otherwise ValueError is raised.

    Returns:
        The same configuration object. Earlier sections may already be updated
        if a later section fails; compute_conf protects callers by copying
        first.
    """
    for key, section in conf.items():
        if isinstance(section, dict) and "excel_file" in section:
            if "excel_column_name" not in section:
                # Existing campaigns disable the Excel source by commenting
                # its column selector while retaining explicit recipients.
                manual = _addresses(section.get("list"), key)
                if not manual:
                    raise ValueError(
                        f"{key}.excel_column_name est requis "
                        "pour l’import Excel "
                        f"lorsque {key}.list est vide"
                    )
                section["list"] = manual
                continue
            imported = email_excel_list(
                section["excel_file"],
                section["excel_column_name"],
                conf["paths"]["base_search"],
            )
            section["list"] = _addresses(section.get("list"), key)
            section["list"] = list(dict.fromkeys(section["list"] + imported))
            del section["excel_file"], section["excel_column_name"]
    return conf


# -----------------------------------------------------------------------------
def read_content_filename(conf: Configuration) -> Configuration:
    """Load Markdown content and apply its ordinary variables in place.

    For each top-level section with a content mapping, replace filename with
    txt, strip leading embedded configuration, then merge ordinary var(...)
    values into the section. Content files use paths.base_search and conf/files
    subfolders. The selected configuration is never replaced by configuration
    inside the body.

    Returns:
        The same configuration object.

    Raises:
        ValueError: A Markdown variable attempts to replace content, html_body,
            or attachments. Embedded configuration parsing errors also
            propagate.
    """
    for section in conf.values():
        if not isinstance(section, dict) or not isinstance(
            section.get("content"), dict
        ):
            continue
        content = section["content"]
        if "filename" in content:
            filename = find_file(
                content["filename"],
                conf["paths"]["base_search"],
                ("", "conf", "files"),
            )
            content["txt"] = common.get_file_content(
                filename, encoding="utf-8-sig"
            )
            del content["filename"]
        if "txt" in content:
            # Configuration is selected by load_conf, never by the email body.
            # Remove it even when a legacy .conf points to this Markdown file.
            _, content["txt"] = split_configuration(content["txt"])
            variables = get_vars_from_md_text(content["txt"])
            if variables.keys() & {"content", "html_body", "attachments"}:
                raise ValueError(
                    "Une variable Markdown ne peut pas remplacer "
                    "content, html_body ou attachments"
                )
            section.update(variables)
    return conf


# -----------------------------------------------------------------------------
def md2html(md_content: str, env, context: Configuration) -> str:
    """Render a Markdown fragment with the configured Jinja environment.

    Args:
        md_content: Authored Markdown, optionally starting with configuration
            comments.
        env: GenerationEnvironment providing templates and resource paths.
        context: Email variables, including an optional model selector.

    Returns:
        HTML for the body fragment, before wrapping it in the email template.

    Leading configuration is removed. Paths come from env.template_conf.
    Authored raw HTML is preserved; this function is not a sanitizer for
    untrusted content.
    """
    _, md_content = split_configuration(md_content)
    context = {**context, "paths": env.template_conf["paths"]}
    return renderer.create_markdown(env.jinja_env, context)(md_content)


# -----------------------------------------------------------------------------
def txt2html(conf: Configuration, env) -> Configuration:
    """Replace content mappings containing txt with rendered HTML in place.

    Each top-level section supplies its own renderer context. Return the same
    configuration object; template and Markdown errors propagate from md2html.
    """
    for section in conf.values():
        if isinstance(section, dict) and isinstance(
            section.get("content"), dict
        ):
            if "txt" in section["content"]:
                section["content"] = md2html(
                    section["content"]["txt"], env, section
                )
    return conf


# -----------------------------------------------------------------------------
def htmlbody(conf: Configuration, env) -> Configuration:
    """Render the outer email template into email.html_body in place.

    The prepared email.content fragment is marked as trusted generated HTML.
    Other email fields form the Jinja context. Return the same configuration.
    """
    email = conf["email"]
    context = {**email, "content": Markup(email["content"])}
    email["html_body"] = env.jinja_env.get_template(email["template"]).render(
        context
    )
    return conf


# -----------------------------------------------------------------------------
def compute_conf(conf: Configuration, cmd_line_args=None) -> Configuration:
    """Prepare a configuration copy for preview or Outlook delivery.

    Args:
        conf: Configuration containing an email section and optional recipient,
            path, and delivery settings. The input is not modified.
        cmd_line_args: Optional object with conf_filename and send_mail
            attributes. send_mail accepts the CLI values yes, no, or conf;
            yes/no override really_send, while conf preserves it.

    Returns:
        A deep copy with defaults, imported Excel lists, Markdown variables,
        rendered email.content, and the complete email.html_body string.

    Raises:
        ValueError: Required email fields, content, or delivery flags are
            invalid.
        OSError: A source file cannot be read.

    Reads configuration resources and templates but writes no files and never
    opens Outlook. Rendering and parsing exceptions propagate. Recipient
    exclusions, attachment existence, and sender-account selection are checked
    during delivery.
    """
    conf = deepcopy(conf)
    if not isinstance(conf.get("email"), dict):
        raise ValueError("La section email est requise")
    paths = conf.setdefault("paths", {})
    paths.setdefault("conf_folder", str(Path.cwd()))
    paths.setdefault("base_search", [paths["conf_folder"]])
    paths.setdefault("img", paths["conf_folder"])
    email = conf["email"]
    email.setdefault("template", "email.html")
    if "content" not in email or email["content"] == {}:
        source = getattr(cmd_line_args, "conf_filename", None) or paths.get(
            "conf_filename"
        )
        if not source:
            raise ValueError(
                "email.content ou un fichier de configuration est requis"
            )
        email["content"] = {"filename": str(Path(source).with_suffix(".md"))}
    send = getattr(cmd_line_args, "send_mail", "conf")
    if send != "conf":
        conf["really_send"] = send == "yes"
    conf.setdefault("really_send", False)
    if not isinstance(conf["really_send"], bool):
        raise ValueError(
            "really_send doit être un booléen (true ou false, sans guillemets)"
        )
    read_excel_list(conf)
    read_content_filename(conf)
    if (
        not isinstance(email.get("subject"), str)
        or not email["subject"].strip()
    ):
        raise ValueError(
            "email.subject est requis (configuration ou variable Markdown)"
        )
    env = genenv.GenerationEnvironment(conf)
    txt2html(conf, env)
    if not isinstance(email.get("content"), str):
        raise ValueError("email.content doit contenir txt ou filename")
    return htmlbody(conf, env)


# -----------------------------------------------------------------------------
def new_email(conf):
    """Create an Outlook mail item through the delivery adapter.

    This compatibility wrapper imports outlook.new_email on demand and is the
    factory used by send_email. Calling it accesses COM and may start Outlook;
    the returned item has not yet been saved or sent.
    """
    # Keep the Outlook adapter unloaded until a mail item is requested.
    # pylint: disable-next=import-outside-toplevel
    from .outlook import new_email as create

    return create(conf)


# -----------------------------------------------------------------------------
def send_email(conf: Configuration) -> Configuration:
    """Save drafts or send messages using a prepared configuration.

    Args:
        conf: Output from compute_conf, including email.subject and
            email.html_body. really_send defaults to False; True sends
            immediately.

    Returns:
        The original, unmodified configuration object.

    Raises:
        ValueError: Recipients, delivery flags, sender account, or email fields
            are invalid.
        FileNotFoundError: An attachment or CID image is missing.
        RuntimeError: The Outlook COM dependency is unavailable.

    Outlook errors propagate. Individual deliveries are sequential: a later
    failure does not undo earlier saves or sends, and no automatic retry is
    attempted.
    """
    # HTML preparation does not need the Outlook delivery adapter.
    # pylint: disable-next=import-outside-toplevel
    from .outlook import deliver

    return deliver(conf, mail_factory=new_email)
