from ingestion.chunker.base_chunker import BaseChunker
from ingestion.chunker.legal_chunker import LegalChunker
from ingestion.chunker.case_law_chunker import CaseLawChunker

class ChunkerFactory:
    @staticmethod
    def get_chunker(loai_van_ban: str) -> BaseChunker:
        if loai_van_ban == "an_le":
            return CaseLawChunker()
        else:
            # Luật, Nghị định, Thông tư, Nghị quyết... đều dùng chung LegalChunker
            return LegalChunker()
