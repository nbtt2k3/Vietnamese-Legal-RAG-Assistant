from pathlib import Path

from .docx_loader import DOCXLoader
from .pdf_loader import PDFLoader


class LoaderFactory:

    LOADERS = {
        ".pdf": PDFLoader,
        ".docx": DOCXLoader,
    }

    @classmethod
    def get_loader(cls, file_path: str):

        extension = Path(file_path).suffix.lower()

        loader = cls.LOADERS.get(extension)

        if loader is None:
            raise ValueError(
                f"Unsupported file type: {extension}"
            )

        return loader()