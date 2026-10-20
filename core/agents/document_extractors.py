"""Document extraction tools for Word and Excel files."""

from typing import Dict, Any, List

def extract_word_document(file_path: str) -> Dict[str, Any]:
    """
    Extract text and tables from Word document.

    Args:
        file_path: Path to .docx file

    Returns:
        Document content and metadata
    """
    try:
        from docx import Document
    except ImportError:
        return {"error": "python-docx not installed"}

    try:
        doc = Document(file_path)

        # Extract text
        text_content = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_content.append(paragraph.text)

        # Extract tables
        tables = []
        for table in doc.tables:
            table_data = []
            for row in table.rows:
                row_data = [cell.text.strip() for cell in row.cells]
                table_data.append(row_data)
            tables.append(table_data)

        return {
            "success": True,
            "text": "\n".join(text_content),
            "tables": tables,
            "paragraph_count": len(text_content),
            "table_count": len(tables)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def extract_excel_enhanced(file_path: str, sheet_limit: int = 5) -> Dict[str, Any]:
    """
    Extract structured data from Excel with JSON and preview.

    Args:
        file_path: Path to .xlsx file
        sheet_limit: Max sheets to process

    Returns:
        Structured data with preview
    """
    try:
        import openpyxl
        import json
    except ImportError:
        return {"error": "openpyxl not installed"}

    try:
        workbook = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        sheets_data = {}

        for sheet_name in list(workbook.sheetnames)[:sheet_limit]:
            sheet = workbook[sheet_name]
            data = []

            for row in sheet.iter_rows(values_only=True):
                if any(cell is not None for cell in row):
                    data.append(list(row))

            sheets_data[sheet_name] = {
                "data": data,
                "rows": len(data),
                "cols": len(data[0]) if data else 0
            }

        return {
            "success": True,
            "sheets": sheets_data,
            "sheet_count": len(sheets_data)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}