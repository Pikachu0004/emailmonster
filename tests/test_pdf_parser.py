import pytest
from pathlib import Path
from pypdf import PdfWriter
from devengers_engine.parsers.extractor import FileExtractor


def test_pdf_extraction(tmp_path: Path):
    """Generates a sample PDF with participant records and verifies FileExtractor extracts them."""
    # Create a small text PDF or extract from text
    # Since pypdf is primarily a reader/merger, we can create a PDF with an empty page and annotations,
    # or write a minimal valid PDF raw byte stream:
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>
endobj
4 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
5 0 obj
<< /Length 140 >>
stream
BT
/F1 12 Tf
100 700 Td
(Kishan Sharma kishan@devengers.org Developer) Tj
0 -20 Td
(Sarah Connor sarah@cyberdyne.io Engineer) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000228 00000 n 
0000000305 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
495
%%EOF
"""
    pdf_file = tmp_path / "attendees.pdf"
    pdf_file.write_bytes(pdf_content)

    contacts, warnings = FileExtractor.extract_from_pdf(pdf_file)
    assert len(contacts) == 2
    assert contacts[0]["email"] == "kishan@devengers.org"
    assert contacts[0]["first_name"] == "Kishan"
    assert contacts[1]["email"] == "sarah@cyberdyne.io"
    assert contacts[1]["first_name"] == "Sarah"
