import fitz
import logging

logger = logging.getLogger(__name__)


def extract_text(path):
    """
    Extract text from a PDF file.
    Uses get_text("text") for normal content and find_tables()
    for structured tabular data (benefits, limits, sub-limits).
    Avoids the previous bug of extracting everything twice.
    """
    doc = fitz.open(path)
    full_text = ""

    for page_num, page in enumerate(doc, start=1):
        # Try table extraction first — get table bounding boxes to exclude
        # table regions from get_text() and avoid duplicate content
        table_rects = []
        table_text = ""
        try:
            tables = page.find_tables()
            for table in tables:
                table_rects.append(table.bbox)  # (x0, y0, x1, y1)
                table_data = table.extract()
                for row in table_data:
                    cells = [str(cell).strip() for cell in row if cell]
                    if cells:
                        table_text += " | ".join(cells) + "\n"
        except Exception:
            # find_tables() may not be available in older PyMuPDF versions
            pass

        # Extract non-table text by clipping out table regions
        if table_rects:
            # Get all text blocks and filter out those inside table areas
            blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, type)
            for block in blocks:
                bx0, by0, bx1, by1 = block[:4]
                block_text = block[4] if len(block) > 4 else ""
                block_type = block[6] if len(block) > 6 else 0  # 0 = text, 1 = image

                if block_type != 0:
                    continue

                # Check if this block overlaps any table rect
                in_table = False
                for tx0, ty0, tx1, ty1 in table_rects:
                    if bx0 >= tx0 - 2 and by0 >= ty0 - 2 and bx1 <= tx1 + 2 and by1 <= ty1 + 2:
                        in_table = True
                        break

                if not in_table:
                    full_text += str(block_text)

            # Append structured table text separately
            full_text += "\n" + table_text
        else:
            # No tables on this page — simple extraction
            full_text += page.get_text("text")

        full_text += "\n\n"

    doc.close()
    logger.info(f"Extracted {len(full_text)} characters from {path}")
    return full_text