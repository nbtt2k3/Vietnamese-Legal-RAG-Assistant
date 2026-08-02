from pathlib import Path

import fitz
from app.core.config import settings


class PDFLoader:
    """
    Loader cho file PDF.
    Đọc từng trang và trả về cấu trúc dữ liệu chuẩn.
    """

    def load(self, file_path: str) -> dict:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(path)
            
        print(f"\n[INFO] Đang dùng PyMuPDF cho file PDF: {path.name}")
        print("       OCR fallback sẽ chỉ chạy trên các trang có quá ít text.")

        document = fitz.open(path)

        pages = []

        for page_index, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            ocr_used = False
            if settings.pdf_ocr_enabled and len(text) < settings.pdf_ocr_min_chars_per_page:
                ocr_text = self._ocr_page(page)
                if ocr_text:
                    text = ocr_text
                    ocr_used = True

            pages.append(
                {
                    "page": page_index,
                    "text": text,
                    "ocr_used": ocr_used,
                }
            )

        document.close()

        ocr_pages = [item["page"] for item in pages if item["ocr_used"]]
        if ocr_pages:
            print(f"[INFO] OCR fallback đã chạy trên trang: {ocr_pages}")
        else:
            print("[INFO] Không cần OCR fallback; PDF đã có text native đủ dùng.")

        return {
            "file_name": path.name,
            "file_path": str(path),
            "file_type": "pdf",
            "documents": pages,
        }

    def _ocr_page(self, page) -> str:
        """OCR only sparse/scanned pages when optional OCR dependencies exist.

        Tesseract itself is an external binary. If it or its language data is
        unavailable, ingestion keeps the native PDF text and records no OCR
        result rather than failing the whole corpus.
        """
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            return ""

        try:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
            return pytesseract.image_to_string(image, lang=settings.pdf_ocr_language).strip()
        except Exception:
            return ""
