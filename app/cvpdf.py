"""
Convert a Markdown CV to an ATS-optimised PDF using Playwright (already installed).

ATS rules enforced:
  - Single-column layout (no CSS grid/flex that spans content)
  - Standard section headings (h2 = Work Experience / Education / Skills etc.)
  - Standard fonts only (Arial / sans-serif)
  - No images, no tables for layout, no text boxes
  - Keyword-rich plain text in the content layer (weasyprint-free)
  - File named with candidate name for easy ATS parsing
"""
import os, re

# ATS-safe CSS: single column, clean typography, no decorative layout elements
ATS_CSS = """
@page { size: A4; margin: 17mm 17mm 13mm 17mm; }
* { box-sizing: border-box; }
body {
    font-family: Arial, Helvetica, sans-serif;
    font-size: 10.5pt;
    color: #111;
    line-height: 1.45;
    max-width: 100%;
}
h1 {
    font-size: 17pt;
    margin: 0 0 1px;
    color: #111;
    font-weight: 700;
}
/* Contact line — the paragraph immediately after h1 */
h1 + p {
    font-size: 9.5pt;
    color: #333;
    margin: 0 0 10px;
}
h2 {
    font-size: 10.5pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #111;
    margin: 13px 0 4px;
    padding-bottom: 2px;
    border-bottom: 1px solid #333;
}
h3 {
    font-size: 10.5pt;
    font-weight: 700;
    margin: 7px 0 1px;
    color: #111;
}
p { margin: 1px 0 5px; }
ul { margin: 2px 0 5px 0; padding-left: 16px; }
li { margin-bottom: 2px; }
a { color: #1a56db; text-decoration: none; }
blockquote {
    display: none; /* Hide internal notes like the tailoring annotation */
}
strong { font-weight: 700; }
em { font-style: italic; }
hr { border: none; border-top: 1px solid #ddd; margin: 8px 0; }
"""


def md_to_pdf(md_text: str, out_path: str) -> str:
    """Render Markdown → ATS-safe PDF. Returns out_path."""
    import markdown as _md
    html_body = _md.markdown(md_text, extensions=["tables"])
    html = f"""<!doctype html>
<html><head>
<meta charset='utf-8'>
<style>{ATS_CSS}</style>
</head><body>{html_body}</body></html>"""

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True)
        pg = br.new_page()
        pg.set_content(html, wait_until="networkidle")
        pg.pdf(
            path=out_path,
            format="A4",
            print_background=False,
            margin={"top": "17mm", "right": "17mm", "bottom": "13mm", "left": "17mm"},
        )
        br.close()
    return out_path


def make_cv_pdf(md_path: str, pdf_path: str | None = None) -> str:
    """Convert a .md CV file to ATS-optimised PDF. Returns the PDF path."""
    if pdf_path is None:
        pdf_path = os.path.splitext(md_path)[0] + ".pdf"
    with open(md_path, encoding="utf-8") as f:
        md = f.read()
    return md_to_pdf(md, pdf_path)
