from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from html.parser import HTMLParser
import re


_BLOCK_TAGS = {
    "article",
    "blockquote",
    "br",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "td",
    "th",
    "tr",
    "ul",
}
_HIDDEN_TAGS = {"script", "style"}
_URL_PATTERN = re.compile(
    r"\b(?:[a-z][a-z0-9+.-]*://\S+|www\.\S+|"
    r"(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/\S*)?)",
    flags=re.IGNORECASE,
)


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(
        self,
        tag: str,
        _attrs: list[tuple[str, str | None]],
    ) -> None:
        normalized = tag.casefold()
        if normalized in _HIDDEN_TAGS:
            self.hidden_depth += 1
        elif not self.hidden_depth and normalized in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.casefold()
        if normalized in _HIDDEN_TAGS:
            self.hidden_depth = max(0, self.hidden_depth - 1)
        elif not self.hidden_depth and normalized in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)


@dataclass(frozen=True, slots=True)
class SourceBudgets:
    maximum_source_characters: int
    maximum_theory_characters: int
    maximum_key_point_characters: int
    maximum_notes_characters: int


@dataclass(frozen=True, slots=True)
class PreparedQuestionSource:
    title: str
    content: str
    source_kind: str
    source_identifier: str


class SourceContentUnavailableError(ValueError):
    pass


def collapse_whitespace(value: str) -> str:
    lines = []
    for raw_line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = re.sub(r"\s+", " ", raw_line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def remove_urls(value: str) -> str:
    return collapse_whitespace(_URL_PATTERN.sub(" ", value))


def clean_html_text(value: str | None) -> str:
    if not value:
        return ""
    parser = _VisibleTextParser()
    parser.feed(value)
    parser.close()
    return remove_urls("".join(parser.parts))


def truncate_text(value: str, maximum_characters: int) -> str:
    if maximum_characters < 0:
        raise ValueError("maximum_characters must not be negative")
    if len(value) <= maximum_characters:
        return value
    return value[:maximum_characters].rstrip()


def prepare_question_source(
    *,
    title: str,
    theory: str | None,
    key_points: Sequence[str],
    description_text: str | None,
    budgets: SourceBudgets,
) -> PreparedQuestionSource:
    clean_title = remove_urls(title)
    clean_theory = remove_urls(theory or "")
    clean_key_points = [
        point
        for point in (remove_urls(point) for point in key_points)
        if point
    ]

    if clean_theory or clean_key_points:
        theory_part = truncate_text(
            clean_theory,
            budgets.maximum_theory_characters,
        )
        remaining_key_point_characters = budgets.maximum_key_point_characters
        bounded_points: list[str] = []
        for point in clean_key_points:
            if remaining_key_point_characters <= 0:
                break
            bounded = truncate_text(point, remaining_key_point_characters)
            if bounded:
                bounded_points.append(bounded)
                remaining_key_point_characters -= len(bounded)

        sections = [f"Title: {clean_title}"]
        if theory_part:
            sections.append(f"Theory:\n{theory_part}")
        if bounded_points:
            sections.append(
                "Key points:\n" + "\n".join(f"- {point}" for point in bounded_points)
            )
        source_kind = "GENERATED_REVISION"
    else:
        notes = truncate_text(
            clean_html_text(description_text),
            budgets.maximum_notes_characters,
        )
        if not notes:
            raise SourceContentUnavailableError(
                "learning item has no usable question-generation content"
            )
        sections = [f"Title: {clean_title}"]
        sections.append(f"Notes:\n{notes}")
        source_kind = "CLEANED_NOTES"

    content = truncate_text(
        "\n\n".join(sections),
        budgets.maximum_source_characters,
    )
    identifier = sha256(content.encode("utf-8")).hexdigest()
    return PreparedQuestionSource(
        title=clean_title,
        content=content,
        source_kind=source_kind,
        source_identifier=identifier,
    )
