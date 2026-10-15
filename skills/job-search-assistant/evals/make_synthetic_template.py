#!/usr/bin/env python3
"""Make fixtures/Synthetic-Resume-Template.docx, a stand-in for the resume template.

build_resume.py clones prototype paragraphs from the template by their position in the
document body (its PROTO table). The real template isn't in the repo, so tests and evals
use this generated file instead: it has the same structure at the same positions, with
placeholder text only. Needs python-docx.

    python make_synthetic_template.py
"""

from __future__ import annotations

import datetime
import io
import re
import sys
import zipfile
from pathlib import Path

import docx
from lxml import etree
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "tailored-resume-builder"))
from build_resume import PROTO  # noqa: E402

OUT = HERE / "fixtures" / "Synthetic-Resume-Template.docx"
BODY_LENGTH = max(PROTO.values()) + 1

# Prototype role -> (style, placeholder text, bold, italic, list item)
ROLES = {
    "title": ("Title", "SAMPLE NAME", True, False, False),
    "contact": ("Normal", "555-0000 · Sample City · sample@example.com", False, False, False),
    "headline": ("Subtitle", "SAMPLE HEADLINE", True, False, False),
    "summary": ("Normal", "Sample summary text.", False, False, False),
    "section": ("Heading 1", "SAMPLE SECTION", True, False, False),
    "highlight": ("List Bullet", "Sample highlight.", False, False, True),
    "company": ("Heading 2", "Sample Company", True, False, False),
    "company_desc": ("Normal", "Sample company description.", False, True, False),
    "role": ("Heading 3", "Sample Role", True, False, False),
    "role_summary": ("Normal", "Sample role summary.", False, False, False),
    "key_acc": ("Normal", "Key Accomplishments:", True, False, False),
    "bullet": ("List Bullet", "Sample accomplishment.", False, False, True),
    "spacer": ("Normal", "", False, False, False),
    "edu_title": ("Heading 1", "Education and Certifications", True, False, False),
    "degree": ("Normal", "Sample Degree", True, False, False),
    "school": ("Normal", "Sample School", False, False, False),
    "addl_title": ("Heading 1", "Additional Information", True, False, False),
    "addl": ("Normal", "Sample additional line.", False, False, False),
}


def numbered(paragraph) -> None:
    """Give the paragraph its own numPr, as list items in the real template have."""
    num_pr = paragraph._p.get_or_add_pPr().get_or_add_numPr()
    num_pr.get_or_add_ilvl().val = 0
    num_pr.get_or_add_numId().val = 1


def main() -> int:
    d = docx.Document()
    body = d.element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)
    section = d.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(section, side, Inches(0.5))
    d.styles["Normal"].font.size = Pt(10)

    by_index = {i: role for role, i in PROTO.items()}
    for i in range(BODY_LENGTH):
        role = by_index.get(i)
        if role == "table":
            table = d.add_table(rows=1, cols=3)
            for cell in table.rows[0].cells:
                p = cell.paragraphs[0]
                p.style = d.styles["List Bullet"]
                p.add_run("Sample competency")
                numbered(p)
            tr_pr = table.rows[0]._tr.get_or_add_trPr()
            height = OxmlElement("w:trHeight")
            height.set(qn("w:val"), "400")
            tr_pr.append(height)
            continue
        style, text, bold, italic, listed = ROLES.get(role, ("Normal", "Sample filler text.", False, False, False))
        p = d.add_paragraph(style=d.styles[style])
        if text:
            run = p.add_run(text)
            run.bold, run.italic = bold or None, italic or None
            run.font.size = Pt(10)  # gives every text run an rPr to clone, as in the real template
        if listed:
            numbered(p)

    fixed = datetime.datetime(2026, 1, 1)
    d.core_properties.author = "job-search-assistant evals"
    d.core_properties.title = "Synthetic resume template"
    d.core_properties.created = d.core_properties.modified = fixed
    buffer = io.BytesIO()
    d.save(buffer)
    OUT.write_bytes(slim(buffer.getvalue()))
    print(f"wrote {OUT.relative_to(HERE)} ({len(body) - 1} body elements, {OUT.stat().st_size} bytes)")
    return 0


# Parts of python-docx's default document that a resume never uses. Dropping them keeps the
# file small, which matters: from the cloud the template reaches the skill as base64 text.
DROP_PARTS = ("word/stylesWithEffects.xml", "docProps/thumbnail.jpeg", "word/webSettings.xml", "customXml/")
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def slim(docx_bytes: bytes) -> bytes:
    """Drop unused parts and every style the document doesn't use (or inherit from)."""
    src = zipfile.ZipFile(io.BytesIO(docx_bytes))
    parts = {i.filename: src.read(i.filename) for i in src.infolist()}
    parts = {n: b for n, b in parts.items() if not n.startswith(DROP_PARTS)}

    styles = etree.fromstring(parts["word/styles.xml"])
    used = set(re.findall(rb'w:(?:pStyle|rStyle|tblStyle) w:val="([^"]+)"', parts["word/document.xml"]))
    used = {u.decode() for u in used} | {"Normal", "DefaultParagraphFont", "TableNormal", "NoList"}
    by_id = {s.get(f"{{{W_NS}}}styleId"): s for s in styles.iter(f"{{{W_NS}}}style")}
    pending = list(used)
    while pending:  # keep the styles the used ones are based on or linked to
        style = by_id.get(pending.pop())
        for ref in ("basedOn", "link", "next"):
            el = style.find(f"{{{W_NS}}}{ref}") if style is not None else None
            val = el.get(f"{{{W_NS}}}val") if el is not None else None
            if val and val not in used:
                used.add(val)
                pending.append(val)
    for style_id, style in by_id.items():
        if style_id not in used:
            styles.remove(style)
    latent = styles.find(f"{{{W_NS}}}latentStyles")
    if latent is not None:
        styles.remove(latent)
    parts["word/styles.xml"] = etree.tostring(styles, xml_declaration=True, encoding="UTF-8", standalone=True)

    def keep_rel(xml: bytes) -> bytes:
        return re.sub(rb"<Relationship [^>]*Target=\"[^\"]*(?:stylesWithEffects|thumbnail|webSettings|customXml)[^\"]*\"[^>]*/>", b"", xml)

    for name in ("_rels/.rels", "word/_rels/document.xml.rels"):
        parts[name] = keep_rel(parts[name])
    parts["[Content_Types].xml"] = re.sub(
        rb"<Override [^>]*PartName=\"/(?:word/stylesWithEffects|word/webSettings|docProps/thumbnail|customXml)[^\"]*\"[^>]*/>",
        b"", parts["[Content_Types].xml"])

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))  # fixed time: same bytes every run
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    return out.getvalue()


if __name__ == "__main__":
    sys.exit(main())
