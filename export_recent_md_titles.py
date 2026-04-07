#!/usr/bin/env python3
"""
Export Evernote notes updated in the last N days whose title matches a fixed string
(default: "md") to Markdown files under an output directory.

Authentication: set EVERNOTE_TOKEN or pass --token. Obtain a developer token from:
  Production: https://www.evernote.com/api/DeveloperToken.action
  Sandbox:    https://sandbox.evernote.com/api/DeveloperToken.action

Example:
  export EVERNOTE_TOKEN="..."
  python export_recent_md_titles.py ./output --days 7 --title md
"""

from __future__ import annotations

import sys

# Evernote SDK imports oauth2, which falls back to distutils (removed in Python 3.12).
if sys.version_info >= (3, 12):
    import setuptools  # noqa: F401

import argparse
import os
import re
import ssl
from typing import Iterable


def _configure_ssl_default_context() -> None:
    """Point default HTTPS verification at certifi's CA bundle when env has no CA path.

    Thrift uses http.client.HTTPSConnection, which calls ssl._create_default_https_context.
    On many macOS Python installs the default store is empty → CERTIFICATE_VERIFY_FAILED.
    """
    if os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE"):
        return
    try:
        import certifi
    except ImportError:
        return

    def _ctx() -> ssl.SSLContext:
        return ssl.create_default_context(cafile=certifi.where())

    ssl._create_default_https_context = _ctx


_configure_ssl_default_context()

import html2text
from bs4 import BeautifulSoup

# evernote3 client uses inspect.getargspec (removed in Python 3.11).
import inspect
from collections import namedtuple

if not hasattr(inspect, "getargspec"):
    _ArgSpec = namedtuple("ArgSpec", "args varargs keywords defaults")

    def getargspec(func):  # type: ignore[no-redef]
        fs = inspect.getfullargspec(func)
        return _ArgSpec(fs.args, fs.varargs, fs.varkw, fs.defaults)

    inspect.getargspec = getargspec  # type: ignore[attr-defined]

from evernote.api.client import EvernoteClient
from evernote.edam.notestore.ttypes import NoteFilter, NotesMetadataResultSpec
from evernote.edam.error.ttypes import EDAMUserException, EDAMSystemException


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Export Evernote notes (title match, recently updated) to .md files "
            "named from the first line of each note."
        )
    )
    p.add_argument(
        "output_dir",
        help="Directory to write .md files (created if missing).",
    )
    p.add_argument(
        "--token",
        default=os.environ.get("EVERNOTE_TOKEN", ""),
        help="Evernote developer token (or set EVERNOTE_TOKEN).",
    )
    p.add_argument(
        "--days",
        type=int,
        default=7,
        help="Only notes updated within this many days (Evernote search: updated:day-N).",
    )
    p.add_argument(
        "--title",
        default="md",
        help='Evernote note title must match this exactly (case-insensitive). Default: "md".',
    )
    p.add_argument(
        "--sandbox",
        action="store_true",
        help="Use Evernote sandbox (sandbox.evernote.com).",
    )
    p.add_argument(
        "--china",
        action="store_true",
        help="Use Yinxiang Biji (app.yinxiang.com) instead of Evernote International.",
    )
    p.add_argument(
        "--page-size",
        type=int,
        default=50,
        help="Notes per findNotesMetadata page (max 250).",
    )
    p.add_argument(
        "--on-conflict",
        choices=("ask", "overwrite", "keep-both", "skip"),
        default="ask",
        help=(
            "If the target .md file already exists with different content: "
            "ask (TTY only; else keep-both), overwrite, keep-both (new _N name), or skip."
        ),
    )
    p.add_argument(
        "--no-rename-after-export",
        action="store_true",
        help="Do not change the Evernote note title after a successful .md write.",
    )
    p.add_argument(
        "--post-export-title",
        default="filed-md",
        help='Evernote title to set after a successful export (default: "filed-md").',
    )
    return p.parse_args()


def _build_search_words(days: int) -> str:
    if days < 0:
        raise ValueError("--days must be non-negative")
    if days == 0:
        return "updated:day"
    return f"updated:day-{days}"


