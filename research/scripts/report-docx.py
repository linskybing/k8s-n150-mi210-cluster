"""Report Markdown -> Word (.docx) for Google Docs: upload to Google Drive, then Open with > Google Docs.
Run from research/:  uv run --with pypandoc_binary --with python-docx python scripts/report-docx.py [report.md]
Pandoc converts the Markdown; python-docx then applies the report format: A4, fonts, black headings that start
a new page per chapter, centered cover / captions / figures, grid tables with column widths fitted to the text."""
import re
import sys
from pathlib import Path

import pypandoc
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "report-2026-11-15.md")
OUT = SRC.with_suffix(".docx")
LATIN, CJK, MONO = "Times New Roman", "標楷體", "Courier New"
TEXT_W = Cm(16)  # A4 width 21 cm minus 2.5 cm margins
CAPTION = re.compile(r"^(表|圖) \d+ ")  # NSTC style: "表 1 標題", "圖 1 標題"
COVER = ("計畫名稱:", "報告名稱:", "日期:")

pypandoc.convert_file(str(SRC), "docx", outputfile=str(OUT),
                      extra_args=["--resource-path", str(SRC.parent), "--syntax-highlighting=none"])
doc = Document(str(OUT))


def set_fonts(rpr, latin, cjk):
    f = rpr.find(qn("w:rFonts"))
    if f is None:
        f = OxmlElement("w:rFonts")
        rpr.insert(0, f)
    for a in list(f.attrib):  # theme fonts override explicit ones
        if a.endswith("Theme"):
            del f.attrib[a]
    for a, v in (("ascii", latin), ("hAnsi", latin), ("cs", latin), ("eastAsia", cjk)):
        f.set(qn("w:" + a), v)


set_fonts(doc.styles.element.find(qn("w:docDefaults")).find(qn("w:rPrDefault")).find(qn("w:rPr")), LATIN, CJK)
for st in doc.styles:
    if st.type in (1, 2) and st.element.rPr is not None and st.element.rPr.find(qn("w:rFonts")) is not None:
        set_fonts(st.element.rPr, LATIN, CJK)
for name in ("Source Code", "Verbatim Char"):
    if name in [s.name for s in doc.styles]:
        set_fonts(doc.styles[name].element.get_or_add_rPr(), MONO, CJK)
        doc.styles[name].font.size = Pt(8.5 if name == "Source Code" else 11)
for name in ("Body Text", "First Paragraph", "Compact"):
    st = doc.styles[name]
    st.font.size = Pt(12)
    st.paragraph_format.line_spacing = 1.5 if name != "Compact" else 1.15
for lvl, size in ((1, 16), (2, 14), (3, 12)):
    st = doc.styles[f"Heading {lvl}"]
    st.font.size, st.font.bold, st.font.color.rgb = Pt(size), True, RGBColor(0, 0, 0)
    st.paragraph_format.space_before, st.paragraph_format.space_after = Pt(12), Pt(6)

for s in doc.sections:
    s.page_width, s.page_height = Cm(21), Cm(29.7)
    s.left_margin = s.right_margin = s.top_margin = s.bottom_margin = Cm(2.5)

# Cover (label lines and the names after them), captions, figures; an explicit page break before every chapter
# (Google Docs does not reliably keep a style-level "page break before")
cover = True
for p in doc.paragraphs:
    if p.style.name == "Heading 1":
        cover = False
        br = OxmlElement("w:p")
        br.append(OxmlElement("w:r"))
        br[0].append(OxmlElement("w:br"))
        br[0][0].set(qn("w:type"), "page")
        p._p.addprevious(br)
    t = p.text.strip()
    if cover and t:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(150 if t == COVER[0] else 24 if t in COVER else 6)
        for r in p.runs:
            r.font.size, r.font.bold = Pt(14 if t in COVER else 18), t not in COVER
    elif CAPTION.match(t) or p._p.xpath(".//w:drawing"):
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def width(text):  # in half-width characters
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in text)


def min_cm(cells):  # narrowest a column can be without breaking a Latin token or a cell of up to 4 CJK characters
    tokens = [w for c in cells[1:] for w in c.text.split() if all(ord(ch) <= 0x2E80 for ch in w)]
    units = max([width(w) for w in tokens] + [min(width(c.text), 8) for c in cells] + [4])
    return min(units, 22) * 0.18 + 0.45  # 10 pt half-width char ~0.18 cm, plus cell padding; longer paths may wrap


def border(tag, el):
    b = OxmlElement(tag)
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{side}")
        e.set(qn("w:val"), "single"), e.set(qn("w:sz"), "4"), e.set(qn("w:color"), "000000")
        b.append(e)
    el.append(b)


for t in doc.tables:
    tblpr = t._tbl.tblPr
    for old in tblpr.findall(qn("w:tblBorders")):
        tblpr.remove(old)
    border("w:tblBorders", tblpr)
    t.autofit = False
    tblw = tblpr.find(qn("w:tblW"))  # full text width for every table, so short tables do not shrink to content
    if tblw is None:
        tblw = OxmlElement("w:tblW")
        tblpr.append(tblw)
    tblw.set(qn("w:type"), "pct"), tblw.set(qn("w:w"), "5000")
    # column width ~ average text width, clamped so short columns stay readable and long ones do not take everything
    n = len(t.columns)
    w = [min(40, max(5, sum(width(r.cells[i].text) for r in t.rows) / len(t.rows))) for i in range(n)]
    cm = [16 * x / sum(w) for x in w]
    need = [min_cm(col.cells) for col in t.columns]
    short = sum(max(0, need[i] - cm[i]) for i in range(n))
    spare = sum(max(0, cm[i] - need[i]) for i in range(n))
    cm = [need[i] if cm[i] < need[i] else cm[i] - short * (cm[i] - need[i]) / spare for i in range(n)]
    for i, col in enumerate(t.columns):
        col.width = Cm(cm[i])
        for c in col.cells:
            c.width = col.width
    for r_i, row in enumerate(t.rows):
        for c in row.cells:
            for p in c.paragraphs:
                p.paragraph_format.line_spacing = 1.0
                for r in p.runs:
                    r.font.size = Pt(10)
                    if r_i == 0:
                        r.font.bold = True
        if r_i == 0:
            trpr = row._tr.get_or_add_trPr()
            if trpr.find(qn("w:tblHeader")) is None:
                trpr.append(OxmlElement("w:tblHeader"))  # repeat header row on each page
            for c in row.cells:
                shd = OxmlElement("w:shd")
                shd.set(qn("w:val"), "clear"), shd.set(qn("w:fill"), "E7E6E6")
                c._tc.get_or_add_tcPr().append(shd)

doc.save(str(OUT))

# self-check: every Markdown table and image made it into the .docx
md = SRC.read_text()
n_tables = len(re.findall(r"^\|[-|]+\|$", md, re.M))
n_images = len(re.findall(r"^!\[", md, re.M))
n_drawn = sum(bool(p._p.xpath(".//w:drawing")) for p in doc.paragraphs)
assert len(doc.tables) == n_tables, (len(doc.tables), n_tables)
assert n_drawn == n_images, (n_drawn, n_images)
print(f"{OUT}: {len(doc.tables)} tables, {n_drawn} figures, {sum(p.style.name == 'Heading 1' for p in doc.paragraphs)} chapters")
