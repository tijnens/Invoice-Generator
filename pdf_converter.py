
from pathlib import Path
import win32com.client


def convert_docx_to_pdf(docx_path, pdf_path):
    """Convert a DOCX to PDF using Microsoft Word."""

    docx_path = Path(docx_path).resolve()
    pdf_path = Path(pdf_path).resolve()

    if not docx_path.is_file():
        raise FileNotFoundError(f"DOCX not found: {docx_path}")

    word = None
    doc = None

    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0

        doc = word.Documents.Open(
            str(docx_path),
            ConfirmConversions=False,
            ReadOnly=True,
            AddToRecentFiles=False,
            NoEncodingDialog=True,
        )

        doc.ExportAsFixedFormat(
            OutputFileName=str(pdf_path),
            ExportFormat=17,  # PDF
        )

        if not pdf_path.is_file():
            raise RuntimeError("Word did not create the PDF.")

    finally:
        if doc is not None:
            doc.Close(False)

        if word is not None:
            word.Quit()