def enml_to_markdown(enml: str) -> str:
    """Convert note ENML to a reasonable Markdown/plain-text representation."""
    soup = BeautifulSoup(enml, "xml")
    root = soup.find("en-note")
    if root is None:
        return ""

    for tag in root.find_all("en-media"):
        mime = tag.get("type", "attachment")
        tag.replace_with(f"[embedded {mime}]")

    for tag in root.find_all("en-crypt"):
        tag.replace_with("[encrypted content]")

    for tag in root.find_all("en-todo"):
        checked = tag.get("checked", "").lower() == "true"
        box = "[x]" if checked else "[ ]"
        tag.replace_with(f"- {box} ")

    for br in root.find_all("br"):
        br.replace_with("\n")

    inner = root.decode_contents()
    h = html2text.HTML2Text()
    h.body_width = 0
    h.unicode_snob = True
    h.ignore_images = False
    md = h.handle(inner).strip()
    return md + ("\n" if md else "")


def first_line_to_basename(markdown: str, note_guid: str, max_len: int = 120) -> str:
    """Derive a filesystem-safe base name (no extension) from the first non-empty line."""
    for line in markdown.splitlines():
        s = line.strip()
        if not s:
            continue
        s = re.sub(r"^#+\s*", "", s)
        s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", s)
        s = re.sub(r"\s+", "-", s)
        s = s.strip(".-_")
        if not s:
            continue
        if len(s) > max_len:
            s = s[:max_len].rstrip("-")
        return s
    return f"untitled-{note_guid[:8]}"


def _normalize_text(s: str) -> str:
    return s.replace("\r\n", "\n").replace("\r", "\n")


