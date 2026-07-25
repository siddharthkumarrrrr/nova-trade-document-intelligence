from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parents[1] / "samples"
OUT.mkdir(exist_ok=True)

def clean():
    p = OUT / "clean-commercial-invoice.pdf"
    c = canvas.Canvas(str(p), pagesize=A4)
    w, h = A4
    c.setFont("Helvetica-Bold", 22); c.drawString(55, h-70, "COMMERCIAL INVOICE")
    c.setFont("Helvetica", 10); c.drawString(55, h-94, "Supplier: Orient Technology Export Co., Ltd.")
    c.line(55, h-108, w-55, h-108)
    rows = [
        ("Invoice Number", "INV-2026-0713"),
        ("Consignee", "ACME RETAIL INDIA PVT LTD"),
        ("HS Code", "847130"),
        ("Port of Loading", "Shanghai, China"),
        ("Port of Discharge", "Nhava Sheva, India"),
        ("Incoterms", "CIF"),
        ("Description", "Laptop computer accessories"),
        ("Gross Weight", "1,250 KG"),
    ]
    y=h-145
    for label,value in rows:
        c.setFont("Helvetica-Bold",10); c.drawString(65,y,label)
        c.setFont("Helvetica",11); c.drawString(205,y,value); y-=38
    c.setFillColorRGB(.06,.36,.47); c.rect(55,90,w-110,44,fill=1,stroke=0)
    c.setFillColorRGB(1,1,1); c.setFont("Helvetica-Bold",11); c.drawString(70,107,"Declared and certified true by the exporter")
    c.save()

def messy():
    p = OUT / "messy-commercial-invoice.pdf"
    c = canvas.Canvas(str(p), pagesize=A4)
    w,h=A4
    c.saveState(); c.translate(18,-12); c.rotate(1.2)
    c.setFillColorRGB(.89,.89,.86); c.rect(35,45,w-70,h-90,fill=1,stroke=0)
    c.setFillColorRGB(.22,.22,.22); c.setFont("Courier-Bold",19); c.drawString(55,h-72,"COMMERCIAL  INVOICE / SCAN")
    rows=[
      "Invoice No: INV-2026-0714",
      "Consignee: Acme Retail India Pvt Ltd",
      "HS: 8471?0",
      "Port of Loading: Shanghai",
      "Discharge: Nhava Sheva",
      "Incoterm: [illegible]",
      "Goods: laptop computer accessories",
      "Gross Wt: 1275 KG",
    ]
    y=h-125
    for i,row in enumerate(rows):
        c.setFont("Courier",10 if i in (2,5) else 11)
        c.drawString(62+(i%2)*3,y,row)
        if i in (2,5):
            c.setFillColorRGB(.62,.62,.6); c.rect(105,y-3,100,13,fill=1,stroke=0); c.setFillColorRGB(.22,.22,.22)
        y-=45
    c.setStrokeColorRGB(.65,.65,.62)
    for y in range(110,730,57): c.line(45,y,w-45,y+2)
    c.restoreState(); c.save()

clean(); messy()
print(f"Created samples in {OUT}")
