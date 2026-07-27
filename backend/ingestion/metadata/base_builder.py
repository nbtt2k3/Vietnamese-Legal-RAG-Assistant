"""
Base class for metadata builders/extractors.
"""
from abc import ABC, abstractmethod
from typing import Union, Any

class BaseMetadataExtractor(ABC):
    """
    Interface cho tất cả các metadata extractor.
    Mỗi extractor sẽ nhận một object (VanBan, AnLe, Dieu, Khoan...) 
    và gán/cập nhật thông tin vào trường `metadata` của object đó.
    """
    
    @abstractmethod
    def extract(self, node: Any, **kwargs):
        """
        Trích xuất và gán metadata vào `node.metadata`.
        `node` có thể là VanBan, AnLe, hoặc các node con (Dieu, Khoan, Diem).
        """
        pass
