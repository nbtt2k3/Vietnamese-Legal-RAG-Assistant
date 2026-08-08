from rag.retrieval.domain_policy import is_scenario_domain_compatible
from rag.retrieval.models import EvidenceBundle, QueryIntent, RetrievedChunk


class EvidenceBuilder:
    def build(self, query_intent: QueryIntent, ranked: list[RetrievedChunk]) -> EvidenceBundle:
        bundle = EvidenceBundle()
        case_law_items = [item for item in ranked if item.metadata.get("document_role") == "case_law"]
        non_case_items = [item for item in ranked if item.metadata.get("document_role") != "case_law"]

        if self._wants_case_law(query_intent):
            for item in case_law_items:
                if len(bundle.case_law_support) >= 2:
                    break
                if item.doc_id not in {entry.doc_id for entry in bundle.case_law_support}:
                    bundle.case_law_support.append(item)

        seen_docs: set[str] = set()
        scored_non_case = sorted(
            non_case_items,
            key=lambda item: self._authority_score(item, query_intent),
            reverse=True,
        )

        for item in scored_non_case:
            if item.doc_id in seen_docs:
                continue

            is_valid_for_core = self._is_core_eligible(item, query_intent)

            if is_valid_for_core and len(bundle.core_authorities) < 5:
                bundle.core_authorities.append(item)
                seen_docs.add(item.doc_id)
            elif self._is_supporting_eligible(item, query_intent) and len(bundle.supporting_authorities) < 6:
                # BUG-07 FIX: Thêm doc_id vào seen_docs cả khi đưa vào supporting_authorities
                # để tránh cùng tài liệu xuất hiện ở cả core lẫn supporting.
                bundle.supporting_authorities.append(item)
                seen_docs.add(item.doc_id)

            if len(bundle.core_authorities) >= 5 and len(bundle.supporting_authorities) >= 6:
                break

        for item in scored_non_case:
            if len(bundle.supporting_authorities) >= 6:
                break
            # BUG-07 FIX: Kiểm tra doc_id thay vì object identity (object identity
            # không bắt được hai RetrievedChunk khác nhau cùng doc_id).
            if item.doc_id in seen_docs:
                continue
            if not self._is_supporting_eligible(item, query_intent):
                continue
            bundle.supporting_authorities.append(item)
            seen_docs.add(item.doc_id)

        for item in ranked:
            for note in item.metadata.get("transition_notes", []) or []:
                if note and note not in bundle.temporal_notes:
                    bundle.temporal_notes.append(note)
            if len(bundle.temporal_notes) >= 3:
                break

        if self._wants_case_law(query_intent) and not bundle.case_law_support:
            for item in ranked:
                if item.metadata.get("document_role") == "case_law" and item.doc_id not in {entry.doc_id for entry in bundle.case_law_support}:
                    bundle.case_law_support.append(item)
                if len(bundle.case_law_support) >= 2:
                    break

        return bundle

    def _authority_score(self, item: RetrievedChunk, query_intent: QueryIntent) -> float:
        score = item.scores.get("final", 0.0)
        metadata = item.metadata
        source = metadata.get("loai_van_ban")
        legal_role = metadata.get("legal_role")
        haystack = " ".join(
            [
                str(metadata.get("citation", "")).lower(),
                str(metadata.get("ten", "")).lower(),
                str(metadata.get("dieu_title", "")).lower(),
                item.text.lower(),
            ]
        )

        if source in query_intent.source_priority:
            score += max(0.0, 4.0 - query_intent.source_priority.index(source))
        if legal_role in {"legal_effect", "condition_exception", "rule"}:
            score += 1.5
        for phrase in query_intent.key_phrases:
            if phrase in haystack:
                score += 2.0
        for term in query_intent.scenario_terms:
            if term in haystack:
                score += 1.0
        for target in query_intent.citation_targets:
            if target.lower() in haystack:
                score += 2.5
        if query_intent.loai_yeu_cau == "scenario_application" and source == "bo_luat":
            score += 2.0
        if query_intent.loai_yeu_cau == "citation_lookup" and source == "bo_luat":
            score += 2.5
        if query_intent.loai_yeu_cau == "validity_question" and "hiệu lực" in haystack:
            score += 2.5
        return score

    def _wants_case_law(self, query_intent: QueryIntent) -> bool:
        return (
            not query_intent.insufficient_facts
            and query_intent.loai_yeu_cau in {"scenario_application", "case_law_question"}
        )

    def _is_core_eligible(self, item: RetrievedChunk, query_intent: QueryIntent) -> bool:
        if self._is_appendix_noise(item, query_intent):
            return False
        if not is_scenario_domain_compatible(item, query_intent):
            return False

        if query_intent.loai_yeu_cau == "loan_interest_rate":
            source_type = str(item.metadata.get("loai_van_ban", ""))
            return source_type in ("bo_luat", "nghi_quyet")

        return True

    def _is_supporting_eligible(self, item: RetrievedChunk, query_intent: QueryIntent) -> bool:
        return (
            not self._is_appendix_noise(item, query_intent)
            and is_scenario_domain_compatible(item, query_intent)
        )

    def _is_appendix_noise(self, item: RetrievedChunk, query_intent: QueryIntent) -> bool:
        metadata = item.metadata
        is_appendix = (
            metadata.get("legal_unit_type") == "phu_luc"
            or metadata.get("legal_role") == "appendix_form"
        )
        if not is_appendix:
            return False

        haystack = " ".join(
            [
                query_intent.normalized_query.casefold(),
                " ".join(query_intent.key_phrases).casefold(),
                " ".join(query_intent.scenario_terms).casefold(),
            ]
        )
        return not any(term in haystack for term in ("phụ lục", "mẫu", "biểu mẫu"))
