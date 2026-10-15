#!/usr/bin/env python3
"""Render a resume .docx (and PDF) from content.json and a resume style file.

Usage: render_resume.py --style resume-style.md --content content.json --out out.docx [--pdf]

The style file (format: resume-style-format.md; example: default-style.md) is the user's look,
as text: page, fonts, colours, section order and layout. The document is built from scratch, so
no Word template is needed. Prints JSON: {"out": ..., "pages": N or null, "warnings": [...]}.
Exit 2, with {"error": ...}, on an invalid style file or content.json.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field, replace

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

STYLE_FORMAT = "1"
SECTIONS = ("summary", "competencies", "highlights", "experience", "education", "certifications", "additional")
DEFAULT_TITLES = {
    "summary": "Summary", "competencies": "Core Competencies", "highlights": "Career Highlights",
    "experience": "Professional Experience", "education": "Education",
    "certifications": "Certifications", "additional": "Additional Information",
}
TEXT_ROLES = ("Body", "Name", "Headline", "Contact", "Section headings", "Company",
              "Company description", "Role", "Location", "Dates")
PAGE_SIZES = {"letter": (8.5, 11.0), "a4": (8.27, 11.69)}
LIMITS = dict(competencies=12, highlights=5)


class StyleError(ValueError):
    pass


def fail(msg: str):
    print(json.dumps({"error": msg}))
    sys.exit(2)


# ---------------------------------------------------------------- style file


@dataclass
class TextStyle:
    font: str | None = None
    size: float | None = None
    bold: bool = False
    italic: bool = False
    caps: bool = False
    underline: bool = False
    color: str | None = None
    rule: bool = False


@dataclass
class Style:
    size: str = "letter"
    margins: dict = field(default_factory=lambda: dict(top=0.5, bottom=0.5, left=0.6, right=0.6))
    text: dict = field(default_factory=dict)
    align: str = "left"
    contact_sep: str = " · "
    order: list = field(default_factory=lambda: list(SECTIONS))
    titles: dict = field(default_factory=lambda: dict(DEFAULT_TITLES))
    competencies: tuple = ("grid", 3)
    bullet: str = "•"
    dates: str = "right"
    acc_label: str = ""
    space_heading: float = 3.0
    space_roles: float = 6.0

    def t(self, role: str) -> TextStyle:
        """The text style for a role, with font, size and colour inherited from Body."""
        body, own = self.text["Body"], self.text.get(role, TextStyle())
        return replace(own, font=own.font or body.font, size=own.size or body.size, color=own.color or body.color)


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_text_style(value: str, where: str, heading: bool) -> TextStyle:
    ts = TextStyle()
    for token in (t.strip() for t in value.split(",")):
        low = token.lower()
        if not token:
            continue
        if re.fullmatch(r"\d+(\.\d+)?", token):
            ts.size = float(token)
            if not 4 <= ts.size <= 72:
                raise StyleError(f"{where}: size {token} is out of range (4-72)")
        elif low in ("bold", "italic", "caps", "underline"):
            setattr(ts, low, True)
        elif low == "rule":
            if not heading:
                raise StyleError(f"{where}: 'rule' only applies to Section headings")
            ts.rule = True
        elif low.startswith("color"):
            hex_ = token[5:].strip().lstrip("#")
            if not re.fullmatch(r"[0-9A-Fa-f]{6}", hex_):
                raise StyleError(f"{where}: color must be 6 hex digits, e.g. color 1F3864")
            ts.color = hex_.upper()
        elif ts.font is None and re.fullmatch(r"[A-Za-z][\w .'-]*", token):
            ts.font = token
        else:
            raise StyleError(f"{where}: don't understand '{token}'")
    return ts


def parse_style(text: str) -> Style:
    st = Style()
    section, version, seen_text = None, None, {}
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if line.startswith("## "):
            section = line[3:].strip().lower()
            if section not in ("page", "text", "layout", "not carried over"):
                raise StyleError(f"line {n}: unknown section '{line[3:].strip()}'")
            continue
        if section is None:
            m = re.match(r"Style format:\s*(\S+)", line)
            if m:
                version = m.group(1)
            continue
        if section == "not carried over" or not line.startswith("- "):
            continue
        key, sep, value = line[2:].partition(":")
        if not sep:
            raise StyleError(f"line {n}: expected '- Key: value'")
        key, value, where = key.strip(), value.strip(), f"line {n} ({key.strip()})"
        if section == "page":
            if key == "Size":
                if value.lower() not in PAGE_SIZES:
                    raise StyleError(f"{where}: size must be Letter or A4")
                st.size = value.lower()
            elif key == "Margins (in)":
                st.margins = parse_margins(value, where)
            else:
                raise StyleError(f"{where}: unknown Page setting")
        elif section == "text":
            if key not in TEXT_ROLES:
                raise StyleError(f"{where}: unknown Text setting (expected one of: {', '.join(TEXT_ROLES)})")
            seen_text[key] = parse_text_style(value, where, heading=key == "Section headings")
        elif section == "layout":
            parse_layout(st, key, value, where)
    if version != STYLE_FORMAT:
        raise StyleError(f"'Style format: {STYLE_FORMAT}' is required (found {version!r})")
    body = seen_text.get("Body")
    if body is None or body.font is None or body.size is None:
        raise StyleError("Text → Body must give a font and a size, e.g. 'Body: Calibri, 10.5'")
    st.text = seen_text
    return st


def parse_margins(value: str, where: str) -> dict:
    if re.fullmatch(r"\d+(\.\d+)?", value):
        return dict.fromkeys(("top", "bottom", "left", "right"), float(value))
    margins = {}
    for part in value.split(","):
        m = re.fullmatch(r"\s*(top|bottom|left|right)\s+(\d+(?:\.\d+)?)\s*", part)
        if not m:
            raise StyleError(f"{where}: expected 'top 0.5, bottom 0.5, left 0.6, right 0.6'")
        margins[m.group(1)] = float(m.group(2))
    if set(margins) != {"top", "bottom", "left", "right"}:
        raise StyleError(f"{where}: give all four margins")
    if any(not 0.2 <= v <= 2 for v in margins.values()):
        raise StyleError(f"{where}: margins must be between 0.2 and 2 inches")
    return margins


def parse_layout(st: Style, key: str, value: str, where: str) -> None:
    if key == "Header alignment":
        if value.lower() not in ("left", "center"):
            raise StyleError(f"{where}: left or center")
        st.align = value.lower()
    elif key == "Contact separator":
        st.contact_sep = unquote(value)
    elif key == "Section order":
        order = [s.strip().lower() for s in value.split(",") if s.strip()]
        bad = [s for s in order if s not in SECTIONS]
        if bad or len(set(order)) != len(order):
            raise StyleError(f"{where}: sections must be distinct, from: {', '.join(SECTIONS)}")
        st.order = order
    elif key == "Section titles":
        for pair in filter(None, (p.strip() for p in value.split(";"))):
            name, eq, title = pair.partition("=")
            name = name.strip().lower()
            if not eq or name not in SECTIONS:
                raise StyleError(f"{where}: expected 'section = Title' pairs; '{pair}' isn't one")
            st.titles[name] = unquote(title)
    elif key == "Competencies":
        m = re.fullmatch(r"grid\s+([1-4])", value.strip(), re.I)
        if m:
            st.competencies = ("grid", int(m.group(1)))
        elif value.lower().startswith("inline"):
            st.competencies = ("inline", unquote(value[6:]) or " · ")
        else:
            raise StyleError(f"{where}: 'grid N' (1-4) or 'inline \" · \"'")
    elif key == "Bullet":
        if not value or len(unquote(value)) > 2:
            raise StyleError(f"{where}: one bullet character, e.g. •")
        st.bullet = unquote(value)
    elif key == "Dates":
        if value.lower() not in ("right", "inline"):
            raise StyleError(f"{where}: right or inline")
        st.dates = value.lower()
    elif key == "Accomplishments label":
        st.acc_label = unquote(value)
    elif key in ("Space after section heading (pt)", "Space between roles (pt)"):
        if not re.fullmatch(r"\d+(\.\d+)?", value):
            raise StyleError(f"{where}: a number of points")
        setattr(st, "space_heading" if "heading" in key else "space_roles", float(value))
    else:
        raise StyleError(f"{where}: unknown Layout setting")


# ---------------------------------------------------------------- content


def validate(c: dict) -> None:
    for k in ("name", "contact", "headline", "summary", "competencies", "highlights", "experience", "education"):
        if k not in c:
            fail(f"content.json missing '{k}'")
    if len(c["competencies"]) > LIMITS["competencies"]:
        fail("too many competencies (max 12)")
    if len(c["highlights"]) > LIMITS["highlights"]:
        fail("too many career highlights (max 5)")
    for j in c["experience"]:
        for k in ("company", "dates", "roles"):
            if k not in j:
                fail(f"experience entry missing '{k}'")
        for r in j["roles"]:
            for k in ("title", "dates", "bullets"):
                if k not in r:
                    fail(f"role missing '{k}'")


# ---------------------------------------------------------------- rendering


class Renderer:
    def __init__(self, st: Style):
        self.st = st
        self.d = docx.Document()
        body = self.d.element.body
        for child in list(body):
            if child.tag != qn("w:sectPr"):
                body.remove(child)
        sec = self.d.sections[0]
        width, height = PAGE_SIZES[st.size]
        sec.page_width, sec.page_height = Inches(width), Inches(height)
        for side, inches in st.margins.items():
            setattr(sec, f"{side}_margin", Inches(inches))
        self.text_width = Inches(width - st.margins["left"] - st.margins["right"])
        normal = self.d.styles["Normal"]
        b = st.t("Body")
        normal.font.name, normal.font.size = b.font, Pt(b.size)
        normal.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), b.font)
        normal.paragraph_format.space_after = Pt(0)
        normal.paragraph_format.space_before = Pt(0)
        self.num_id = self._bullet_numbering()

    # -- low-level helpers
    def run(self, p, text: str, role: str, **override):
        ts = replace(self.st.t(role), **override)
        r = p.add_run(text)
        f = r.font
        f.name, f.size = ts.font, Pt(ts.size)
        r._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), ts.font)
        f.bold, f.italic, f.all_caps, f.underline = ts.bold or None, ts.italic or None, ts.caps or None, ts.underline or None
        if ts.color:
            f.color.rgb = RGBColor.from_string(ts.color)
        return r

    def para(self, after: float = 0.0, align: str | None = None):
        p = self.d.add_paragraph()
        p.paragraph_format.space_after = Pt(after)
        if align == "center":
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        return p

    def _bullet_numbering(self) -> int:
        """Add a one-level bullet list using the style's bullet character; return its numId."""
        numbering = self.d.part.numbering_part.element
        abstract_ids = [int(a.get(qn("w:abstractNumId"))) for a in numbering.findall(qn("w:abstractNum"))]
        num_ids = [int(n.get(qn("w:numId"))) for n in numbering.findall(qn("w:num"))]
        aid, nid = max(abstract_ids, default=0) + 1, max(num_ids, default=0) + 1
        a = OxmlElement("w:abstractNum")
        a.set(qn("w:abstractNumId"), str(aid))
        lvl = OxmlElement("w:lvl")
        lvl.set(qn("w:ilvl"), "0")
        for tag, val in (("w:start", "1"), ("w:numFmt", "bullet"), ("w:lvlText", self.st.bullet), ("w:lvlJc", "left")):
            el = OxmlElement(tag)
            el.set(qn("w:val"), val)
            lvl.append(el)
        ppr, ind = OxmlElement("w:pPr"), OxmlElement("w:ind")
        ind.set(qn("w:left"), "300")
        ind.set(qn("w:hanging"), "200")
        ppr.append(ind)
        lvl.append(ppr)
        rpr, fonts = OxmlElement("w:rPr"), OxmlElement("w:rFonts")
        body_font = self.st.t("Body").font
        for attr in ("w:ascii", "w:hAnsi", "w:cs"):
            fonts.set(qn(attr), body_font)
        rpr.append(fonts)
        lvl.append(rpr)
        a.append(lvl)
        num = OxmlElement("w:num")
        num.set(qn("w:numId"), str(nid))
        ref = OxmlElement("w:abstractNumId")
        ref.set(qn("w:val"), str(aid))
        num.append(ref)
        # abstractNum elements must come before num elements
        first_num = numbering.find(qn("w:num"))
        if first_num is not None:
            first_num.addprevious(a)
        else:
            numbering.append(a)
        numbering.append(num)
        return nid

    def bullet(self, text: str, container=None):
        p = container.add_paragraph() if container is not None else self.d.add_paragraph()
        p.paragraph_format.space_after = Pt(1)
        num_pr = p._p.get_or_add_pPr().get_or_add_numPr()
        num_pr.get_or_add_ilvl().val = 0
        num_pr.get_or_add_numId().val = self.num_id
        self.run(p, text, "Body")
        return p

    def heading(self, section: str):
        title = self.st.titles.get(section, DEFAULT_TITLES[section])
        if not title:
            return
        p = self.para(after=self.st.space_heading)
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.keep_with_next = True
        self.run(p, title, "Section headings")
        if self.st.t("Section headings").rule:
            color = self.st.t("Section headings").color or "auto"
            bdr, bottom = OxmlElement("w:pBdr"), OxmlElement("w:bottom")
            for k, v in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", color)):
                bottom.set(qn(k), v)
            bdr.append(bottom)
            p._p.get_or_add_pPr().append(bdr)

    def dated_line(self, left_role: str, left: str, location: str, dates: str, after: float = 0.0):
        p = self.para(after=after)
        p.paragraph_format.keep_with_next = True
        self.run(p, left, left_role)
        if location:
            self.run(p, ", ", left_role, bold=False, italic=False, caps=False)
            self.run(p, location, "Location")
        if dates:
            if self.st.dates == "right":
                p.paragraph_format.tab_stops.add_tab_stop(self.text_width, WD_TAB_ALIGNMENT.RIGHT)
                p.add_run("\t")
            else:
                self.run(p, " | ", "Dates")
            self.run(p, dates, "Dates")
        return p

    # -- sections
    def header(self, c: dict):
        a = self.st.align
        self.run(self.para(align=a), c["name"], "Name")
        if c.get("headline"):
            self.run(self.para(after=1, align=a), c["headline"], "Headline")
        contact = [x for x in c.get("contact", []) if x]
        if contact:
            self.run(self.para(after=2, align=a), self.st.contact_sep.join(contact), "Contact")

    def summary(self, c):
        if c.get("summary"):
            self.heading("summary")
            self.run(self.para(after=2), c["summary"], "Body")

    def competencies(self, c):
        items = c.get("competencies") or []
        if not items:
            return
        self.heading("competencies")
        kind, arg = self.st.competencies
        if kind == "inline":
            self.run(self.para(after=2), arg.join(items), "Body")
            return
        cols = min(arg, len(items))
        rows = math.ceil(len(items) / cols)
        table = self.d.add_table(rows=1, cols=cols)
        table.alignment = WD_TABLE_ALIGNMENT.LEFT
        for i, cell in enumerate(table.rows[0].cells):
            chunk = items[i * rows:(i + 1) * rows]
            cell._tc.remove(cell.paragraphs[0]._p)
            for item in chunk:
                self.bullet(item, container=cell)
            if not chunk:
                cell.add_paragraph()

    def highlights(self, c):
        if c.get("highlights"):
            self.heading("highlights")
            for h in c["highlights"]:
                self.bullet(h)

    def experience(self, c):
        if not c.get("experience"):
            return
        self.heading("experience")
        gap = Pt(self.st.space_roles)
        for j, job in enumerate(c["experience"]):
            line = self.dated_line("Company", job["company"], job.get("location", ""), job["dates"])
            if j:
                line.paragraph_format.space_before = gap
            if job.get("description"):
                self.run(self.para(after=1), job["description"], "Company description")
            for i, role in enumerate(job["roles"]):
                line = self.dated_line("Role", role["title"], role.get("location", ""), role["dates"], after=1)
                if i:  # the space goes before each later role, so no empty spacer paragraphs
                    line.paragraph_format.space_before = gap
                if role.get("summary"):
                    self.run(self.para(after=1), role["summary"], "Body")
                if role["bullets"] and self.st.acc_label:
                    self.run(self.para(), self.st.acc_label, "Body", bold=True)
                for b in role["bullets"]:
                    self.bullet(b)

    def _pairs(self, section, items, first, second):
        if not items:
            return
        self.heading(section)
        for it in items:
            p = self.para(after=1)
            self.run(p, it[first], "Body", bold=True)
            if it.get(second):
                self.run(p, ", " + it[second], "Body")

    def education(self, c):
        self._pairs("education", c.get("education"), "degree", "school")

    def certifications(self, c):
        self._pairs("certifications", c.get("certifications"), "name", "detail")

    def additional(self, c):
        if c.get("additional"):
            self.heading("additional")
            for line in c["additional"]:
                self.run(self.para(after=1), line, "Body")

    def render(self, c: dict) -> None:
        self.header(c)
        for section in self.st.order:
            getattr(self, section)(c)

    def save(self, out: str) -> None:
        self.d.save(out)


