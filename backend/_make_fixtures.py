"""Generate a small PDF + DOCX fixture with known facts for smoke testing."""

import docx
from pypdf import PdfReader

PDF_FACTS = [
    ("Zephyr Logistics Annual Report 2025", 34),
    ("Total revenue for the year was $48.2 million.", 34),
    ("The CEO is Maria Okonkwo, appointed in March 2023.", 35),
    ("Headquarters are located in Rotterdam, Netherlands.", 35),
    ("Shipping delays reduced customer satisfaction by 12 percent.", 36),
    ("The board approved a new $6 million warehouse in Gdansk.", 37),
    ("Net profit margin improved from 4.1 to 7.8 percent.", 37),
]

doc = docx.Document()
doc.add_heading("Project Falcon Status Report", level=1)
doc.add_paragraph(
    "Project Falcon is an internal initiative to rebuild the customer portal. "
    "The project sponsor is Dr. Alan Reyes."
)
doc.add_paragraph("The launch date is scheduled for 15 November 2026.")
doc.add_paragraph("The allocated budget is $1.35 million.")
doc.add_paragraph("Key risk: the payment gateway migration has not completed testing.")

table = doc.add_table(rows=2, cols=2)
table.cell(0, 0).text = "Milestone"
table.cell(0, 1).text = "Owner"
table.cell(1, 0).text = "Data migration"
table.cell(1, 1).text = "Priya Raman"

doc.save("testdata_falcon.docx")

print("wrote testdata_falcon.docx")

# The PDF is built by writing a minimal file, then verified by the reader.
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    pdf_path = "testdata_zephyr.pdf"
    pdf = canvas.Canvas(pdf_path, pagesize=letter)
    title, _ = PDF_FACTS[0]
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(72, 740, title)
    pdf.setFont("Helvetica", 11)
    y = 700
    for line, _ in PDF_FACTS[1:]:
        pdf.drawString(72, y, line)
        y -= 20
    pdf.save()
    print(f"wrote {pdf_path} pages={len(PdfReader(pdf_path).pages)}")
except ImportError:
    print("reportlab unavailable")
