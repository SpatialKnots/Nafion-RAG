from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Article, ArticleTag, Chunk, Page, Section


@dataclass(frozen=True)
class TagCandidate:
    tag_type: str
    tag_value: str
    confidence: float


@dataclass(frozen=True)
class SectionCandidate:
    name: str
    normalized_name: str
    page_start: int
    page_end: int
    source_type: str


TERM_PATTERNS: dict[str, dict[str, list[str]]] = {
    "ion_form": {
        "H": [r"\bH[- ]?Nafion\b", r"\bprotonated\s+Nafion\b", r"\bH\+\s*form\b"],
        "Li": [r"\bLi[- ]?Nafion\b", r"\blithiated\s+Nafion\b", r"\blithium\s+form\b"],
        "Na": [r"\bNa[- ]?Nafion\b", r"\bsodium\s+type\b", r"\bsodium\s+form\b"],
        "K": [r"\bK[- ]?Nafion\b", r"\bpotassium\s+form\b"],
        "Cs": [r"\bCs[- ]?Nafion\b", r"\bcesium\s+form\b"],
        "Mg": [r"\bMg[- ]?Nafion\b", r"\bmagnesium\s+form\b"],
        "Ca": [r"\bCa[- ]?Nafion\b", r"\bcalcium\s+form\b"],
    },
    "solvent": {
        "EC": [r"\bethylene\s+carbonate\b", r"\bEC\b"],
        "SL": [r"\bsulfolane\b", r"\bSL\b"],
        "NMP": [r"\bNMP\b", r"\bN-methyl-?2-?pyrrolidone\b"],
        "DMF": [r"\bDMF\b", r"\bdimethylformamide\b"],
        "DMA": [r"\bDMA\b", r"\bdimethylacetamide\b"],
        "DMSO": [r"\bDMSO\b", r"\bdimethyl\s+sulfoxide\b"],
        "PC": [r"\bpropylene\s+carbonate\b", r"\bPC\b"],
        "DOL": [r"\bDOL\b", r"\bdioxolane\b"],
        "DME": [r"\bDME\b", r"\bdimethoxyethane\b"],
        "water": [r"\bwater\b", r"\baqueous\b"],
        "ethanol": [r"\bethanol\b", r"\bEtOH\b"],
        "methanol": [r"\bmethanol\b", r"\bMeOH\b"],
        "isopropanol": [r"\bisopropanol\b", r"\b2-propanol\b", r"\bIPA\b"],
    },
    "method": {
        "conductivity": [r"\bconductivit(?:y|ies)\b", r"\bionic\s+conductivity\b"],
        "EIS": [r"\bEIS\b", r"\belectrochemical\s+impedance\b", r"\bimpedance\s+spectroscop"],
        "TGA": [r"\bTGA\b", r"\bthermogravimetric"],
        "TGA-MS": [r"\bTGA[- ]?MS\b", r"\bthermogravimetric.*mass\s+spectrom"],
        "DSC": [r"\bDSC\b", r"\bdifferential\s+scanning\s+calorim"],
        "XRD": [r"\bXRD\b", r"\bX-ray\s+diffraction\b"],
        "WAXD": [r"\bWAXD\b", r"\bwide[- ]angle\s+X-ray\b"],
        "SAXS": [r"\bSAXS\b", r"\bsmall[- ]angle\s+X-ray\b"],
        "SANS": [r"\bSANS\b", r"\bsmall[- ]angle\s+neutron\b"],
        "FTIR": [r"\bFTIR\b", r"\bFT-?IR\b", r"\binfrared\s+spectroscop"],
        "NMR": [r"\bNMR\b", r"\bnuclear\s+magnetic\s+resonance\b"],
        "SEM": [r"\bSEM\b", r"\bscanning\s+electron\s+microscop"],
        "TEM": [r"\bTEM\b", r"\btransmission\s+electron\s+microscop"],
        "AFM": [r"\bAFM\b", r"\batomic\s+force\s+microscop"],
        "swelling": [r"\bswelling\b", r"\buptake\b"],
    },
    "material": {
        "Nafion 115": [r"\bNafion[- ]?115\b"],
        "Nafion 117": [r"\bNafion[- ]?117\b"],
        "Nafion 212": [r"\bNafion[- ]?212\b"],
        "Nafion 211": [r"\bNafion[- ]?211\b"],
        "PVDF": [r"\bPVDF\b", r"\bpolyvinylidene\s+fluoride\b"],
        "PVDF-HFP": [r"\bPVDF[- ]?HFP\b"],
    },
    "battery_role": {
        "electrolyte": [r"\belectrolyte\b", r"\bpolymer\s+electrolyte\b"],
        "separator": [r"\bseparator\b"],
        "binder": [r"\bbinder\b"],
    },
    "sample_type": {
        "membrane": [r"\bmembrane\b"],
        "film": [r"\bfilm\b"],
        "dispersion": [r"\bdispersion\b"],
    },
}

