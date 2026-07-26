from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

SCHEMA_VERSION = 1
DEFAULT_MANIFEST = Path("docs/document-pairs.json")

_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_EXPLICIT_ANCHOR_RE = re.compile(r"""<a\s+(?:name|id)=["']([^"']+)["'][^>]*>""", re.IGNORECASE)
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_INLINE_CODE_RE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
_BOLD_RE = re.compile(r"(?<!\*)\*\*([^*\n]+)\*\*(?!\*)")
_INLINE_LINK_RE = re.compile(r"!?\[[^\]\n]*\]\((?P<target><[^>\n]+>|[^)\n]+)\)")
_REFERENCE_TARGET_RE = re.compile(r"^\s*\[[^\]\n]+\]:\s*(?P<target><[^>\n]+>|\S+)", re.MULTILINE)
_URL_RE = re.compile(r"""https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+""")
_ENGLISH_WORD_RE = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")
_MIN_CJK_PER_ENGLISH_WORD = 0.15
_LANGUAGE_NAME_TERMS = {"English", "Simplified Chinese", "英文", "简体中文"}


@dataclass(frozen=True)
class DocumentPair:
    en: str
    zh_cn: str


@dataclass(frozen=True)
class LinkTarget:
    target: str
    line: int


@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    detail: str
    line: int | None = None

    def as_dict(self) -> dict[str, str | int]:
        result: dict[str, str | int] = {"code": self.code, "path": self.path, "detail": self.detail}
        if self.line is not None:
            result["line"] = self.line
        return result


def load_pairs(manifest_path: Path) -> list[DocumentPair]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        msg = f"unsupported documentation-pair schema: {payload.get('schema_version')!r}"
        raise ValueError(msg)
    raw_pairs = payload.get("pairs")
    if not isinstance(raw_pairs, list):
        msg = "documentation-pair manifest must contain a pairs list"
        raise ValueError(msg)

    pairs: list[DocumentPair] = []
    for index, raw_pair in enumerate(raw_pairs):
        if not isinstance(raw_pair, dict):
            msg = f"documentation pair {index} must be an object"
            raise ValueError(msg)
        en = raw_pair.get("en")
        zh_cn = raw_pair.get("zh_CN")
        if not isinstance(en, str) or not isinstance(zh_cn, str):
            msg = f"documentation pair {index} must contain string en and zh_CN paths"
            raise ValueError(msg)
        pairs.append(DocumentPair(en=en, zh_cn=zh_cn))
    return pairs


