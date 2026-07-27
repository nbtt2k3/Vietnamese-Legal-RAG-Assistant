from generation.models import AnswerSection, Claim, LegalAnswer
from generation.utils import chunk_to_citation, dedupe_citations
from retrieval.models import RetrievalResult

class BaseLLMGenerator:
    _GROUNDING_STOPWORDS = {
        "theo", "cua", "của", "va", "và", "la", "là", "co", "có", "khong", "không",
        "duoc", "được", "phai", "phải", "neu", "nếu", "thi", "thì", "cho", "trong",
        "mot", "một", "cac", "các", "ve", "về", "voi", "với", "tu", "từ", "tai", "tại",
        "nay", "này", "do", "đó", "can", "cần", "se", "sẽ", "hoac", "hoặc", "khi",
        "nhung", "những", "noi", "nội", "dung", "quy", "dinh", "định", "phap", "pháp",
        "luat", "luật", "van", "văn", "ban", "bản",
    }

    def _parse_llm_response(
        self, 
        data: dict, 
        query: str, 
        retrieval_result: RetrievalResult, 
        method_name: str
    ) -> LegalAnswer:
        sections = []
        core = getattr(retrieval_result.evidence, "core_authorities", [])
        case_law = getattr(retrieval_result.evidence, "case_law_support", [])
        supporting = getattr(retrieval_result.evidence, "supporting_authorities", [])[:4]
        
        raw_items = core + case_law + supporting
        evidence_by_id = {f"E{i+1}": item for i, item in enumerate(raw_items)}
        valid_e_ids = set(evidence_by_id)
        invalid_e_ids_used = False
        claims_without_evidence = False
        weakly_supported_claims = False
        total_claims = 0
        grounded_claims = 0

        for section_key, title in [
            ("quy_dinh_phap_luat", "Quy định pháp luật"),
            ("ap_dung_so_bo", "Áp dụng sơ bộ"),
        ]:
            raw_claims = data.get(section_key, []) if isinstance(data, dict) else []
            if isinstance(raw_claims, list) and raw_claims:
                claims = []
                content_lines = []
                for idx, c in enumerate(raw_claims):
                    if not isinstance(c, dict):
                        continue
                    statement = c.get("claim", "")
                    reasoning = c.get("reasoning", "")
                    e_ids = c.get("evidence_ids", [])
                    if not isinstance(e_ids, list):
                        e_ids = [str(e_ids)] if e_ids else []
                    e_ids = [str(eid).strip() for eid in e_ids if str(eid).strip()]
                    valid_claim_e_ids = [eid for eid in e_ids if eid in valid_e_ids]
                        
                    claims.append(Claim(statement=statement, reasoning=reasoning, evidence_ids=e_ids))
                    total_claims += 1
                    
                    for eid in e_ids:
                        if eid not in valid_e_ids:
                            invalid_e_ids_used = True
                    if not valid_claim_e_ids:
                        claims_without_evidence = True
                    elif self._claim_is_supported(statement, reasoning, valid_claim_e_ids, evidence_by_id):
                        grounded_claims += 1
                    else:
                        weakly_supported_claims = True
                            
                    content_lines.append(f"**Nhận định {idx+1}:** {statement}\n*Lập luận:* {reasoning}\n*Căn cứ:* {', '.join(e_ids) if e_ids else 'Không có'}")
                if claims:
                    sections.append(
                        AnswerSection(title=title, content="\n\n".join(content_lines), claims=claims)
                    )
                
        for section_key, title in [
            ("tinh_tiet_can_bo_sung", "Tình tiết cần bổ sung"),
            ("rui_ro_phap_ly", "Rủi ro pháp lý"),
            ("buoc_tiep_theo", "Bước tiếp theo"),
        ]:
            notes = data.get(section_key, []) if isinstance(data, dict) else []
            if notes:
                if not isinstance(notes, list):
                    notes = [str(notes)]
                sections.append(
                    AnswerSection(title=title, content="\n".join(f"- {item}" for item in notes if item))
                )

        disclaimers = []
        conflict = data.get("conflict_detected", False)
        uncertainty = str(data.get("uncertainty", "")).strip()
        
        if conflict:
            disclaimers.append("LƯU Ý: Đã phát hiện mâu thuẫn pháp lý trong các căn cứ áp dụng.")
        if invalid_e_ids_used:
            disclaimers.append("CẢNH BÁO: AI đã tạo ra căn cứ không tồn tại trong hồ sơ (Hallucination). Vui lòng đối chiếu kỹ.")
        if claims_without_evidence:
            disclaimers.append("CẢNH BÁO: Một số nhận định pháp lý không có căn cứ hợp lệ trong evidence được truy xuất.")
        if weakly_supported_claims:
            disclaimers.append("CẢNH BÁO: Một số nhận định có trích dẫn nhưng mức khớp nội dung với evidence còn yếu; cần đối chiếu lại nguồn.")
        if uncertainty and uncertainty.lower() not in ("không", "none", "", "null"):
            disclaimers.append(f"Chưa chắc chắn: {uncertainty}")
        if not valid_e_ids:
            disclaimers.append("TỪ CHỐI TRẢ LỜI: Không tìm thấy căn cứ pháp lý phù hợp trong hệ thống.")
            sections = [AnswerSection(title="Từ chối trả lời", content="Câu hỏi của bạn nằm ngoài phạm vi hoặc hệ thống chưa cập nhật văn bản liên quan.")]
        
        citations = []
        seen = set()
        for i, item in enumerate(raw_items):
            cit = chunk_to_citation(item)
            cit.evidence_id = f"E{i+1}"
            
            key = cit.citation.strip().lower()
            if not key or key in seen:
                continue
            citations.append(cit)
            seen.add(key)
            if len(citations) >= 8:
                break
                
        confidence_data = {
            **(getattr(retrieval_result, "confidence", {})),
            "generator_uncertainty": uncertainty,
            "missing_facts": str(data.get("missing_facts", "")),
            "conflict_detected": conflict,
            "invalid_evidence_used": invalid_e_ids_used,
            "claims_without_evidence": claims_without_evidence,
            "weakly_supported_claims": weakly_supported_claims,
            "grounded_claim_count": grounded_claims,
            "total_claim_count": total_claims,
            "grounding_coverage": round(grounded_claims / total_claims, 3) if total_claims else None,
        }
        
        if (
            conflict
            or invalid_e_ids_used
            or claims_without_evidence
            or weakly_supported_claims
            or (uncertainty and uncertainty.lower() not in ("không", "none", "", "null"))
        ):
            confidence_data["level"] = "low"

        return LegalAnswer(
            query=query,
            short_answer=str(data.get("short_answer", "")).strip(),
            sections=sections,
            citations=citations,
            confidence=confidence_data,
            disclaimers=disclaimers,
            retrieval_debug=getattr(retrieval_result, "retrieval_debug", {}),
            answer_method=method_name,
        )

    def _claim_is_supported(self, statement: str, reasoning: str, evidence_ids: list[str], evidence_by_id: dict) -> bool:
        claim_tokens = self._grounding_tokens(f"{statement} {reasoning}")
        if not claim_tokens:
            return True

        evidence_text = " ".join(
            " ".join(
                [
                    item.text or "",
                    str(item.metadata.get("citation", "")),
                    str(item.metadata.get("ten", "")),
                    str(item.metadata.get("dieu_title", "")),
                ]
            )
            for eid in evidence_ids
            for item in [evidence_by_id[eid]]
        )
        evidence_tokens = self._grounding_tokens(evidence_text)
        if not evidence_tokens:
            return False

        overlap = claim_tokens & evidence_tokens
        required_overlap = 1 if len(claim_tokens) <= 3 else 2
        return len(overlap) >= required_overlap

    def _grounding_tokens(self, text: str) -> set[str]:
        import re
        import unicodedata

        normalized = unicodedata.normalize("NFC", text or "").casefold()
        tokens = re.findall(r"[\wÀ-ỹĐđ]+", normalized, flags=re.UNICODE)
        return {
            token
            for token in tokens
            if len(token) >= 3 and token not in self._GROUNDING_STOPWORDS and not token.isdigit()
        }
