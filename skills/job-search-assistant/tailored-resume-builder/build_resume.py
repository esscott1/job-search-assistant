#!/usr/bin/env python3
"""Fill the Job-Seeker-6 resume template with selected content.

Usage: build_resume.py --template T.docx --content content.json --out out.docx [--pdf]

The template supplies every format decision (page size, margins, styles,
numbering, the competencies table). This script only clones the template's own
paragraphs by role and swaps in text, so the result matches the template.
Prints JSON: {"out": ..., "pages": N or null, "warnings": [...]}; exit 2 on bad input.
"""
import argparse, copy, json, os, subprocess, sys, tempfile
import docx
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
RIGHT_TAB = 10800  # twips: 7.5in text width on Letter with 0.5in side margins

# Prototype paragraphs, as indexes into the body of Job-Seeker-6-Resume-Template-.docx
PROTO = dict(title=0, contact=1, headline=2, summary=4, section=5, table=7,
             highlight=11, company=20, company_desc=21, role=22, role_summary=23,
             key_acc=25, bullet=26, spacer=33, edu_title=78, degree=79, school=80,
             addl_title=88, addl=89)
LIMITS = dict(competencies=12, highlights=5, summary_chars=700)


def fail(msg):
    print(json.dumps({"error": msg})); sys.exit(2)


def validate(c):
    for k in ("name", "contact", "headline", "summary", "competencies", "highlights",
              "experience", "education"):
        if k not in c: fail(f"content.json missing '{k}'")
    if len(c["competencies"]) > LIMITS["competencies"]: fail("too many competencies (max 12)")
    if len(c["highlights"]) > LIMITS["highlights"]: fail("too many career highlights (max 5)")
    for j in c["experience"]:
        for k in ("company", "dates", "roles"):
            if k not in j: fail(f"experience entry missing '{k}'")
        for r in j["roles"]:
            for k in ("title", "dates", "bullets"):
                if k not in r: fail(f"role missing '{k}'")


def clean(p, keep_rpr_from=None):
    """Remove all runs/hyperlinks from p; return a copy of the rPr of the first text run."""
    rpr = None
    for r in p.iter(W + "r"):
        if r.find(W + "t") is not None and r.find(W + "rPr") is not None:
            rpr = copy.deepcopy(r.find(W + "rPr")); break
    for ch in list(p):
        if ch.tag != W + "pPr": p.remove(ch)
    return rpr


def add_run(p, text, rpr=None, bold=None, italic=None):
    r = OxmlElement("w:r")
    if rpr is not None:
        rp = copy.deepcopy(rpr)
        for tag, val in (("w:b", bold), ("w:i", italic)):
            if val is None: continue
            for e in rp.findall(qn(tag)): rp.remove(e)
            if val: rp.insert(0, OxmlElement(tag))
        r.append(rp)
    elif bold or italic:
        rp = OxmlElement("w:rPr")
        if bold: rp.append(OxmlElement("w:b"))
        if italic: rp.append(OxmlElement("w:i"))
        r.append(rp)
    t = OxmlElement("w:t"); t.text = text; t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    r.append(t); p.append(r); return r


def add_tab(p, rpr=None):
    r = OxmlElement("w:r")
    if rpr is not None: r.append(copy.deepcopy(rpr))
    r.append(OxmlElement("w:tab")); p.append(r)


def set_right_tab(p):
    ppr = p.find(W + "pPr")
    tabs = ppr.find(W + "tabs")
    if tabs is not None: ppr.remove(tabs)
    tabs = OxmlElement("w:tabs"); tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "right"); tab.set(qn("w:pos"), str(RIGHT_TAB)); tabs.append(tab)
    # schema order: pStyle, keepNext..., numPr, ..., tabs, ... spacing, ind, jc
    after = [W + x for x in ("pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr",
                             "widowControl", "numPr", "suppressLineNumbers", "pBdr", "shd")]
    idx = 0
    for i, ch in enumerate(list(ppr)):
        if ch.tag in after: idx = i + 1
    ppr.insert(idx, tabs)
    ind = ppr.find(W + "ind")  # drop hanging indent so the date tab lands at the margin
    if ind is not None: ppr.remove(ind)


