from ingestion.metadata.base_builder import BaseMetadataExtractor
from ingestion.metadata.models import KeywordMetadata
from ingestion.parser.structure import AnLe

class KeywordMetadataExtractor(BaseMetadataExtractor):
    def extract(self, node, **kwargs):
        if isinstance(node, AnLe):
            if node.tu_khoa:
                meta = KeywordMetadata(keywords=node.tu_khoa)
                self._ensure_metadata(node)
                node.metadata["search"] = meta.to_dict()
                
    def _ensure_metadata(self, node):
        if not hasattr(node, "metadata") or node.metadata is None:
            node.metadata = {}
