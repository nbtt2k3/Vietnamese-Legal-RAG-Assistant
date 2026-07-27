from abc import ABC, abstractmethod
from typing import List
from ingestion.chunker.models import Chunk

class BaseChunker(ABC):
    @abstractmethod
    def chunk(self, data: dict) -> List[Chunk]:
        """
        Nhận vào JSON dict của văn bản từ data/metadata/
        Trả về danh sách các đối tượng Chunk.
        """
        pass