class Builder:
    def __init__(self, template):
        self.d = docx.Document(template)
        body = self.d.element.body
        self.kids = list(body.iterchildren())
        self.proto = {k: copy.deepcopy(self.kids[i]) for k, i in PROTO.items()}
        sect = body.find(W + "sectPr")
        for ch in self.kids:
            if ch is not sect: body.remove(ch)
        self.body, self.sect = body, sect

    def emit(self, el): self.sect.addprevious(el); return el

    def para(self, key, text, **kw):
        p = copy.deepcopy(self.proto[key]); rpr = clean(p)
        if text: add_run(p, text, rpr, **kw)
        return self.emit(p)

    def line_with_dates(self, key, left_bold, left_rest, dates, rest_italic=False):
        p = copy.deepcopy(self.proto[key]); rpr = clean(p)
        set_right_tab(p)
        if key == "company":  # Heading 2 company line: company bold via style, location plain
            add_run(p, left_bold, rpr, bold=True)
            if left_rest: add_run(p, ", " + left_rest, rpr, bold=False)
            add_tab(p); add_run(p, dates, rpr, bold=False)
        else:
            add_run(p, left_bold, rpr, bold=True)
            if left_rest: add_run(p, ", " if not left_bold.endswith(",") else " ", rpr, bold=False); add_run(p, left_rest, rpr, bold=False, italic=True)
            add_tab(p, rpr); add_run(p, dates, rpr, bold=False, italic=False)
        return self.emit(p)

    def competencies(self, items):
        tbl = copy.deepcopy(self.proto["table"])
        cells = tbl.findall(".//" + W + "tc")
        bullet = None
        for p in cells[0].findall(W + "p"):
            if p.find(W + "pPr/" + W + "numPr") is not None: bullet = copy.deepcopy(p); break
        rpr = clean(bullet)
        per = -(-len(items) // len(cells)) if items else 0
        for i, tc in enumerate(cells):
            for p in tc.findall(W + "p"): tc.remove(p)
            chunk = items[i * per:(i + 1) * per]
            for it in chunk:
                p = copy.deepcopy(bullet); add_run(p, it, rpr); tc.append(p)
            if not chunk: tc.append(OxmlElement("w:p"))
        for tr in tbl.findall(W + "tr"):  # let the table size to its content
            h = tr.find(W + "trPr/" + W + "trHeight")
            if h is not None: h.getparent().remove(h)
        return self.emit(tbl)

    def build(self, c):
        self.para("title", c["name"])
        self.para("contact", "  ·  ".join(c["contact"]))
        self.para("headline", c["headline"])
        self.para("spacer", "")
        self.para("summary", c["summary"])
        self.para("section", "CORE COMPETENCIES"); self.competencies(c["competencies"])
        self.para("spacer", "")
        self.para("section", "CAREER HIGHLIGHTS")
        for h in c["highlights"]: self.para("highlight", h)
        self.para("spacer", "")
        self.para("section", "PROFESSIONAL EXPERIENCE")
        for j in c["experience"]:
            self.line_with_dates("company", j["company"], j.get("location", ""), j["dates"])
            if j.get("description"): self.para("company_desc", j["description"], italic=True)
            for r in j["roles"]:
                self.line_with_dates("role", r["title"], r.get("location", ""), r["dates"])
                if r.get("summary"): self.para("role_summary", r["summary"])
                if r["bullets"]:
                    self.para("key_acc", "Key Accomplishments:", bold=True)
                    for b in r["bullets"]: self.para("bullet", b)
                self.para("spacer", "")
        self.para("edu_title", "Education and Certifications")
        for e in c["education"]:
            self.para("degree", e["degree"], bold=True)
            if e.get("school"): self.para("school", e["school"])
        for e in c.get("certifications", []):
            self.para("degree", e["name"], bold=True)
            if e.get("detail"): self.para("school", e["detail"])
        if c.get("additional"):
            self.para("addl_title", "Additional Information")
            for a in c["additional"]: self.para("addl", a)

    def save(self, out): self.d.save(out)


def count_pages(path):
    try:
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", td, path],
                           check=True, capture_output=True, timeout=120)
            pdf = os.path.join(td, os.path.splitext(os.path.basename(path))[0] + ".pdf")
            out = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
            n = int([l for l in out.splitlines() if l.startswith("Pages:")][0].split()[1])
            return n, open(pdf, "rb").read()
    except Exception:
        return None, None


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--template", required=True); a.add_argument("--content", required=True)
    a.add_argument("--out", required=True); a.add_argument("--pdf", action="store_true")
    a = a.parse_args()
    c = json.load(open(a.content)); validate(c)
    b = Builder(a.template); b.build(c); b.save(a.out)
    pages, pdf = count_pages(a.out)
    warnings = []
    if pages is None: warnings.append("could not render to PDF; page count unverified")
    elif pages != 2: warnings.append(f"resume is {pages} pages; target is exactly 2")
    if a.pdf and pdf: open(os.path.splitext(a.out)[0] + ".pdf", "wb").write(pdf)
    print(json.dumps({"out": a.out, "pages": pages, "warnings": warnings}))


if __name__ == "__main__":
    main()
