from pathlib import Path
import re
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, ListFlowable, ListItem,
    KeepTogether, HRFlowable
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "pdf"
OUT.mkdir(parents=True, exist_ok=True)
BLUE = colors.HexColor("#0D5B78")
TEAL = colors.HexColor("#00A88F")
INK = colors.HexColor("#12212B")
MUTED = colors.HexColor("#5F6F78")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="TitleNova", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=22, leading=25, textColor=INK, spaceAfter=7))
styles.add(ParagraphStyle(name="Kicker", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=BLUE, tracking=1.2, spaceAfter=3))
styles.add(ParagraphStyle(name="H1Nova", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=14.5, leading=17, textColor=BLUE, spaceBefore=7, spaceAfter=4))
styles.add(ParagraphStyle(name="H2Nova", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=10.5, leading=12, textColor=INK, spaceBefore=5, spaceAfter=2))
styles.add(ParagraphStyle(name="BodyNova", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.7, leading=9.5, textColor=INK, spaceAfter=2.5))
styles.add(ParagraphStyle(name="BulletNova", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.6, leading=9.3, leftIndent=10, firstLineIndent=0, textColor=INK))
styles.add(ParagraphStyle(name="NoteNova", parent=styles["BodyText"], fontName="Helvetica-Oblique", fontSize=7.7, leading=10, textColor=MUTED, borderColor=colors.HexColor("#D8E4E8"), borderWidth=.6, borderPadding=6, backColor=colors.HexColor("#F3F7F7")))
styles.add(ParagraphStyle(name="CodeNova", parent=styles["Code"], fontName="Courier", fontSize=6.1, leading=7.2, textColor=INK, backColor=colors.HexColor("#F2F5F6"), borderPadding=4))

def clean(text):
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`(.+?)`", r"<font name='Courier'>\1</font>", text)
    return text

def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D8E1E5")); canvas.line(18*mm, 14*mm, 192*mm, 14*mm)
    canvas.setFont("Helvetica", 7); canvas.setFillColor(MUTED)
    canvas.drawString(18*mm, 9*mm, "GoComet - Nova - Part 1")
    canvas.drawRightString(192*mm, 9*mm, f"Page {doc.page}")
    canvas.restoreState()

def parse(md_path):
    lines = md_path.read_text(encoding="utf-8").splitlines()
    story=[]; bullets=[]; code=[]; in_code=False
    def flush_bullets():
        nonlocal bullets
        if bullets:
            story.append(ListFlowable([ListItem(Paragraph(clean(x), styles["BulletNova"])) for x in bullets], bulletType="bullet", start="circle", leftIndent=14, bulletFontSize=5, spaceAfter=3))
            bullets=[]
    for line in lines:
        if line.startswith("```"):
            flush_bullets()
            if in_code:
                story.append(Paragraph("<br/>".join(clean(x).replace(" ", "&nbsp;") for x in code), styles["CodeNova"]))
                code=[]
            in_code=not in_code; continue
        if in_code: code.append(line); continue
        if line.startswith("- "):
            bullets.append(line[2:]); continue
        flush_bullets()
        if not line.strip():
            continue
        if line.startswith("# "):
            story += [Paragraph("GOCOMET · NOVA · FULL-STACK AI ENGINEER", styles["Kicker"]), Paragraph(clean(line[2:]), styles["TitleNova"]), HRFlowable(width="100%", thickness=2, color=TEAL, spaceAfter=8)]
        elif line.startswith("## "): story.append(Paragraph(clean(line[3:]), styles["H1Nova"]))
        elif line.startswith("### "): story.append(Paragraph(clean(line[4:]), styles["H2Nova"]))
        elif line.startswith("> "): story.append(Paragraph(clean(line[2:]), styles["NoteNova"]))
        else: story.append(Paragraph(clean(line), styles["BodyNova"]))
    flush_bullets()
    return story

def build(source, filename, title):
    doc=SimpleDocTemplate(str(OUT/filename), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=16*mm, bottomMargin=18*mm, title=title, author="Full-Stack AI Engineer candidate")
    doc.build(parse(ROOT/source), onFirstPage=footer, onLaterPages=footer)

build("docs/PRD.md", "Nova-Part-1-PRD.pdf", "Nova Trade Document Intelligence - PRD")
build("docs/TECHNICAL_WRITEUP.md", "Nova-Part-1-Technical-Writeup.pdf", "Nova Trade Document Intelligence - Technical Write-up")
print(f"Built PDFs in {OUT}")
