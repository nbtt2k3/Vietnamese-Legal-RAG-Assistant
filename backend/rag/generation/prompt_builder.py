import json

from rag.generation.utils import chunk_to_citation
from rag.retrieval.models import RetrievalResult


class LegalPromptBuilder:
    def build(self, query: str, retrieval_result: RetrievalResult) -> str:
        evidence = []
        evidence_items = (
            [("core_authority", item) for item in retrieval_result.evidence.core_authorities]
            + [("case_law_support", item) for item in retrieval_result.evidence.case_law_support]
            + [("supporting_authority", item) for item in retrieval_result.evidence.supporting_authorities[:4]]
        )
        for i, (evidence_group, item) in enumerate(evidence_items):
            citation = chunk_to_citation(item)
            evidence.append(
                {
                    "evidence_id": f"E{i+1}",
                    "evidence_group": evidence_group,
                    "citation": citation.citation,
                    "source_type": citation.source_type,
                    "legal_role": citation.legal_role,
                    "validity_status": citation.validity_status,
                    "validity_basis": citation.validity_basis,
                    "validity_confidence": citation.validity_confidence,
                    "source_verification_status": citation.source_verification_status,
                    "source_of_validity": citation.source_of_validity,
                    "source_url": citation.source_url,
                    "source_file": citation.source_file,
                    "snippet": citation.snippet,
                }
            )

        instructions = {
            "task": "Trả lời câu hỏi pháp lý Việt Nam chỉ dựa trên căn cứ được cung cấp.",
            "requirements": [
                "Không bịa thêm căn cứ ngoài context.",
                "BẮT BUỘC SỬ DỤNG TRÍCH DẪN: Ở mỗi câu khẳng định pháp lý, phải chèn ID của căn cứ theo định dạng [E1], [E2] ngay trong câu.",
                "Mỗi mục trong quy_dinh_phap_luat và ap_dung_so_bo bắt buộc phải có evidence_ids không rỗng, và evidence_ids chỉ được lấy từ danh sách căn cứ được cung cấp.",
                "Nếu không tìm thấy căn cứ trực tiếp hỗ trợ một nhận định, không được đưa nhận định đó vào kết luận; hãy ghi vào missing_facts hoặc uncertainty.",
                "Phần reasoning phải giải thích vì sao đoạn trích và nguồn trích dẫn được chọn hỗ trợ nhận định, không chỉ lặp lại kết luận.",
                "TÍNH TOÁN TOÁN HỌC: Nếu tình huống liên quan đến tiền, lãi suất, bồi thường, BẮT BUỘC phải viết rõ phép tính (vd: 20% x 500 triệu = 100 triệu) và đối chiếu với trần luật định.",
                "Không dùng ngôn ngữ nước đôi (như 'có thể không phải trả') đối với các quy định mang tính cấm đoán tuyệt đối (vd: vượt trần lãi suất thì Tòa án không công nhận).",
                "Nêu rõ nếu kết luận còn phụ thuộc thêm tình tiết.",
                "Ưu tiên Bộ luật Dân sự, sau đó văn bản hướng dẫn, rồi án lệ nếu phù hợp.",
                "THỨ TỰ ƯU TIÊN CĂN CỨ: Dùng evidence_group='core_authority' làm căn cứ quy phạm chính; chỉ dùng case_law_support để minh họa hoặc áp dụng tương tự, không thay thế điều luật.",
                "Không khẳng định chắc chắn khi căn cứ chỉ cho thấy hướng phân tích.",
                "POLICY ABSTENTION: Nếu tình trạng hiệu lực của căn cứ (validity_status) là 'chua_xac_dinh' hoặc trống, TUYỆT ĐỐI không được kết luận văn bản đó 'đang còn hiệu lực' hoặc 'chắc chắn áp dụng được'.",
                "KIỂM TRA NGUỒN: Nếu source_verification_status không phải 'official_verified', phải nêu bằng tiếng Việt dễ hiểu rằng nguồn hiện mới được ghi nhận từ tệp nội bộ và mã kiểm tra toàn vẹn, chưa được xác minh trực tiếp từ nguồn có thẩm quyền."
            ],
            "output_schema": {
                "quy_dinh_phap_luat": [{"claim": "string", "reasoning": "string", "evidence_ids": ["string"]}],
                "ap_dung_so_bo": [{"claim": "string", "reasoning": "string", "evidence_ids": ["string"]}],
                "tinh_tiet_can_bo_sung": ["string"],
                "rui_ro_phap_ly": ["string"],
                "buoc_tiep_theo": ["string"],
                "uncertainty": "string",
                "missing_facts": "string",
                "conflict_detected": "boolean"
            },
        }
        payload = {
            "query": query,
            "query_intent": retrieval_result.query_intent.to_dict(),
            "confidence": retrieval_result.confidence,
            "evidence": evidence,
            "temporal_notes": retrieval_result.evidence.temporal_notes,
            "instructions": instructions,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)
