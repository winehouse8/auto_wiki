#!/usr/bin/env python3
"""Living Wiki 사람이 읽는 문서의 한국어 기본 계약을 검사한다."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path


HANGUL_RE = re.compile(r"[가-힣]")
LATIN_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")
ID_ONLY_RE = re.compile(
    r"(?:RFC|CLM|SRC|ADM|ACTOR|CMP|COL|MFB|MFR|RUN|REV|SPEC|ADR|SNP|EVT|ACT|PLAN|CAND|LCT|EXT)(?:-[A-Z0-9.]+)+",
    re.IGNORECASE,
)
FENCE_RE = re.compile(r"^\s*(```+|~~~+)\s*([A-Za-z0-9_+-]*)\s*$")
FRONTMATTER_FIELD_RE = re.compile(
    r"^(title|description|summary|name|label|subtitle|abstract|caption|alt|rationale|note|notes):\s*(.*)$"
)
INLINE_CODE_RE = re.compile(r"`[^`]*`")
URL_RE = re.compile(r"https?://\S+")
LINK_TARGET_RE = re.compile(r"\]\([^)]*\)")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]*)\)")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}")
EXCLUDED_TOP_LEVEL = {".git", "raw"}
OPENAI_YAML = Path("skills/living-wiki-steward/agents/openai.yaml")
FRONTMATTER_BLOCK_MARKERS = {"|", ">", "|-", ">-", "|+", ">+"}
HUMAN_READABLE_FENCE_LANGUAGES = {"text", "plain", "plaintext", "mermaid"}
MERMAID_DIRECTIVE_RE = re.compile(
    r"^(?:graph|flowchart)\s+(?:TD|TB|BT|RL|LR)$|"
    r"^(?:sequenceDiagram|classDiagram|stateDiagram(?:-v2)?|erDiagram|journey|gantt|pie|mindmap|timeline)$|"
    r"^(?:end|style|classDef|linkStyle|click)\b|^%%",
    re.IGNORECASE,
)
MERMAID_LABEL_RE = re.compile(r"[\[\(\{]\s*([^\]\)\}]+?)\s*[\]\)\}]")


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _markdown_paths(root: Path) -> list[Path]:
    result: list[Path] = []
    for path in root.rglob("*.md"):
        relative = path.relative_to(root)
        if not relative.parts or relative.parts[0] in EXCLUDED_TOP_LEVEL:
            continue
        if any(part.startswith(".") for part in relative.parts):
            continue
        result.append(path)
    return sorted(result)


def _is_external_source_title(path: Path, root: Path, heading_level: int | None = None) -> bool:
    relative = path.relative_to(root)
    if len(relative.parts) < 3 or relative.parts[:2] != ("wiki", "sources"):
        return False
    return heading_level in {None, 1}


def _is_machine_heading(text: str) -> bool:
    cleaned = text.strip().strip("` ")
    if not cleaned:
        return False
    return bool(ID_ONLY_RE.fullmatch(cleaned)) or not re.search(r"[A-Za-z가-힣]", cleaned)


def _is_numbered_citation(line: str) -> bool:
    stripped = line.strip()
    if re.match(r"^[-*]?\s*\[\d+\]\s+\[.+\]\(.+\)\s*$", stripped):
        return True
    return False


def _strip_allowed_links(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        label, target = match.groups()
        machine_label = label.strip().strip("` ")
        if (
            "/sources/" in target
            or target.startswith("sources/")
            or _is_machine_heading(machine_label)
            or re.fullmatch(r"(?:agent|human):[A-Za-z0-9_.-]+", machine_label)
        ):
            return ""
        return label

    return MARKDOWN_LINK_RE.sub(replace, value)


def _prose_counts(line: str, *, strip_allowed_links: bool = False) -> tuple[int, int]:
    cleaned = INLINE_CODE_RE.sub("", line)
    cleaned = ID_ONLY_RE.sub("", cleaned)
    cleaned = re.sub(r"\b(?:agent|human):[A-Za-z0-9_.-]+\b", "", cleaned)
    cleaned = _strip_allowed_links(cleaned) if strip_allowed_links else LINK_TARGET_RE.sub("]", cleaned)
    cleaned = URL_RE.sub("", cleaned)
    return len(HANGUL_RE.findall(cleaned)), len(LATIN_WORD_RE.findall(cleaned))


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def _is_table_row(line: str) -> bool:
    stripped = INLINE_CODE_RE.sub("", line).strip()
    return "|" in stripped and len(_table_cells(line)) >= 2


def _is_machine_only_fragment(value: str) -> bool:
    if re.fullmatch(
        r"\s*[-*+]?\s*(?:SHA-256|ID|URL|API|CLI|locator|경로|해시)\s*:\s*`[^`]+`\s*",
        value,
        re.IGNORECASE,
    ):
        return True
    cleaned = INLINE_CODE_RE.sub("", value)
    cleaned = URL_RE.sub("", cleaned)
    cleaned = re.sub(r"^[\s>*+\-│├└─→←↔]+", "", cleaned).strip()
    cleaned = cleaned.strip("[](){}.,:; ")
    if not cleaned:
        return True
    if _is_machine_heading(cleaned):
        return True
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", cleaned):
        return True
    if re.fullmatch(r"(?:[A-Za-z0-9_.~$-]+/)+[A-Za-z0-9_.~$-]*", cleaned):
        return True
    if re.fullmatch(
        r"[A-Za-z0-9_]+(?:\s*(?:--?>|<--?|==>|---|:::|\||→|←|↔|/)\s*[A-Za-z0-9_]+)+",
        cleaned,
    ):
        return True
    return False


def _is_machine_only_prose_line(value: str) -> bool:
    if re.fullmatch(
        r"\s*[-*+]?\s*(?:SHA-256|ID|URL|API|CLI|locator|경로|해시)\s*:\s*`[^`]+`\s*",
        value,
        re.IGNORECASE,
    ):
        return True
    cleaned = INLINE_CODE_RE.sub("", value)
    cleaned = URL_RE.sub("", cleaned)
    cleaned = re.sub(r"^[\s>*+\-]+", "", cleaned).strip("[](){}.,:; ")
    if not cleaned:
        return True
    if _is_machine_heading(cleaned):
        return True
    return bool(re.fullmatch(r"(?:[A-Za-z0-9_.~$-]+/)+[A-Za-z0-9_.~$-]*", cleaned))


def _table_cell_is_preserved_machine_value(cell: str, header: str) -> bool:
    normalized_header = INLINE_CODE_RE.sub("", header).strip()
    normalized_cell = cell.strip().strip("*_ ")
    if re.search(r"원제|저자|발행자|출판 상태|라이선스", normalized_header, re.IGNORECASE):
        return True
    source_header = re.search(
        r"출처|자료|문서|논문|영상|제목|source|reference|title",
        normalized_header,
        re.IGNORECASE,
    )
    if source_header and re.search(r"\[[^\]]+\]\(https?://[^)]+\)", normalized_cell):
        return True
    if source_header and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._/-]*", normalized_cell):
        return True
    if re.search(r"\bID\b|식별자|행위자|생성자|평가자|검토자", normalized_header, re.IGNORECASE):
        machine_label = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", normalized_cell)
        machine_label = machine_label.strip("` ")
        return bool(
            _is_machine_heading(machine_label)
            or re.fullmatch(r"(?:agent|human):[A-Za-z0-9_.-]+", machine_label)
        )
    if re.search(r"URL|주소", normalized_header, re.IGNORECASE):
        return bool(re.fullmatch(r"https?://\S+", normalized_cell.strip("<>")))
    if re.search(r"SHA-256|해시", normalized_header, re.IGNORECASE):
        return bool(re.fullmatch(r"`?[a-fA-F0-9]{16,}`?", normalized_cell))
    if re.search(r"locator|정확한 위치", normalized_header, re.IGNORECASE):
        return bool(
            re.search(
                r"(?:JSON|PDF|HTML|section|§|page|p\.|pp\.|line|timestamp|chapter|commit|README|path|file|row|transcript|paragraph|table|figure|heading|anchor|\$\.|\d{1,2}:\d{2})",
                normalized_cell,
                re.IGNORECASE,
            )
        )
    return _is_machine_only_fragment(cell)


def _has_external_original_title_context(line: str) -> bool:
    return bool(
        HANGUL_RE.search(line)
        and re.search(r"영상|논문|자료|문서|원제|출처|저장소|글", line)
        and re.search(r"\[[^\]]+\]\(https?://[^)]+\)", line)
    )


def _has_exact_quote_provenance(line: str) -> bool:
    if "원문" not in line:
        return False
    has_source = bool(re.search(r"SRC-[A-Z0-9]+|https?://\S+", line, re.IGNORECASE))
    locator_label = re.search(
        r"locator|정확한 위치|페이지|\b쪽\b|\b행\b|\b줄\b|timestamp|타임스탬프",
        line,
        re.IGNORECASE,
    )
    locator_value = ""
    if locator_label:
        locator_value = line[locator_label.end() :].lstrip()
        if locator_value.startswith((":", "=")):
            locator_value = locator_value[1:].strip()
        locator_value = locator_value.strip("` ;,")
    has_locator = bool(locator_value) or bool(
        re.search(r"\b\d{1,2}:\d{2}(?::\d{2})?\b|§\s*\S+", line)
    )
    return has_source and has_locator


def _human_fence_line_finding(
    relative: str,
    number: int,
    line: str,
    language: str,
) -> str | None:
    stripped = line.strip()
    if not stripped:
        return None
    if language == "mermaid" and MERMAID_DIRECTIVE_RE.match(stripped):
        return None
    fragments = MERMAID_LABEL_RE.findall(stripped) if language == "mermaid" else []
    candidates = fragments or [stripped]
    for candidate in candidates:
        if _is_machine_only_fragment(candidate):
            continue
        hangul, latin = _prose_counts(candidate)
        if (latin >= 2 and hangul == 0) or (latin >= 5 and hangul < 3):
            return (
                f"{relative}:{number} [KO-DOC-010] 사람이 읽는 다이어그램 라벨이 "
                "한국어가 아닙니다."
            )
    return None


def _machine_link_only(line: str) -> bool:
    match = re.match(r"^[-*+]\s+\[([^\]]+)\]\(([^)]+)\)\s*$", line.strip())
    if not match:
        return False
    label, target = match.groups()
    target_stem = Path(target.split("#", 1)[0]).stem
    return _is_machine_heading(label) or label == target_stem


def _frontmatter_findings(path: Path, root: Path, lines: list[str]) -> tuple[list[str], int]:
    if not lines or lines[0].strip() != "---":
        return [], 0
    relative = _relative(path, root)
    findings: list[str] = []
    index = 1
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped == "---":
            return findings, index + 1
        match = FRONTMATTER_FIELD_RE.match(stripped)
        if not match:
            index += 1
            continue
        field, raw_value = match.groups()
        value = raw_value.split(" #", 1)[0].strip()
        if value in FRONTMATTER_BLOCK_MARKERS:
            parts: list[str] = []
            cursor = index + 1
            while cursor < len(lines) and (lines[cursor].startswith((" ", "\t")) or not lines[cursor].strip()):
                parts.append(lines[cursor].strip())
                cursor += 1
            value = " ".join(parts).strip()
        value = value.strip("'\"")
        title_exception = field == "title" and (
            _is_external_source_title(path, root) or _is_machine_heading(value)
        )
        name_exception = field == "name" and bool(
            re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value)
        )
        hangul, latin = _prose_counts(value)
        if (
            not value
            or (not hangul and not title_exception and not name_exception)
            or (latin >= 5 and hangul < 3 and not title_exception and not name_exception)
        ):
            findings.append(
                f"{relative}:{index + 1} [KO-DOC-002] 사람이 읽는 {field} 값이 한국어가 아닙니다."
            )
        index += 1
    findings.append(f"{relative}:1 [KO-DOC-008] YAML frontmatter가 닫히지 않았습니다.")
    return findings, len(lines)


def _wrapped_paragraph_findings(
    path: Path,
    root: Path,
    lines: list[str],
    frontmatter_end: int,
) -> list[str]:
    relative = _relative(path, root)
    findings: list[str] = []
    paragraph: list[str] = []
    start = 0
    in_fence = False

    def flush() -> None:
        nonlocal paragraph, start
        if len(paragraph) > 1:
            counts = [_prose_counts(item) for item in paragraph]
            hangul = sum(item[0] for item in counts)
            latin = sum(item[1] for item in counts)
            if latin >= 3 and hangul == 0 and all(item[1] < 3 for item in counts):
                findings.append(
                    f"{relative}:{start} [KO-DOC-004] 줄바꿈된 일반 문장이 영어로만 작성됐습니다."
                )
        paragraph = []
        start = 0

    for number, line in enumerate(lines, start=1):
        if number <= frontmatter_end:
            continue
        stripped = line.strip()
        if FENCE_RE.match(line):
            flush()
            in_fence = not in_fence
            continue
        structural = (
            in_fence
            or not stripped
            or line.startswith(("    ", "\t"))
            or stripped.startswith(("#", "|", "- ", "* ", ">", "<!--"))
            or _is_numbered_citation(line)
            or bool(re.fullmatch(r"=+|-{3,}", stripped))
        )
        if structural:
            flush()
            continue
        if not paragraph:
            start = number
        paragraph.append(line)
    flush()
    return findings


def _validate_markdown(path: Path, root: Path, supplied_text: str | None = None) -> list[str]:
    relative = _relative(path, root)
    text = supplied_text if supplied_text is not None else path.read_text(encoding="utf-8")
    findings: list[str] = []
    if not HANGUL_RE.search(text):
        findings.append(f"{relative}:1 [KO-DOC-001] 한국어 사람이 읽는 문구가 없습니다.")

    lines = text.splitlines()
    frontmatter_findings, frontmatter_end = _frontmatter_findings(path, root, lines)
    findings.extend(frontmatter_findings)
    in_fence = False
    fence_language = ""
    table_header_expected = True
    table_headers: list[str] = []
    original_quote_context = False
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if number <= frontmatter_end:
            continue

        fence_match = FENCE_RE.match(line)
        if fence_match:
            if in_fence:
                in_fence = False
                fence_language = ""
            else:
                in_fence = True
                fence_language = fence_match.group(2).lower()
            continue
        if in_fence:
            if fence_language in HUMAN_READABLE_FENCE_LANGUAGES:
                finding = _human_fence_line_finding(
                    relative,
                    number,
                    line,
                    fence_language,
                )
                if finding:
                    findings.append(finding)
            table_header_expected = True
            continue
        if not stripped:
            table_header_expected = True
            continue
        if stripped.startswith("<!--"):
            continue
        quote_marker = _has_exact_quote_provenance(stripped)
        if original_quote_context and not stripped.startswith(">") and not quote_marker:
            original_quote_context = False
        if line.startswith(("    ", "\t")):
            continue

        if re.fullmatch(r"=+|-{3,}", stripped) and number > 1:
            title = lines[number - 2].strip()
            if (
                re.search(r"[A-Za-z]", title)
                and not HANGUL_RE.search(title)
                and not _is_machine_heading(title)
                and not _is_external_source_title(path, root, 1)
            ):
                findings.append(
                    f"{relative}:{number - 1} [KO-DOC-003] Setext 제목이 영어로만 작성됐습니다."
                )
            continue

        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2)
            heading_hangul, heading_latin = _prose_counts(title)
            source_title = _is_external_source_title(path, root, level)
            if (
                re.search(r"[A-Za-z]", title)
                and not HANGUL_RE.search(title)
                and not _is_machine_heading(title)
                and not source_title
            ):
                findings.append(
                    f"{relative}:{number} [KO-DOC-003] 예외가 아닌 제목·섹션명이 영어로만 작성됐습니다."
                )
            elif (
                heading_latin >= 5
                and heading_hangul < 3
                and not source_title
                and not _is_machine_heading(title)
            ):
                findings.append(
                    f"{relative}:{number} [KO-DOC-005] 제목·섹션명이 영어 중심이며 한국어 몇 글자로 우회할 수 없습니다."
                )
            table_header_expected = True
            continue

        if _is_table_row(line):
            if TABLE_SEPARATOR_RE.match(stripped):
                table_header_expected = False
                continue
            cells = _table_cells(line)
            if table_header_expected:
                table_headers = cells
                for cell in cells:
                    hangul, latin = _prose_counts(cell)
                    machine_only = cell.strip().upper() in {"ID", "URL", "SHA-256", "API", "CLI"}
                    if latin and not hangul and not machine_only:
                        findings.append(
                            f"{relative}:{number} [KO-DOC-003] 표 머리글이 영어로만 작성됐습니다."
                        )
                        break
                    if latin >= 5 and hangul < 3:
                        findings.append(
                            f"{relative}:{number} [KO-DOC-005] 표 머리글이 영어 중심이며 한국어 몇 글자로 우회할 수 없습니다."
                        )
                        break
                table_header_expected = False
            else:
                for index, cell in enumerate(cells):
                    header = table_headers[index] if index < len(table_headers) else ""
                    if (
                        index > 0
                        and table_headers
                        and re.search(r"항목|필드|field", table_headers[0], re.IGNORECASE)
                        and cells
                    ):
                        header = cells[0]
                    if _table_cell_is_preserved_machine_value(cell, header):
                        continue
                    hangul, latin = _prose_counts(cell, strip_allowed_links=True)
                    if "원제" in cell and hangul:
                        continue
                    if latin >= 2 and hangul == 0:
                        findings.append(
                            f"{relative}:{number} [KO-DOC-004] 표 본문의 사람이 읽는 문장이 영어로만 작성됐습니다."
                        )
                        break
                    if latin >= 5 and hangul < 3:
                        findings.append(
                            f"{relative}:{number} [KO-DOC-005] 표 본문이 영어 중심이며 한국어 몇 글자로 우회할 수 없습니다."
                        )
                        break
            continue
        table_header_expected = True

        if _is_numbered_citation(line):
            continue
        if _machine_link_only(line):
            continue
        if stripped.startswith(">") and original_quote_context:
            continue
        if quote_marker:
            original_quote_context = True
        elif not stripped.startswith(">"):
            original_quote_context = False
        hangul, latin = _prose_counts(line)
        if "원제" in stripped and hangul:
            continue
        if _has_external_original_title_context(line):
            continue
        short_prose = stripped.startswith(("- ", "* ", "+ ")) or stripped.endswith((".", "!", "?"))
        english_only = latin >= 2 or (latin >= 1 and short_prose)
        if english_only and hangul == 0 and not _is_machine_only_prose_line(line):
            findings.append(
                f"{relative}:{number} [KO-DOC-004] 예외가 아닌 일반 문장이 영어로만 작성됐습니다."
            )
        elif latin >= 5 and hangul < 3:
            findings.append(
                f"{relative}:{number} [KO-DOC-005] 일반 문장이 영어 중심이며 한국어 몇 글자로 우회할 수 없습니다."
            )
    if in_fence:
        findings.append(f"{relative}:{len(lines) or 1} [KO-DOC-007] 닫히지 않은 코드 펜스가 있습니다.")
    findings.extend(_wrapped_paragraph_findings(path, root, lines, frontmatter_end))
    return findings


def _validate_openai_yaml(root: Path) -> list[str]:
    findings: list[str] = []
    required = {"display_name", "short_description", "default_prompt"}
    paths = sorted(root.glob("skills/**/agents/openai.yaml"))
    canonical_skill = root / OPENAI_YAML.parents[1]
    if canonical_skill.is_dir() and not (root / OPENAI_YAML).is_file():
        findings.append(f"{OPENAI_YAML.as_posix()}:1 [KO-DOC-006] Skill UI 파일이 없습니다.")
    for path in paths:
        relative = _relative(path, root)
        seen: set[str] = set()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = re.match(r"\s*(display_name|short_description|default_prompt):\s*(.*)$", line)
            if not match:
                continue
            field, raw_value = match.groups()
            seen.add(field)
            value = raw_value.split(" #", 1)[0].strip().strip("'\"")
            hangul, latin = _prose_counts(value)
            if not hangul or (latin >= 4 and hangul < 3):
                findings.append(
                    f"{relative}:{number} [KO-DOC-006] {field} 사용자 표시 값이 한국어가 아닙니다."
                )
        for field in sorted(required - seen):
            findings.append(
                f"{relative}:1 [KO-DOC-006] 필수 사용자 표시 필드 {field}가 없습니다."
            )
    return findings


def _validate_installed_global_loader(root: Path) -> list[str]:
    if not (root / "wiki" / "specs" / "korean-documentation-policy.md").is_file():
        return []
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    override = codex_home / "AGENTS.override.md"
    path = override if override.is_file() and override.stat().st_size else codex_home / "AGENTS.md"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r"<!-- LIVING_WIKI_BOOTSTRAP:BEGIN -->(.*?)<!-- LIVING_WIKI_BOOTSTRAP:END -->",
        text,
        re.DOTALL,
    )
    if not match:
        return ["$CODEX_HOME/AGENTS.md:1 [KO-DOC-009] Living Wiki 전역 부트스트랩 블록이 없습니다."]
    block = match.group(1)
    findings: list[str] = []
    if not HANGUL_RE.search(block):
        findings.append("$CODEX_HOME/AGENTS.md:1 [KO-DOC-009] 전역 부트스트랩이 한국어가 아닙니다.")
    if "wiki/specs/korean-documentation-policy.md" not in block:
        findings.append("$CODEX_HOME/AGENTS.md:1 [KO-DOC-009] 전역 부트스트랩에 한국어 문서 정책 경로가 없습니다.")
    return findings


def _finding_sort_key(value: str) -> tuple[str, int, str, str]:
    match = re.match(r"^(.*?):(\d+) \[([^\]]+)\]", value)
    if not match:
        return value, 0, "", value
    path, line, rule = match.groups()
    return path, int(line), rule, value


def validate_markdown_text(root: Path, relative_path: Path, text: str) -> list[str]:
    """아직 쓰지 않은 생성 Markdown을 동일 계약으로 검사한다."""

    root = root.resolve()
    return _validate_markdown(root / relative_path, root, supplied_text=text)


def validate_repository(root: Path) -> list[str]:
    """안정적인 경로·줄·규칙 ID 순서로 모든 위반을 반환한다."""

    root = root.resolve()
    findings: list[str] = []
    for path in _markdown_paths(root):
        findings.extend(_validate_markdown(path, root))
    findings.extend(_validate_openai_yaml(root))
    findings.extend(_validate_installed_global_loader(root))
    return sorted(set(findings), key=_finding_sort_key)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Living Wiki 한국어 문서 계약 검사")
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    args = parser.parse_args(argv)
    findings = validate_repository(args.root)
    for finding in findings:
        print(f"오류: {finding}")
    if findings:
        print(f"한국어 문서 검사 실패: {len(findings)}건")
        return 1
    print("한국어 문서 검사 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
