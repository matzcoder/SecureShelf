"""Count what you collected: python tools/count_pages.py
PDFs: real page count. HTML: 1 page each. Code: number of source files."""
import os

from pypdf import PdfReader

CODE = (".py", ".java", ".go", ".c", ".h", ".js", ".ts", ".scala", ".rs", ".kt", ".yaml", ".yml")
pdf_pages = html = code = broken = 0
for folder, _, files in os.walk("data/raw"):
    for f in files:
        p = os.path.join(folder, f)
        low = f.lower()
        if low.endswith(".pdf"):
            try:
                n = len(PdfReader(p).pages)
                pdf_pages += n
                print(f"{n:5d} pages {p}")
            except Exception as e:
                broken += 1
                print(" BROKEN ", p, e.__class__.__name__)
        elif low.endswith((".html", ".htm")):
            html += 1
        elif low.endswith(CODE):
            code += 1
print(f"\nPDF pages: {pdf_pages} | HTML pages: {html} | code files: {code} | broken files: {broken}")
print(f"TOTAL pages for DATASET.md: {pdf_pages + html}")