def count_pages(path: str):
    try:
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", td, path],
                           check=True, capture_output=True, timeout=120)
            pdf = os.path.join(td, os.path.splitext(os.path.basename(path))[0] + ".pdf")
            out = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
            n = int([line for line in out.splitlines() if line.startswith("Pages:")][0].split()[1])
            with open(pdf, "rb") as fh:
                return n, fh.read()
    except Exception:
        return None, None


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--style", required=True)
    a.add_argument("--content", required=True)
    a.add_argument("--out", required=True)
    a.add_argument("--pdf", action="store_true")
    a = a.parse_args()
    try:
        with open(a.style, encoding="utf-8") as fh:
            st = parse_style(fh.read())
    except (OSError, StyleError) as e:
        fail(f"style file: {e}")
    with open(a.content, encoding="utf-8") as fh:
        c = json.load(fh)
    validate(c)
    r = Renderer(st)
    r.render(c)
    r.save(a.out)
    pages, pdf = count_pages(a.out)
    warnings = []
    if pages is None:
        warnings.append("could not render to PDF; page count unverified")
    elif pages > 2:
        warnings.append(f"resume is {pages} pages; the limit is 2")
    if a.pdf and pdf:
        with open(os.path.splitext(a.out)[0] + ".pdf", "wb") as fh:
            fh.write(pdf)
    print(json.dumps({"out": a.out, "pages": pages, "warnings": warnings}))


if __name__ == "__main__":
    main()