def discover_markdown_paths(root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "*.md"],
        check=True,
        capture_output=True,
    )
    paths = {path.decode("utf-8").replace("\\", "/") for path in result.stdout.split(b"\0") if path}
    return {path for path in paths if (root / path).is_file()}


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _clean_link_target(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        return target[1:-1]
    return target.split(maxsplit=1)[0]


def _link_targets(text: str) -> list[LinkTarget]:
    targets = [
        LinkTarget(_clean_link_target(match.group("target")), _line_number(text, match.start()))
        for match in _INLINE_LINK_RE.finditer(text)
    ]
    targets.extend(
        LinkTarget(_clean_link_target(match.group("target")), _line_number(text, match.start()))
        for match in _REFERENCE_TARGET_RE.finditer(text)
    )
    return targets


def _trim_external_url(url: str) -> str:
    url = url.rstrip(".,;:!?")
    while url.endswith(")") and url.count("(") < url.count(")"):
        url = url[:-1]
    return url


def _external_urls(text: str) -> Counter[str]:
    urls: list[str] = []
    for match in _URL_RE.finditer(text):
        if match.end() < len(text) and text[match.end()] == "<":
            continue
        urls.append(_trim_external_url(match.group()))
    return Counter(urls)


def _visible_lines(text: str) -> list[str]:
    result: list[str] = []
    in_fence = False
    fence_marker = ""
    for line in text.splitlines():
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if not in_fence:
                in_fence = True
                fence_marker = marker[0]
            elif marker[0] == fence_marker:
                in_fence = False
            continue
        if not in_fence:
            result.append(line)
    return result


def _visible_text_with_line_numbers(text: str) -> str:
    result: list[str] = []
    in_fence = False
    fence_marker = ""
    for line in text.splitlines():
        fence_match = _FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if not in_fence:
                in_fence = True
                fence_marker = marker[0]
            elif marker[0] == fence_marker:
                in_fence = False
            result.append("")
        elif in_fence:
            result.append("")
        else:
            result.append(line)
    return "\n".join(result)


def _prose_language_counts(en_text: str, zh_text: str) -> tuple[int, int, int]:
    def prose(text: str) -> str:
        visible = "\n".join(_visible_lines(text))
        visible = _INLINE_CODE_RE.sub(" ", visible)
        visible = _URL_RE.sub(" ", visible)
        return re.sub(r"<[^>]+>", " ", visible)

    english_words = len(_ENGLISH_WORD_RE.findall(prose(en_text)))
    chinese_characters = len(_CJK_RE.findall(prose(zh_text)))
    minimum_chinese = max(4, int(english_words * _MIN_CJK_PER_ENGLISH_WORD + 0.999999))
    return english_words, chinese_characters, minimum_chinese


def _heading_levels(text: str) -> tuple[int, ...]:
    return tuple(len(match.group(1)) for line in _visible_lines(text) if (match := _HEADING_RE.match(line)))


def _fenced_code_semantics(text: str) -> tuple[str, ...]:
    blocks: list[str] = []
    current: list[str] | None = None
    fence_marker = ""
    for line in text.splitlines():
        fence_match = _FENCE_RE.match(line)
        if current is None and fence_match:
            fence_marker = fence_match.group(1)[0]
            current = [line.lstrip()[3:]]
        elif current is not None and fence_match and fence_match.group(1)[0] == fence_marker:
            blocks.append("\n".join(current))
            current = None
            fence_marker = ""
        elif current is not None:
            if line.lstrip().startswith("#"):
                continue
            current.append(re.sub(r"\s+#.*$", "", line).rstrip())
    return tuple(blocks)


def _github_slug(value: str) -> str:
    value = re.sub(r"!?\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"<[^>]+>", "", value)
    value = value.replace("`", "").replace("*", "")
    value = value.casefold()
    value = "".join(character for character in value if character.isalnum() or character in {" ", "-", "_"})
    return re.sub(r"\s", "-", value.strip())


def _anchors(text: str) -> set[str]:
    anchors = {match.group(1) for match in _EXPLICIT_ANCHOR_RE.finditer(text)}
    slug_counts: Counter[str] = Counter()
    for line in _visible_lines(text):
        match = _HEADING_RE.match(line)
        if not match:
            continue
        slug = _github_slug(match.group(2))
        count = slug_counts[slug]
        slug_counts[slug] += 1
        anchors.add(slug if count == 0 else f"{slug}-{count}")
    return anchors


def _duplicate_explicit_anchors(text: str) -> set[str]:
    anchors = Counter(match.group(1) for match in _EXPLICIT_ANCHOR_RE.finditer(text))
    return {anchor for anchor, count in anchors.items() if count > 1}


def _is_external(target: str) -> bool:
    scheme = urlsplit(target).scheme.casefold()
    return scheme in {"http", "https", "mailto"}


def _resolve_local_target(root: Path, source: str, target: str) -> tuple[Path, str] | None:
    if _is_external(target):
        return None
    split = urlsplit(target)
    if not split.path:
        return root / source, unquote(split.fragment)
    if split.path.startswith("/"):
        return None
    path = unquote(split.path)
    resolved = (root / source).parent.joinpath(path).resolve()
    return resolved, unquote(split.fragment)


def _repo_relative(root: Path, path: Path) -> str | None:
    try:
        return path.relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def _normalized_local_links(root: Path, source: str, text: str, pair_ids: dict[str, int]) -> Counter[str]:
    normalized: list[str] = []
    for link in _link_targets(text):
        if _is_external(link.target):
            continue
        resolved = _resolve_local_target(root, source, link.target)
        if resolved is None:
            normalized.append(f"invalid:{link.target}")
            continue
        path, fragment = resolved
        repo_path = _repo_relative(root, path)
        if repo_path is None:
            normalized.append(f"outside:{link.target}")
        elif repo_path in pair_ids:
            normalized.append(f"doc-pair:{pair_ids[repo_path]}#{fragment}")
        else:
            normalized.append(f"path:{repo_path}#{fragment}")
    return Counter(normalized)


def _strip_ui_icon(value: str) -> str:
    return re.sub(r"^[^A-Za-z0-9\u3400-\u9fff]+", "", value).strip()


def _ui_term_lookup(root: Path) -> dict[str, tuple[str, str]]:
    i18n_path = root / "src/gui/i18n.py"
    if not i18n_path.is_file():
        return {}
    module = ast.parse(i18n_path.read_text(encoding="utf-8"), filename=str(i18n_path))
    translations: dict[str, str] = {}
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "_ZH_CN_TEXT" for target in node.targets):
            continue
        payload = ast.literal_eval(node.value)
        if isinstance(payload, dict):
            translations = {
                source: translated
                for source, translated in payload.items()
                if isinstance(source, str) and isinstance(translated, str)
            }
        break

    lookup: dict[str, tuple[str, str]] = {}
    for source, translated in translations.items():
        pair = (source, translated)
        for value in pair:
            lookup[value] = pair
            stripped = _strip_ui_icon(value)
            if stripped:
                lookup[stripped] = (_strip_ui_icon(source), _strip_ui_icon(translated))
    return lookup


def _ui_alternatives(value: str, lookup: dict[str, tuple[str, str]]) -> set[str]:
    if value in _LANGUAGE_NAME_TERMS:
        return set()
    if value in lookup:
        return set(lookup[value])
    parts = value.split(" > ")
    if len(parts) < 2 or any(part not in lookup for part in parts):
        return set()
    pairs = [lookup[part] for part in parts]
    return {" > ".join(pair[0] for pair in pairs), " > ".join(pair[1] for pair in pairs)}


def _path_alternatives(value: str, pairs: list[DocumentPair]) -> set[str]:
    alternatives = {value}
    for pair in pairs:
        members = (pair.en, pair.zh_cn, Path(pair.en).name, Path(pair.zh_cn).name)
        for member in members:
            if value.endswith(member):
                prefix = value[: -len(member)]
                alternatives.update(prefix + candidate for candidate in members)
    return alternatives


def _protected_terms(
    text: str, pairs: list[DocumentPair], ui_lookup: dict[str, tuple[str, str]]
) -> list[tuple[str, int, set[str]]]:
    visible = _visible_text_with_line_numbers(text)
    terms: list[tuple[str, int, set[str]]] = []
    for pattern, allow_machine_terms in ((_INLINE_CODE_RE, True), (_BOLD_RE, False)):
        for match in pattern.finditer(visible):
            value = match.group(1).strip()
            alternatives = _ui_alternatives(value, ui_lookup)
            machine_term = allow_machine_terms and (
                (value.isascii() and not re.search(r"\s", value) and bool(re.search(r"[A-Za-z0-9]", value)))
                or bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*\s*[:=]\s*\S+", value))
            )
            if not alternatives and not machine_term:
                continue
            terms.append((value, _line_number(visible, match.start()), alternatives | _path_alternatives(value, pairs)))
    return terms


def check_documentation(
    root: Path, manifest_path: Path | None = None, markdown_paths: set[str] | None = None
) -> list[Finding]:
    root = root.resolve()
    manifest_path = manifest_path or root / DEFAULT_MANIFEST
    pairs = load_pairs(manifest_path)
    markdown_paths = markdown_paths if markdown_paths is not None else discover_markdown_paths(root)
    findings: list[Finding] = []

    pair_ids: dict[str, int] = {}
    for pair_id, pair in enumerate(pairs):
        for language, path in (("en", pair.en), ("zh_CN", pair.zh_cn)):
            if path in pair_ids:
                findings.append(Finding("duplicate_pair_member", path, f"listed more than once ({language})"))
            pair_ids[path] = pair_id

    declared = set(pair_ids)
    findings.extend(
        Finding("unpaired_document", path, "tracked Markdown is missing from document-pairs.json")
        for path in sorted(markdown_paths - declared)
    )
    findings.extend(
        Finding("missing_document", path, "declared documentation counterpart does not exist")
        for path in sorted(declared - markdown_paths)
    )

    texts: dict[str, str] = {}
    for path in sorted(declared & markdown_paths):
        try:
            texts[path] = (root / path).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            findings.append(Finding("unreadable_document", path, str(error)))

    ui_lookup = _ui_term_lookup(root)
    for pair in pairs:
        if pair.en not in texts or pair.zh_cn not in texts:
            continue
        en_text = texts[pair.en]
        zh_text = texts[pair.zh_cn]

        english_words, chinese_characters, minimum_chinese = _prose_language_counts(en_text, zh_text)
        if chinese_characters < minimum_chinese:
            findings.append(
                Finding(
                    "insufficient_chinese_text",
                    pair.zh_cn,
                    (
                        f"Chinese counterpart has {chinese_characters} CJK prose characters; "
                        f"at least {minimum_chinese} are required for {english_words} English prose words"
                    ),
                )
            )

        en_targets = _link_targets(en_text)
        zh_targets = _link_targets(zh_text)
        if not any(
            (_repo_relative(root, resolved[0]) if resolved else None) == pair.zh_cn
            for link in en_targets
            if (resolved := _resolve_local_target(root, pair.en, link.target))
        ):
            findings.append(Finding("missing_language_link", pair.en, f"does not link to {pair.zh_cn}"))
        if not any(
            (_repo_relative(root, resolved[0]) if resolved else None) == pair.en
            for link in zh_targets
            if (resolved := _resolve_local_target(root, pair.zh_cn, link.target))
        ):
            findings.append(Finding("missing_language_link", pair.zh_cn, f"does not link to {pair.en}"))

        en_headings = _heading_levels(en_text)
        zh_headings = _heading_levels(zh_text)
        if en_headings != zh_headings:
            findings.append(
                Finding(
                    "heading_structure_mismatch",
                    pair.zh_cn,
                    f"heading levels differ from {pair.en}: {zh_headings!r} != {en_headings!r}",
                )
            )

        if _fenced_code_semantics(en_text) != _fenced_code_semantics(zh_text):
            findings.append(
                Finding("code_block_mismatch", pair.zh_cn, f"non-comment fenced code differs from {pair.en}")
            )

        en_visible = "\n".join(_visible_lines(en_text))
        zh_visible = "\n".join(_visible_lines(zh_text))
        for source_path, target_path, source_text, target_text in (
            (pair.en, pair.zh_cn, en_text, zh_visible),
            (pair.zh_cn, pair.en, zh_text, en_visible),
        ):
            for value, line, alternatives in _protected_terms(source_text, pairs, ui_lookup):
                if not any(alternative in target_text for alternative in alternatives):
                    findings.append(
                        Finding(
                            "protected_term_mismatch",
                            source_path,
                            f"{value!r} has no code/UI-label counterpart in {target_path}",
                            line,
                        )
                    )

        en_urls = _external_urls(en_text)
        zh_urls = _external_urls(zh_text)
        if en_urls != zh_urls:
            findings.append(
                Finding(
                    "external_url_mismatch",
                    pair.zh_cn,
                    f"external URLs differ from {pair.en}: zh={dict(zh_urls)!r}, en={dict(en_urls)!r}",
                )
            )

        en_links = _normalized_local_links(root, pair.en, en_text, pair_ids)
        zh_links = _normalized_local_links(root, pair.zh_cn, zh_text, pair_ids)
        if en_links != zh_links:
            findings.append(
                Finding(
                    "local_link_mismatch",
                    pair.zh_cn,
                    f"local links differ from {pair.en}: zh={dict(zh_links)!r}, en={dict(en_links)!r}",
                )
            )

        for path, text in ((pair.en, en_text), (pair.zh_cn, zh_text)):
            findings.extend(
                Finding("duplicate_anchor", path, f"duplicate explicit anchor: {anchor}")
                for anchor in sorted(_duplicate_explicit_anchors(text))
            )
            for link in _link_targets(text):
                if _is_external(link.target):
                    continue
                if urlsplit(link.target).path.startswith("/"):
                    findings.append(
                        Finding(
                            "repository_absolute_link", path, f"repository link starts with /: {link.target}", link.line
                        )
                    )
                    continue
                resolved = _resolve_local_target(root, path, link.target)
                if resolved is None:
                    continue
                target_path, fragment = resolved
                repo_path = _repo_relative(root, target_path)
                if repo_path is None:
                    findings.append(Finding("link_outside_repository", path, link.target, link.line))
                    continue
                if not target_path.exists():
                    findings.append(Finding("missing_link_target", path, link.target, link.line))
                    continue
                if fragment and target_path.suffix.casefold() == ".md":
                    target_text = texts.get(repo_path)
                    if target_text is None:
                        try:
                            target_text = target_path.read_text(encoding="utf-8")
                        except OSError, UnicodeError:
                            continue
                    if fragment not in _anchors(target_text):
                        findings.append(Finding("missing_anchor", path, link.target, link.line))

    return sorted(findings, key=lambda finding: (finding.path, finding.line or 0, finding.code))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate bilingual Markdown pairs and their links.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--manifest", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    root = args.root.resolve()
    manifest = args.manifest
    if manifest is not None and not manifest.is_absolute():
        manifest = root / manifest
    try:
        findings = check_documentation(root, manifest)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False, indent=2))
        return 2

    print(
        json.dumps(
            {
                "ok": not findings,
                "manifest": str((manifest or root / DEFAULT_MANIFEST).relative_to(root)),
                "findings": [finding.as_dict() for finding in findings],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
