from retrieval.models import QueryIntent, RetrievedChunk
from sentence_transformers import CrossEncoder
from pathlib import Path
from app.logger import logger
from app.config import settings

class LegalReranker:
    def __init__(self, model_name: str | None = None):
        if model_name is None:
            model_name = str(settings.project_root / "data" / "models" / "BAAI" / "bge-reranker-v2-m3")

        # BUG-01 FIX: Khởi tạo meta_bonus_weights TRƯỚC các early return
        # để tránh AttributeError nếu encoder bị disabled hoặc model không tìm thấy.
        self.meta_bonus_weights = {
            "bo_luat": 0.8,
            "luat": 0.6,
            "nghi_dinh": 0.4,
            "thong_tu": 0.2,
        }
        try:
            import os, yaml
            rules_path = os.path.join(os.path.dirname(__file__), "rules.yaml")
            with open(rules_path, "r", encoding="utf-8") as f:
                rules_data = yaml.safe_load(f)
                weights = rules_data.get("domain_config", {}).get("meta_bonus_weights")
                if weights:
                    self.meta_bonus_weights = weights
        except Exception as e:
            logger.warning(f"Failed to load meta_bonus_weights: {e}")

        logger.info(f"Loading CrossEncoder Reranker: {model_name}")
        if not settings.cross_encoder_reranking_enabled:
            logger.info("Cross-encoder reranking is disabled; using deterministic hybrid fallback.")
            self.encoder = None
            return
        if not Path(model_name).is_dir():
            logger.warning(
                "Local reranker model is unavailable; using deterministic hybrid fallback. "
                "Download and configure a local model before enabling cross-encoder reranking."
            )
            self.encoder = None
            return
        try:
            self.encoder = CrossEncoder(model_name, max_length=512)
        except Exception as e:
            logger.error(f"Failed to load CrossEncoder: {e}")
            self.encoder = None

    def rerank(self, query_intent: QueryIntent, candidates: list[RetrievedChunk], top_k: int = 12) -> list[RetrievedChunk]:
        if not candidates:
            return []

        # If model failed to load, fallback to original score or 0
        if not self.encoder:
            for item in candidates:
                item.scores["final"] = (
                    item.scores.get("hybrid", 0.0)
                    + 0.05 * item.scores.get("metadata", 0.0)
                    + 0.005 * item.scores.get("lexical", 0.0)
                    + 0.01 * item.scores.get("vector", 0.0)
                )
            candidates.sort(key=lambda item: item.scores.get("final", 0.0), reverse=True)
            return self._diversify(candidates, top_k)

        # Build pairs for CrossEncoder (query, passage)
        # Combine title, dieu_title and chunk text for a comprehensive passage
        pairs = []
        for item in candidates:
            meta = item.metadata
            title = meta.get("ten", "")
            dieu_title = meta.get("dieu_title", "")
            text = item.text
            
            passage = f"{title} - {dieu_title}. {text}".strip()
            pairs.append([query_intent.raw_query, passage])

        # Predict relevance scores in batches for better performance
        # Note: num_workers is kept at 0 (default) to prevent PyTorch DataLoader crashing on Windows
        scores = self.encoder.predict(pairs, batch_size=32)
        
        # Phase 4 Reranking Features
        for item, score in zip(candidates, scores):
            item.scores["cross_encoder"] = float(score)
            meta_bonus = 0.0
            meta = item.metadata
            
            # 1. Citation Exact Match (Factual Similarity override)
            citation = str(meta.get("citation", "")).lower()
            if meta.get("citation") and any(target.lower() in citation for target in query_intent.citation_targets):
                meta_bonus += 3.0
                
            # 2. Legal Authority Hierarchy
            loai = str(meta.get("loai_van_ban", ""))
            meta_bonus += self.meta_bonus_weights.get(loai, 0.0)
            if meta.get("document_role") == "case_law": meta_bonus += 0.7
                
            # 3. Effective Status
            validity = str(meta.get("validity_status", ""))
            if validity in ("dang_co_hieu_luc", "co_hieu_luc_va_thay_the_van_ban_khac"):
                meta_bonus += 0.5
            elif validity == "het_hieu_luc":
                meta_bonus -= 1.0 # Penalize if it slipped through
                
            # 4. Temporal Compatibility
            year_hint = query_intent.time_context.get("year_hint")
            if year_hint:
                if year_hint in str(meta.get("effective_date", "")) or year_hint in str(meta.get("effective_from", "")):
                    meta_bonus += 0.8

            item.scores["final"] = float(score) + meta_bonus

        candidates.sort(key=lambda item: item.scores.get("final", 0.0), reverse=True)
        return self._diversify(candidates, top_k)

    def _diversify(self, ranked: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        selected: list[RetrievedChunk] = []
        per_doc_counts: dict[str, int] = {}

        for item in ranked:
            doc_id = item.doc_id or item.chunk_id
            document_role = item.metadata.get("document_role")
            limit = 2 if document_role == "case_law" else 3
            if per_doc_counts.get(doc_id, 0) >= limit:
                continue
            selected.append(item)
            per_doc_counts[doc_id] = per_doc_counts.get(doc_id, 0) + 1
            if len(selected) >= top_k:
                break
        return selected
