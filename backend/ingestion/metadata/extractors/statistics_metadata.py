from ingestion.metadata.base_builder import BaseMetadataExtractor
from ingestion.metadata.models import StatisticsMetadata
from ingestion.parser.structure import VanBan, AnLe, Dieu, Khoan, Diem
from ingestion.metadata.utils import count_words, count_characters

class StatisticsMetadataExtractor(BaseMetadataExtractor):
    def extract(self, node, **kwargs):
        if isinstance(node, (VanBan, AnLe)):
            pass
        elif isinstance(node, (Dieu, Khoan, Diem)):
            stats = StatisticsMetadata(
                word_count=count_words(node.text),
                char_count=count_characters(node.text)
            )
            self._ensure_metadata(node)
            node.metadata["statistics"] = stats.to_dict()
            
    def _ensure_metadata(self, node):
        if not hasattr(node, "metadata") or node.metadata is None:
            node.metadata = {}
