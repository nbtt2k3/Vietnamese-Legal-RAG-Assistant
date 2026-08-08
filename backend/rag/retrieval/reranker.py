from rag.retrieval.models import QueryIntent, RetrievedChunk
from sentence_transformers import CrossEncoder
from pathlib import Path
from app.core.config import settings
from app.core.logging import logger
from rag.retrieval.text_utils import contains_normalized, normalize_for_match, tokenize_for_bm25

class LegalReranker:
    def __init__(self, model_name: str | None = None):
        self.provider = str(settings.reranker_provider or "auto").strip().lower()
        self.jina_api_key = settings.jina_api_key
        self.jina_model = settings.jina_reranker_model
        self.jina_url = settings.jina_reranker_url
        self.jina_timeout_seconds = settings.jina_timeout_seconds

        if model_name is None:
            configured_name = settings.reranker_model_name
            local_model = settings.project_root / "data" / "models" / "BAAI" / "bge-reranker-v2-m3"
            # Prefer the checked-in/local model when the configured value is a
            # Hugging Face model id. This keeps production startup offline and
            # makes the .env setting actually control which model is selected.
            model_name = str(local_model) if local_model.is_dir() else configured_name

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

        if (
            settings.cross_encoder_reranking_enabled
            and self.provider in {"auto", "jina"}
            and self.jina_api_key
        ):
            self.encoder = None
            self.using_jina = True
            logger.info("Using Jina AI reranker: %s", self.jina_model)
            return

        self.using_jina = False
        if self.provider == "jina" and not self.jina_api_key:
            logger.warning("RERANKER_PROVIDER=jina but JINA_API_KEY is missing; using local fallback.")

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

    def rerank(
        self,
        query_intent: QueryIntent,
        candidates: list[RetrievedChunk],
        top_k: int = 12,
        score_cache: dict[tuple[str, str], float] | None = None,
    ) -> list[RetrievedChunk]:
        if not candidates:
            return []

        # If model failed to load, fallback to original score or 0
        if not self.encoder:
            if getattr(self, "using_jina", False):
                try:
                    # Jina is remote and the pipeline reranks twice (before
                    # and after cross-document expansion). Reuse the same
                    # request-scoped cache as the local CrossEncoder path.
                    active_cache = score_cache if score_cache is not None else {}
                    uncached = []
                    uncached_keys = []
                    for item in candidates:
                        key = (query_intent.raw_query, item.chunk_id)
                        if key not in active_cache:
                            uncached.append(self._passage(item))
                            uncached_keys.append(key)
                    if uncached:
                        scores = self._jina_predict(query_intent.raw_query, uncached)
                        for key, score in zip(uncached_keys, scores):
                            active_cache[key] = float(score)
                    return self._finish_rerank(query_intent, candidates, active_cache, top_k=top_k)
                except Exception as exc:
                    logger.warning("Jina reranker failed; falling back to local/deterministic ranking: %s", exc)
                    self.using_jina = False

            for item in candidates:
                item.scores["final"] = (
                    item.scores.get("hybrid", 0.0)
                    + 0.05 * item.scores.get("metadata", 0.0)
                    + 0.005 * item.scores.get("lexical", 0.0)
                    + 0.01 * item.scores.get("vector", 0.0)
                )
            candidates.sort(key=lambda item: item.scores.get("final", 0.0), reverse=True)
            return self._diversify(candidates, top_k)

        # Build only uncached pairs. The same query reranks the initial
        # candidates and then the expanded candidate set; reusing exact model
        # scores here preserves ranking while avoiding duplicate inference.
        pairs = []
        uncached_keys: list[tuple[str, str]] = []
        active_cache = score_cache if score_cache is not None else {}
        for item in candidates:
            cache_key = (query_intent.raw_query, item.chunk_id)
            if cache_key in active_cache:
                continue
            pairs.append([query_intent.raw_query, self._passage(item)])
            uncached_keys.append(cache_key)

        # Predict relevance scores in batches for better performance
        # Note: num_workers is kept at 0 (default) to prevent PyTorch DataLoader crashing on Windows
        if pairs:
            scores = self.encoder.predict(pairs, batch_size=32)
            for cache_key, score in zip(uncached_keys, scores):
                active_cache[cache_key] = float(score)
        
        return self._finish_rerank(query_intent, candidates, active_cache, top_k=top_k)

    def _passage(self, item: RetrievedChunk) -> str:
        meta = item.metadata
        title = meta.get("ten", "")
        dieu_title = meta.get("dieu_title", "")
        return f"{title} - {dieu_title}. {item.text}".strip()

    def _jina_predict(self, query: str, documents: list[str]) -> list[float]:
        """Call Jina's OpenAI-compatible rerank endpoint and restore input order."""
        if not self.jina_api_key:
            raise RuntimeError("JINA_API_KEY is not configured")
        import httpx

        response = httpx.post(
            self.jina_url,
            headers={"Authorization": f"Bearer {self.jina_api_key}"},
            json={"model": self.jina_model, "query": query, "documents": documents},
            timeout=self.jina_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results", payload.get("data", []))
        scores = [0.0] * len(documents)
        for result in results:
            index = int(result.get("index", -1))
            if 0 <= index < len(scores):
                scores[index] = float(result.get("relevance_score", result.get("score", 0.0)))
        return scores

    def _finish_rerank(
        self,
        query_intent: QueryIntent,
        candidates: list[RetrievedChunk],
        active_cache: dict[tuple[str, str], float] | None = None,
        top_k: int = 12,
    ) -> list[RetrievedChunk]:
        active_cache = active_cache or {}
        # Phase 4 Reranking Features
        for item in candidates:
            score = item.scores.get("cross_encoder", active_cache.get((query_intent.raw_query, item.chunk_id), 0.0))
            item.scores["cross_encoder"] = score
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
            if query_intent.loai_yeu_cau in {"scenario_application", "case_law_question"} and meta.get("document_role") == "case_law":
                # Scenario questions are often answered by an applicable
                # án lệ; a generic Bộ luật hit must not displace it merely
                # because the authority bonus is higher.
                meta_bonus += 4.0
                
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

            # 5. Deterministic lexical agreement. This is deliberately small
            # versus the cross-encoder, but breaks ties when the remote/local
            # reranker gives similar scores to several legal articles.
            passage = " ".join(
                str(meta.get(key, "")) for key in ("citation", "ten", "dieu_title", "chuong_title")
            ) + " " + item.text
            phrase_hits = sum(
                1 for phrase in query_intent.key_phrases
                if phrase and contains_normalized(passage, phrase)
            )
            query_tokens = {
                token for token in tokenize_for_bm25(normalize_for_match(query_intent.normalized_query))
                if len(token) >= 4
            }
            passage_tokens = set(tokenize_for_bm25(normalize_for_match(passage)))
            token_overlap = len(query_tokens & passage_tokens) / max(1, len(query_tokens))
            lexical_bonus = min(1.5, phrase_hits * 0.35 + token_overlap * 1.2)
            item.scores["lexical_agreement"] = lexical_bonus
            meta_bonus += lexical_bonus

            # Agreement between independent retrievers is stronger evidence
            # than a single metadata hit. This is especially important for
            # scenario questions where metadata often returns broad articles.
            source_count = len(set(item.sources))
            agreement_bonus = 0.25 * max(0, source_count - 1)
            if "lexical" in item.sources and "vector" in item.sources:
                agreement_bonus += 0.45
            item.scores["retriever_agreement"] = agreement_bonus
            meta_bonus += agreement_bonus

            item.scores["final"] = score + meta_bonus

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
