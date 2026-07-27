"""
Factory to create Metadata Builders.
"""
from ingestion.metadata.metadata_builder import MetadataBuilder
from ingestion.metadata.extractors.document_metadata import DocumentMetadataExtractor
from ingestion.metadata.extractors.hierarchy_metadata import HierarchyMetadataExtractor
from ingestion.metadata.extractors.legal_retrieval_metadata import LegalRetrievalMetadataExtractor
from ingestion.metadata.extractors.statistics_metadata import StatisticsMetadataExtractor
from ingestion.metadata.extractors.keyword_metadata import KeywordMetadataExtractor

class MetadataFactory:
    @staticmethod
    def get_builder(loai_van_ban: str) -> MetadataBuilder:
        extractors = [
            DocumentMetadataExtractor(),
            LegalRetrievalMetadataExtractor(),
            StatisticsMetadataExtractor()
        ]
        
        if loai_van_ban == "an_le":
            extractors.append(KeywordMetadataExtractor())
        else:
            extractors.append(HierarchyMetadataExtractor())
            
        return MetadataBuilder(extractors)
