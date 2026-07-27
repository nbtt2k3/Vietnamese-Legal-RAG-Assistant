from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph


class DOCXLoader:
    """
    Loader cho file DOCX.

    Đọc paragraph và table THEO ĐÚNG THỨ TỰ xuất hiện trong văn bản gốc,
    thay vì đọc hết paragraph rồi mới đọc table (dẫn đến xáo trộn nội dung).
    Lý do: bảng có thể nằm ở đầu (quốc hiệu, số hiệu văn bản), ở giữa
    (bảng trong Nghị quyết/Thông tư), hoặc ở cuối (phụ lục, mẫu biểu) —
    tùy từng loại văn bản (Bộ luật, Nghị định, Thông tư, Nghị quyết, Án lệ).
    """

    def load(self, file_path: str) -> dict:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(path)

        document = Document(path)

        lines = self._iter_block_items(document)

        return {
            "file_name": path.name,
            "file_path": str(path),
            "file_type": "docx",
            "documents": [
                {
                    "page": None,
                    "text": "\n".join(lines),
                }
            ],
        }

    def _iter_block_items(self, document) -> list[str]:
        """Duyệt qua body XML theo đúng thứ tự, phân biệt paragraph vs table."""
        body = document.element.body
        lines = []

        for child in body.iterchildren():
            if child.tag == qn("w:p"):
                text = Paragraph(child, document).text.strip()
                if text:
                    lines.append(text)

            elif child.tag == qn("w:tbl"):
                lines.extend(self._table_to_lines(Table(child, document)))

        return lines

    def _table_to_lines(self, table: Table) -> list[str]:
        """
        Chuyển đổi bảng thành định dạng Markdown Table.
        Dọn xuống dòng NỘI BỘ trong từng cell (vd 'QUỐC HỘI\\n--------\\nLuật số: X')
        thành khoảng trắng, để mỗi hàng bảng chỉ tạo đúng 1 dòng thật.
        """
        lines = []
        seen_tc = set()
        
        parsed_rows = []
        max_cols = 0
        
        for row in table.rows:
            cells = []
            for cell in row.cells:
                if cell._tc in seen_tc:
                    continue
                seen_tc.add(cell._tc)
                text = " ".join(cell.text.split())   # gộp mọi \n, khoảng trắng thừa thành 1 dòng sạch
                cells.append(text)
            if cells:
                parsed_rows.append(cells)
                max_cols = max(max_cols, len(cells))
                
        if not parsed_rows:
            return []
            
        for i, row_cells in enumerate(parsed_rows):
            # Bù thêm ô trống nếu hàng này thiếu cột (do trộn ô phức tạp)
            row_cells.extend([""] * (max_cols - len(row_cells)))
            
            lines.append("| " + " | ".join(row_cells) + " |")
            
            # Thêm dòng phân cách Markdown sau dòng tiêu đề (hàng đầu tiên)
            if i == 0:
                lines.append("|" + "|".join(["---"] * max_cols) + "|")
                
        return lines