SECTION_PATTERNS: dict[str, list[str]] = {
    "abstract": [r"^\s*abstract\b"],
    "introduction": [r"^\s*(?:1\.?\s*)?introduction\b"],
    "experimental": [r"^\s*(?:\d+\.?\s*)?(?:experimental|materials?\s+and\s+methods|methods?)\b"],
    "results": [r"^\s*(?:\d+\.?\s*)?(?:results|results\s+and\s+discussion)\b"],
    "discussion": [r"^\s*(?:\d+\.?\s*)?discussion\b"],
    "conclusions": [r"^\s*(?:\d+\.?\s*)?conclusions?\b"],
    "references": [r"^\s*(?:references|bibliography)\b"],
    "supplementary": [r"^\s*supplementary\b", r"^\s*supporting\s+information\b"],
}

EVIDENCE_PATTERNS: dict[str, list[str]] = {
    "experimental_data": [r"\bmeasured\b", r"\bprepared\b", r"\bwas\s+studied\b", r"\bexperiment"],
    "numerical_table": [r"\bTable\s+\d+", r"\b\d+(?:\.\d+)?\s*(?:wt\s*%|mol|S\s*cm|mS\s*cm|°C|K)\b"],
    "figure_caption": [r"\bFig\.\s*\d+", r"\bFigure\s+\d+"],
    "method_description": [r"\bwas\s+measured\b", r"\bwere\s+measured\b", r"\bwas\s+prepared\b", r"\bwere\s+prepared\b"],
    "computational": [r"\bDFT\b", r"\bquantum\s+chemical\b", r"\bcalculation"],
    "review_background": [r"\bhas\s+been\s+reported\b", r"\bin\s+the\s+literature\b", r"\breview"],
}


def _matches(text: str, patterns: Iterable[str]) -> int:
    return sum(1 for pattern in patterns if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE))


def extract_tags(text: str) -> list[TagCandidate]:
    tags: list[TagCandidate] = []
    for tag_type, values in TERM_PATTERNS.items():
        for value, patterns in values.items():
            count = _matches(text, patterns)
            if count:
                tags.append(TagCandidate(tag_type=tag_type, tag_value=value, confidence=min(1.0, 0.55 + 0.15 * count)))
    for value, patterns in EVIDENCE_PATTERNS.items():
        count = _matches(text, patterns)
        if count:
            tags.append(TagCandidate(tag_type="evidence_type", tag_value=value, confidence=min(1.0, 0.55 + 0.15 * count)))
    return tags


