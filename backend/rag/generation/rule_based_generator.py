from rag.generation.models import AnswerSection, LegalAnswer
from rag.generation.utils import (
    build_human_review_signal,
    build_source_validity_confidence,
    build_source_validity_disclaimers,
    chunk_to_citation,
    clean_whitespace,
    dedupe_citations,
)
from rag.retrieval.domain_policy import is_scenario_domain_compatible
from rag.retrieval.models import RetrievalResult, RetrievedChunk
from rag.retrieval.text_utils import citation_matches, normalize_for_match


class RuleBasedLegalGenerator:
    def __init__(self):
        self.validity_keywords = ["hiệu lực", "thời điểm", "có hiệu lực từ", "công chứng", "chứng thực", "thỏa thuận", "đối kháng"]
        try:
            import os, yaml
            rules_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "retrieval", "rules.yaml")
            with open(rules_path, "r", encoding="utf-8") as f:
                rules_data = yaml.safe_load(f)
                keywords = rules_data.get("domain_config", {}).get("validity_keywords")
                if keywords:
                    self.validity_keywords = keywords
        except Exception:
            pass

    def generate(self, query: str, retrieval_result: RetrievalResult) -> LegalAnswer:
        intent = retrieval_result.query_intent
        ranked = retrieval_result.candidates

        primary = self._select_primary_authorities(retrieval_result)
        primary_doc_ids = {item.doc_id for item in primary}
        supporting = [
            item
            for item in self._select_ranked_non_case(retrieval_result)
            if item.doc_id not in primary_doc_ids
        ][:4]
        case_law = self._select_case_law(retrieval_result)

        if intent.insufficient_facts:
            short_answer = self._build_insufficient_short_answer(primary, case_law)
        else:
            short_answer = self._build_short_answer(intent.loai_yeu_cau, primary, case_law)
        sections = [
            self._build_conclusion_section(intent.loai_yeu_cau, primary, case_law),
            self._build_analysis_section(intent.loai_yeu_cau, primary, supporting, case_law),
            self._build_practical_section(intent.loai_yeu_cau, primary, case_law, intent.insufficient_facts),
        ]
        sections = [section for section in sections if section.content.strip()]

        raw_citations = dedupe_citations(
            [chunk_to_citation(item) for item in primary + supporting + case_law],
            limit=10,
        )
        for i, cit in enumerate(raw_citations):
            cit.evidence_id = f"E{i+1}"
        citations = raw_citations
        evidence_items = primary + supporting + case_law
        confidence = self._build_confidence_note(retrieval_result, evidence_items)
        if intent.insufficient_facts:
            confidence["level"] = "low"
            confidence["missing_facts"] = ", ".join(intent.missing_fact_hints)
            confidence["insufficient_facts"] = True
        review_signal = build_human_review_signal(intent.loai_yeu_cau, confidence, evidence_items)
        confidence.update(review_signal)
        disclaimers = self._build_disclaimers(intent.loai_yeu_cau, ranked, case_law, evidence_items)

        return LegalAnswer(
            query=query,
            short_answer=short_answer,
            sections=sections,
            citations=citations,
            confidence=confidence,
            disclaimers=disclaimers,
            retrieval_debug=retrieval_result.retrieval_debug,
            answer_method="rule_based",
        )

    def _select_primary_authorities(self, retrieval_result: RetrievalResult) -> list[RetrievedChunk]:
        intent = retrieval_result.query_intent
        ranked = self._select_ranked_non_case(retrieval_result)
        scored = sorted(
            ranked,
            key=lambda item: self._generation_priority_score(
                item,
                intent.loai_yeu_cau,
                intent.citation_targets,
                intent.key_phrases,
                intent.scenario_terms,
                intent.normalized_query,
            ),
            reverse=True,
        )

        # Explicit authorities are stronger than generic semantic relevance.
        # Select one or more hits for each requested document/article before
        # applying the normal domain preference. This is important for
        # multi-document questions and for cautious answers whose facts are
        # incomplete but whose governing article is still known.
        explicit = self._select_explicit_target_authorities(retrieval_result)
        if explicit:
            return self._order_same_article_units(explicit[:4])

        if intent.loai_yeu_cau == "citation_lookup":
            # A citation lookup often needs multiple clauses of the same article.
            return self._order_same_article_units(scored[:4])

        if intent.loai_yeu_cau == "validity_question" and intent.citation_targets:
            focused = [
                item
                for item in scored
                if self._matches_generation_target(item, intent.citation_targets)
            ]
            if focused:
                return self._order_same_article_units(focused[:4])

        selected: list[RetrievedChunk] = []
        seen_docs: set[str] = set()
        for item in scored:
            if item.doc_id in seen_docs:
                continue
            selected.append(item)
            seen_docs.add(item.doc_id)
            if len(selected) >= 4:
                break
        return selected

    def _select_explicit_target_authorities(
        self,
        retrieval_result: RetrievalResult,
    ) -> list[RetrievedChunk]:
        intent = retrieval_result.query_intent
        targets = list(dict.fromkeys(intent.citation_targets))
        if not targets:
            return []

        # Do not let the scenario domain filter discard an explicitly named
        # statutory source. The exact target has already been constrained by
        # retrieval; generation should preserve that evidence.
        candidates = [
            item
            for item in retrieval_result.candidates
            if item.metadata.get("document_role") != "case_law"
        ]
        if not candidates:
            return []
        scored = sorted(
            candidates,
            key=lambda item: self._generation_priority_score(
                item,
                intent.loai_yeu_cau,
                intent.citation_targets,
                intent.key_phrases,
                intent.scenario_terms,
                intent.normalized_query,
            ),
            reverse=True,
        )

        selected: list[RetrievedChunk] = []
        selected_ids: set[str] = set()
        for target in targets:
            match = next(
                (
                    item for item in scored
                    if item.chunk_id not in selected_ids
                    and self._matches_generation_target(item, [target])
                ),
                None,
            )
            if match:
                selected.append(match)
                selected_ids.add(match.chunk_id)

        # Add adjacent parent/child units from an explicitly selected article
        # while keeping a hard bound on answer evidence size.
        for item in scored:
            if item.chunk_id in selected_ids:
                continue
            if any(self._matches_generation_target(item, [target]) for target in targets):
                selected.append(item)
                selected_ids.add(item.chunk_id)
            if len(selected) >= 4:
                break
        return selected

    def _order_same_article_units(self, items: list[RetrievedChunk]) -> list[RetrievedChunk]:
        ordered: list[RetrievedChunk] = []
        index = 0
        while index < len(items):
            item = items[index]
            doc_id = item.doc_id
            article = str(item.metadata.get("dieu_number", "")).strip()
            group = [item]
            index += 1
            while index < len(items):
                next_item = items[index]
                if next_item.doc_id != doc_id or str(next_item.metadata.get("dieu_number", "")).strip() != article:
                    break
                group.append(next_item)
                index += 1
            if article and len(group) > 1:
                group.sort(key=self._legal_unit_order_key)
            ordered.extend(group)
        return ordered

    def _legal_unit_order_key(self, item: RetrievedChunk) -> tuple[int, str]:
        value = str(item.metadata.get("khoan_number", "")).strip()
        if value.isdigit():
            return (int(value), "")
        return (10_000, value)

    def _matches_generation_target(self, item: RetrievedChunk, citation_targets: list[str]) -> bool:
        metadata = item.metadata
        haystack = normalize_for_match(
            " ".join(
                [
                    item.chunk_id,
                    item.doc_id,
                    str(metadata.get("citation", "")),
                    str(metadata.get("so_hieu", "")),
                    str(metadata.get("ten", "")),
                    str(metadata.get("dieu_title", "")),
                ]
            )
        )
        for target in citation_targets:
            if citation_matches(str(metadata.get("citation", "")), target):
                return True
            target_norm = normalize_for_match(target)
            if target_norm and target_norm in haystack:
                return True
            if target_norm.startswith("nghi dinh "):
                number_part = target_norm.replace("nghi dinh ", "", 1).strip()
                if number_part and number_part in haystack:
                    return True
        return False

    def _select_ranked_non_case(self, retrieval_result: RetrievalResult) -> list[RetrievedChunk]:
        intent = retrieval_result.query_intent
        return [
            item
            for item in retrieval_result.candidates
            if item.metadata.get("document_role") != "case_law"
            and is_scenario_domain_compatible(item, intent)
        ]

    def _select_case_law(self, retrieval_result: RetrievalResult) -> list[RetrievedChunk]:
        intent = retrieval_result.query_intent
        if intent.loai_yeu_cau not in {"scenario_application", "case_law_question"}:
            return []
        selected: list[RetrievedChunk] = []
        seen_docs: set[str] = set()
        for item in retrieval_result.candidates:
            if item.metadata.get("document_role") != "case_law":
                continue
            if not is_scenario_domain_compatible(item, intent):
                continue
            if item.doc_id in seen_docs:
                continue
            selected.append(item)
            seen_docs.add(item.doc_id)
            if len(selected) >= 2:
                break
        return selected

    def _generation_priority_score(
        self,
        item: RetrievedChunk,
        request_type: str,
        citation_targets: list[str],
        key_phrases: list[str],
        scenario_terms: list[str],
        normalized_query: str = "",
    ) -> float:
        score = float(item.scores.get("final", 0.0))
        metadata = item.metadata
        source = str(metadata.get("loai_van_ban", ""))
        legal_role = str(metadata.get("legal_role", ""))
        haystack = " ".join(
            [
                str(metadata.get("citation", "")).lower(),
                str(metadata.get("ten", "")).lower(),
                str(metadata.get("dieu_title", "")).lower(),
                item.text.lower(),
            ]
        )
        normalized_haystack = normalize_for_match(haystack)

        for target in citation_targets:
            target_lower = normalize_for_match(target)
            if citation_matches(str(metadata.get("citation", "")), target):
                score += 12.0
            if "nghi dinh" in target_lower and target_lower.replace("nghi dinh ", "") in normalized_haystack:
                score += 12.0

        if request_type == "citation_lookup":
            if source == "bo_luat":
                score += 8.0
            if "điều" in str(metadata.get("citation", "")).lower():
                score += 2.0
        elif request_type == "validity_question":
            if source == "bo_luat":
                score += 5.0
            if source == "nghi_dinh":
                score += 4.0
            if "thời điểm" in normalized_query.lower() or "ngày hiệu lực" in " ".join(key_phrases).lower():
                if "hiệu lực thi hành" in haystack:
                    score += 10.0
            for kw in self.validity_keywords:
                if kw in haystack:
                    score += 2.0
        elif request_type == "scenario_application":
            if source == "bo_luat":
                score += 6.0
            if source == "nghi_dinh":
                score += 3.0
            if legal_role in {"legal_effect", "condition_exception", "rights_obligations"}:
                score += 2.0
        else:
            if source == "bo_luat":
                score += 4.0

        for phrase in key_phrases:
            if phrase in haystack:
                score += 1.5
        for term in scenario_terms:
            if term in haystack:
                score += 0.8
        return score

    def _build_short_answer(self, request_type: str, primary: list[RetrievedChunk], case_law: list[RetrievedChunk]) -> str:
        if request_type == "validity_question":
            return self._build_validity_short_answer(primary)
        if request_type == "scenario_application":
            return self._build_scenario_short_answer(primary, case_law)
        if request_type == "citation_lookup":
            return self._build_citation_short_answer(primary)
        return self._build_general_short_answer(primary)

    def _build_validity_short_answer(self, primary: list[RetrievedChunk]) -> str:
        citations = [item.metadata.get("citation", item.chunk_id) for item in primary[:2]]
        if citations:
            return (
                "Căn cứ hiện có cho thấy vấn đề hiệu lực cần được xác định chủ yếu theo "
                + "; ".join(citations)
                + "."
            )
        return "Cần dựa vào điều khoản về hiệu lực và thời điểm phát sinh hiệu lực của giao dịch để trả lời chính xác."

    def _build_scenario_short_answer(self, primary: list[RetrievedChunk], case_law: list[RetrievedChunk]) -> str:
        if primary:
            citations = [str(item.metadata.get("citation", item.chunk_id)) for item in primary[:2]]
            if case_law:
                citations.extend(str(item.metadata.get("citation", item.chunk_id)) for item in case_law[:1])
            return (
                "Với dữ kiện hiện tại, chưa nên kết luận tuyệt đối; cần đối chiếu tình tiết thực tế với "
                + "; ".join(citations)
                + "."
            )
        return "Tình huống này cần đối chiếu thêm hồ sơ, chứng cứ và các căn cứ pháp luật trực tiếp liên quan trước khi kết luận."

    def _build_insufficient_short_answer_legacy(self, primary: list[RetrievedChunk]) -> str:
        citation = str(primary[0].metadata.get("citation", primary[0].chunk_id)) if primary else "Điều 117 Bộ luật Dân sự"
        return (
            "Chưa đủ tình tiết để kết luận hợp đồng vô hiệu. Cần đối chiếu điều kiện về chủ thể, "
            "sự tự nguyện, mục đích và nội dung của giao dịch theo "
            + citation
            + "."
        )

    def _build_insufficient_short_answer(
        self,
        primary: list[RetrievedChunk],
        case_law: list[RetrievedChunk] | None = None,
    ) -> str:
        evidence = [*primary[:2], *(case_law or [])[:1]]
        citations = [
            str(item.metadata.get("citation", item.chunk_id))
            for item in evidence
        ]
        citation_text = "; ".join(dict.fromkeys(citations))
        if not citation_text:
            citation_text = "Điều 117 Bộ luật Dân sự"
        return (
            "Chưa đủ tình tiết để kết luận chính xác. Cần đối chiếu chủ thể, thời điểm, "
            "giấy tờ, hành vi và nội dung giao dịch theo "
            + citation_text
            + "."
        )

    def _build_citation_short_answer(self, primary: list[RetrievedChunk]) -> str:
        if primary:
            citations = ", ".join(str(item.metadata.get("citation", item.chunk_id)) for item in primary[:3])
            return f"Các căn cứ pháp lý trọng tâm hiện được truy xuất là: {citations}."
        return "Chưa truy xuất được đủ căn cứ trọng tâm để trả lời chắc chắn."

    def _build_general_short_answer(self, primary: list[RetrievedChunk]) -> str:
        if primary:
            return f"Căn cứ gần nhất với câu hỏi hiện tại là {primary[0].metadata.get('citation', primary[0].chunk_id)}."
        return "Chưa có đủ căn cứ được truy xuất để hình thành câu trả lời đáng tin cậy."

    def _build_conclusion_section(
        self,
        request_type: str,
        primary: list[RetrievedChunk],
        case_law: list[RetrievedChunk],
    ) -> AnswerSection:
        lines = []
        citations = []
        for item in primary[:2]:
            citation = chunk_to_citation(item)
            citations.append(citation)
            lines.append(f"- {citation.citation}: {clean_whitespace(item.text)}")
        if request_type == "scenario_application":
            for item in case_law[:1]:
                citation = chunk_to_citation(item)
                citations.append(citation)
                lines.append(f"- Thực tiễn xét xử tham chiếu: {citation.citation}: {clean_whitespace(item.text)}")
        return AnswerSection(
            title="Kết luận sơ bộ",
            content="\n".join(lines),
            citations=dedupe_citations(citations, limit=4),
        )

    def _build_analysis_section(
        self,
        request_type: str,
        primary: list[RetrievedChunk],
        supporting: list[RetrievedChunk],
        case_law: list[RetrievedChunk],
    ) -> AnswerSection:
        lines = []
        citations = []
        for index, item in enumerate(primary[:3], start=1):
            citation = chunk_to_citation(item)
            citations.append(citation)
            lines.append(f"{index}. {citation.citation}: {clean_whitespace(item.text)}")
        if request_type == "scenario_application" and case_law:
            for item in case_law[:2]:
                citation = chunk_to_citation(item)
                citations.append(citation)
                lines.append(f"- Án lệ/thực tiễn: {citation.citation}: {clean_whitespace(item.text)}")
        elif supporting:
            for item in supporting[:2]:
                citation = chunk_to_citation(item)
                citations.append(citation)
                lines.append(f"- Bổ trợ: {citation.citation}: {clean_whitespace(item.text)}")
        return AnswerSection(
            title="Phân tích pháp lý",
            content="\n".join(lines),
            citations=dedupe_citations(citations, limit=6),
        )

    def _build_practical_section(
        self,
        request_type: str,
        primary: list[RetrievedChunk],
        case_law: list[RetrievedChunk],
        insufficient_facts: bool = False,
    ) -> AnswerSection:
        notes = []
        citations = []
        if request_type == "scenario_application":
            notes.append("- Cần kiểm tra thêm hồ sơ, chứng cứ, thời điểm phát sinh sự kiện và vai trò của từng chủ thể trước khi áp dụng căn cứ pháp luật.")
            notes.append("- Nếu tình huống có nhiều quan hệ pháp luật chồng lấn, cần tách từng vấn đề để tránh dùng nhầm căn cứ giữa các lĩnh vực.")
            if insufficient_facts:
                notes.append("- Với dữ kiện hiện có, chưa thể kết luận hợp đồng vô hiệu; cần làm rõ chủ thể, sự tự nguyện, mục đích và nội dung giao dịch.")
        elif request_type == "validity_question":
            notes.append("- Nên tách bạch giữa hiệu lực của hợp đồng/giao dịch và hiệu lực đối kháng với người thứ ba vì đây là hai lớp pháp lý khác nhau.")
            notes.append("- Nếu văn bản có yêu cầu công chứng, chứng thực hoặc đăng ký, cần kiểm tra thêm mốc thời gian thực tế của từng thủ tục.")
        elif request_type == "citation_lookup":
            notes.append("- Nên dùng các căn cứ trên làm bộ nguồn gốc trước, sau đó mới mở rộng sang nghị định, nghị quyết hoặc án lệ nếu cần áp dụng thực tế.")
        else:
            notes.append("- Cần đối chiếu thêm tình tiết thực tế để tránh áp dụng sai điều luật.")

        citation_items = list(primary[:1])
        if request_type == "scenario_application":
            citation_items.extend(case_law[:1])
        for item in citation_items:
            citations.append(chunk_to_citation(item))
        return AnswerSection(
            title="Lưu ý thực tiễn",
            content="\n".join(notes),
            citations=dedupe_citations(citations, limit=2),
        )

    def _build_confidence_note(self, retrieval_result: RetrievalResult, evidence_items: list[RetrievedChunk]) -> dict:
        confidence = dict(retrieval_result.confidence)
        confidence.update(build_source_validity_confidence(evidence_items))
        level = confidence.get("level", "low")
        if level == "high":
            confidence["generator_note"] = "Câu trả lời có nhiều căn cứ hỗ trợ hoặc khớp trực tiếp với nguồn truy xuất."
        elif level == "medium":
            confidence["generator_note"] = "Câu trả lời có căn cứ liên quan nhưng vẫn cần kiểm tra thêm tình tiết hoặc văn bản bổ trợ."
        else:
            confidence["generator_note"] = "Căn cứ truy xuất còn mỏng, không nên dùng như kết luận cuối cùng."
        return confidence

    def _build_disclaimers(
        self,
        request_type: str,
        ranked: list[RetrievedChunk],
        case_law: list[RetrievedChunk],
        evidence_items: list[RetrievedChunk],
    ) -> list[str]:
        notes = [
            "Câu trả lời này là phân tích hỗ trợ từ hệ thống Vietnamese Legal RAG Assistant, không thay thế ý kiến tư vấn pháp lý chính thức.",
        ]
        notes.extend(build_source_validity_disclaimers(evidence_items))
        if request_type == "scenario_application":
            notes.append("Với câu hỏi tình huống, kết luận cuối cùng còn phụ thuộc hồ sơ, chứng cứ, thời điểm phát sinh giao dịch và cách Tòa án đánh giá sự kiện.")
        if not ranked:
            notes.append("Hệ thống chưa truy xuất được đủ căn cứ để đưa ra đánh giá đáng tin cậy.")
        if case_law and request_type in {"scenario_application", "case_law_question"}:
            notes.append("Án lệ được dùng như nguồn tham khảo định hướng áp dụng pháp luật, cần đối chiếu kỹ với tình tiết vụ việc thực tế.")
        return notes