def _read_utf8(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        return f.read()


def _first_unused_name(base: str, ext: str, used: set[str]) -> str:
    """Next filename base[_n].ext not reserved in this run (in-session collisions)."""
    n = 0
    while True:
        name = f"{base}{ext}" if n == 0 else f"{base}_{n}{ext}"
        if name not in used:
            return name
        n += 1


def _first_free_name_on_disk(dir_path: str, base: str, ext: str, used: set[str]) -> tuple[str, str]:
    """First base[_n].ext not in used and not on disk (for keep-both)."""
    n = 0
    while True:
        name = f"{base}{ext}" if n == 0 else f"{base}_{n}{ext}"
        full = os.path.join(dir_path, name)
        if name not in used and not os.path.exists(full):
            return name, full
        n += 1


def _rename_evernote_note_title(note_store, guid: str, new_title: str) -> None:
    """Set the note's title on the server (requires full note content for updateNote)."""
    n = note_store.getNote(guid, True, False, False, False)
    n.title = new_title
    note_store.updateNote(n)


def _maybe_rename_after_export(
    note_store,
    guid: str,
    post_title: str,
    no_rename: bool,
) -> None:
    if no_rename:
        return
    try:
        _rename_evernote_note_title(note_store, guid, post_title)
    except (EDAMUserException, EDAMSystemException) as e:
        print(f"Warning: could not rename Evernote note {guid}: {e}", file=sys.stderr)


def _resolve_conflict_action(on_conflict: str, path: str) -> str:
    """Return overwrite | keep-both | skip."""
    if on_conflict != "ask":
        return on_conflict
    if not sys.stdin.isatty():
        print(
            f"Output file differs (non-interactive); keeping both: {path}",
            file=sys.stderr,
        )
        return "keep-both"
    while True:
        r = input(
            f"File exists with different content:\n  {path}\n"
            "[o]verwrite / [k]eep both (new name) / [s]kip? [o/k/s]: "
        ).strip().lower()
        if r in ("o", "overwrite"):
            return "overwrite"
        if r in ("k", "keep", "keep-both", "b"):
            return "keep-both"
        if r in ("s", "skip", "n", "q"):
            return "skip"
        print("Please enter o, k, or s.", file=sys.stderr)


def iter_note_guids(
    note_store,
    words: str,
    page_size: int,
    total_out: list[int | None],
) -> Iterable[tuple[str, str]]:
    """Yield (guid, title) for all notes matching the search words.

    On the first API response, sets total_out[0] to totalNotes (search hit count).
    """
    nf = NoteFilter()
    nf.words = words

    spec = NotesMetadataResultSpec()
    spec.includeTitle = True
    spec.includeUpdated = True

    offset = 0
    while True:
        batch = note_store.findNotesMetadata(nf, offset, page_size, spec)
        if total_out[0] is None:
            total_out[0] = int(batch.totalNotes)
        for meta in batch.notes:
            yield meta.guid, meta.title or ""
        offset += len(batch.notes)
        if not batch.notes or offset >= batch.totalNotes:
            break


def main() -> int:
    args = _parse_args()
    if not args.token.strip():
        print("Error: missing API token. Set EVERNOTE_TOKEN or pass --token.", file=sys.stderr)
        if args.china:
            print(
                "  China (印象笔记 / Yinxiang): "
                "https://app.yinxiang.com/api/DeveloperToken.action",
                file=sys.stderr,
            )
        elif args.sandbox:
            print(
                "  Sandbox: https://sandbox.evernote.com/api/DeveloperToken.action",
                file=sys.stderr,
            )
        else:
            print(
                "  International: https://www.evernote.com/api/DeveloperToken.action",
                file=sys.stderr,
            )
        return 1

    out_dir = os.path.abspath(args.output_dir)
    os.makedirs(out_dir, exist_ok=True)

    client = EvernoteClient(
        token=args.token.strip(),
        sandbox=args.sandbox,
        china=args.china,
    )
    note_store = client.get_note_store()

    search = _build_search_words(args.days)
    title_want = args.title.strip().casefold()
    if not title_want:
        print("Error: --title must not be empty.", file=sys.stderr)
        return 1

    post_title = (args.post_export_title or "").strip()
    if not post_title and not args.no_rename_after_export:
        print("Error: --post-export-title must not be empty (or use --no-rename-after-export).", file=sys.stderr)
        return 1

    page = max(1, min(args.page_size, 250))
    exported = 0
    skipped_title = 0
    skipped_unchanged = 0
    skipped_conflict = 0
    skipped_read_error = 0
    total_out: list[int | None] = [None]
    used_names: set[str] = set()

    try:
        for guid, title in iter_note_guids(note_store, search, page, total_out):
            if (title or "").strip().casefold() != title_want:
                skipped_title += 1
                continue
            enml = note_store.getNoteContent(guid)
            md = enml_to_markdown(enml)
            base = first_line_to_basename(md, guid)
            name = _first_unused_name(base, ".md", used_names)
            path = os.path.join(out_dir, name)

            if os.path.exists(path):
                try:
                    existing = _read_utf8(path)
                except OSError as e:
                    print(f"Could not read {path}: {e}", file=sys.stderr)
                    skipped_read_error += 1
                    continue
                if _normalize_text(existing) == _normalize_text(md):
                    print(f"skip (unchanged): {path}")
                    _maybe_rename_after_export(
                        note_store, guid, post_title, args.no_rename_after_export
                    )
                    skipped_unchanged += 1
                    continue

                action = _resolve_conflict_action(args.on_conflict, path)
                if action == "skip":
                    print(f"skip: {path}")
                    skipped_conflict += 1
                    continue
                if action == "keep-both":
                    name, path = _first_free_name_on_disk(out_dir, base, ".md", used_names)
                # overwrite: keep path as-is

            used_names.add(os.path.basename(path))
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(md)
            print(path)
            exported += 1

            _maybe_rename_after_export(
                note_store, guid, post_title, args.no_rename_after_export
            )
    except (EDAMUserException, EDAMSystemException) as e:
        print(f"Evernote API error: {e}", file=sys.stderr)
        return 1

    total_notes = total_out[0] if total_out[0] is not None else 0
    skipped = skipped_title + skipped_unchanged + skipped_conflict + skipped_read_error
    print(
        f"Summary: total notes (search)={total_notes}; "
        f"skipped={skipped} "
        f"(title mismatch={skipped_title}, unchanged={skipped_unchanged}, "
        f"conflict skip={skipped_conflict}, read error={skipped_read_error}); "
        f"new={exported}"
    )

    if exported == 0:
        print(
            f"No notes matched title={args.title!r} with search {search!r}.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