def classify_source_type(text: str) -> str:
    compact_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if re.search(r"\bTable\s+\d+", text, flags=re.IGNORECASE):
        return "table"
    table_like_lines = 0
    for line in compact_lines:
        numbers = re.findall(r"\d+(?:\.\d+)?", line)
        cells = re.split(r"\s{2,}|\t+", line)
        if len(numbers) >= 4 and len(cells) >= 4:
            table_like_lines += 1
    if len(compact_lines) >= 4 and table_like_lines >= 4 and table_like_lines / len(compact_lines) >= 0.35:
        return "table"
    if re.search(r"^\s*(?:Fig\.|Figure)\s*\d+", text, flags=re.IGNORECASE | re.MULTILINE):
        return "figure_caption"
    if re.search(r"\b(?:experimental|materials?\s+and\s+methods|was\s+measured|were\s+measured)\b", text, flags=re.IGNORECASE):
        return "method"
    return "main_text"


def detect_sections(pages: list[Page]) -> list[SectionCandidate]:
    starts: list[tuple[str, str, int, str]] = []
    for page in pages:
        for line in (page.text or "").splitlines():
            normalized_line = re.sub(r"\s+", " ", line).strip()
            if len(normalized_line) > 80:
                continue
            for normalized, patterns in SECTION_PATTERNS.items():
                if any(re.search(pattern, normalized_line, flags=re.IGNORECASE) for pattern in patterns):
                    if not starts or starts[-1][0] != normalized:
                        starts.append((normalized, normalized_line, page.page_number, "main_text"))
                    break

    if not starts and pages:
        return [SectionCandidate(name="Full text", normalized_name="full_text", page_start=pages[0].page_number, page_end=pages[-1].page_number, source_type="main_text")]

    sections: list[SectionCandidate] = []
    for index, (normalized, name, page_start, source_type) in enumerate(starts):
        next_start = starts[index + 1][2] if index + 1 < len(starts) else pages[-1].page_number
        page_end = max(page_start, next_start - 1 if next_start > page_start else next_start)
        sections.append(SectionCandidate(name=name, normalized_name=normalized, page_start=page_start, page_end=page_end, source_type=source_type))
    return sections


def _best_section_for_chunk(chunk: Chunk, sections: list[Section]) -> Section | None:
    candidates = [
        section
        for section in sections
        if section.page_start is not None
        and section.page_end is not None
        and chunk.page_start <= section.page_end
        and chunk.page_end >= section.page_start
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda section: min(chunk.page_end, section.page_end or chunk.page_end) - max(chunk.page_start, section.page_start or chunk.page_start))


def classify_article(session: Session, article: Article) -> None:
    session.execute(delete(ArticleTag).where(ArticleTag.article_id == article.id).where(ArticleTag.source == "rule_based"))
    session.execute(delete(Section).where(Section.article_id == article.id))
    session.flush()

    pages = list(session.scalars(select(Page).where(Page.article_id == article.id).order_by(Page.page_number)))
    chunks = list(session.scalars(select(Chunk).where(Chunk.article_id == article.id).order_by(Chunk.chunk_index)))

    for section_candidate in detect_sections(pages):
        session.add(
            Section(
                article_id=article.id,
                name=section_candidate.name,
                normalized_name=section_candidate.normalized_name,
                page_start=section_candidate.page_start,
                page_end=section_candidate.page_end,
                source_type=section_candidate.source_type,
            )
        )
    session.flush()
    sections = list(session.scalars(select(Section).where(Section.article_id == article.id).order_by(Section.page_start)))

    tag_keys: set[tuple[str, str]] = set()
    article_text = "\n\n".join(chunk.text for chunk in chunks)
    for tag in extract_tags(article_text):
        key = (tag.tag_type, tag.tag_value)
        if key in tag_keys:
            continue
        tag_keys.add(key)
        session.add(
            ArticleTag(
                article_id=article.id,
                tag_type=tag.tag_type,
                tag_value=tag.tag_value,
                confidence=tag.confidence,
                source="rule_based",
            )
        )

    for chunk in chunks:
        chunk.source_type = classify_source_type(chunk.text)
        best_section = _best_section_for_chunk(chunk, sections)
        chunk.section_id = best_section.id if best_section is not None else None
