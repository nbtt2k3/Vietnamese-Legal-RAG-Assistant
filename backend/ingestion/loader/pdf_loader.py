from pathlib import Path

import fitz


class PDFLoader:
    """
    Loader cho file PDF.
    Đọc từng trang và trả về cấu trúc dữ liệu chuẩn.
    """

    def load(self, file_path: str) -> dict:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(path)
            
        print(f"\n[WARNING] Đang dùng pdf_loader cho file: {path.name}")
        print("          Thư viện PyMuPDF có thể làm vỡ cấu trúc Bảng biểu (Tables) và lẫn Header/Footer.")
        print("          Khuyến nghị: Nên sử dụng file gốc DOCX hoặc dùng LlamaParse cho PDF.\n")

        document = fitz.open(path)

        pages = []

        for page_index, page in enumerate(document, start=1):
            text = page.get_text("text")

            pages.append(
                {
                    "page": page_index,
                    "text": text.strip(),
                }
            )

        document.close()

        return {
            "file_name": path.name,
            "file_path": str(path),
            "file_type": "pdf",
            "documents": pages,
        }