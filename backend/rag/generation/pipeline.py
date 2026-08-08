from rag.generation.ollama_generator import OllamaLegalGenerator
from rag.generation.models import AnswerSection, LegalAnswer
from rag.generation.rule_based_generator import RuleBasedLegalGenerator
from rag.retrieval.models import RetrievalResult
from rag.retrieval.pipeline import RetrievalPipeline


class GenerationPipeline:
    def __init__(self, use_llm: bool = True):
        self.retrieval = RetrievalPipeline()
        self.rule_based = RuleBasedLegalGenerator()
        
        # Smart Fallback: Online (Groq) -> Offline (Ollama)
        if use_llm:
            try:
                from rag.generation.groq_generator import GroqLegalGenerator
                from app.core.config import settings
                groq_gen = GroqLegalGenerator(api_key=settings.groq_api_key)
                if groq_gen.is_available():
                    self.llm = groq_gen
                else:
                    self.llm = OllamaLegalGenerator()
            except ImportError:
                print("[WARNING] Thư viện 'groq' chưa được cài đặt. Fallback sang Ollama (Offline).")
                self.llm = OllamaLegalGenerator()
        else:
            self.llm = None

    def run(self, query: str, history: list = None) -> tuple[LegalAnswer, RetrievalResult]:
        import time
        t_pipeline_start = time.time()  # BUG-06 FIX: Đo từ đầu hàm để bao gồm cả retrieval
        retrieval_result = self.retrieval.run(query, history=history)
        
        # GUARDRAILS
        if retrieval_result.query_intent.loai_yeu_cau == "out_of_scope":
            answer = LegalAnswer(
                query=query,
                short_answer="Xin lỗi, câu hỏi của bạn có chứa nội dung không phù hợp, nằm ngoài phạm vi pháp luật Việt Nam, hoặc vi phạm chính sách an toàn. Tôi chỉ có thể trả lời các vấn đề pháp lý hợp lệ.",
                sections=[],
                citations=[],
                confidence={"level": "high", "note": "Guardrail triggered"},
                disclaimers=[],
                retrieval_debug=retrieval_result.retrieval_debug,
                answer_method="guardrail"
            )
            answer = self._build_guardrail_answer(query, retrieval_result)
            return answer, retrieval_result

        t0 = time.time()
        fallback_answer = self.rule_based.generate(query, retrieval_result)
        latency_fallback = round(time.time() - t0, 3)

        t1 = time.time()
        answer = self.llm.generate(query, retrieval_result, history=history) if self.llm else None
        latency_llm = round(time.time() - t1, 3)

        retrieval_result.retrieval_debug["latency_generation_llm"] = latency_llm
        retrieval_result.retrieval_debug["latency_generation_fallback"] = latency_fallback
        # BUG-06 FIX: Tính total pipeline từ t_pipeline_start (trước cả retrieval)
        # để có con số end-to-end chính xác.
        retrieval_result.retrieval_debug["latency_total_pipeline"] = round(time.time() - t_pipeline_start, 3)
        if answer is None:
            answer = fallback_answer
        else:
            if not answer.citations:
                answer.citations = fallback_answer.citations
            if not answer.disclaimers:
                answer.disclaimers = fallback_answer.disclaimers
                
        answer.retrieval_debug = retrieval_result.retrieval_debug
        answer.confidence = {**retrieval_result.confidence, **answer.confidence}
        self._apply_grounding_gate(answer)
        return answer, retrieval_result

    async def run_stream(self, query: str, history: list = None):
        import json
        import asyncio
        import time
        from fastapi.encoders import jsonable_encoder

        t_pipeline_start = time.time()  # BUG-06 FIX: Đo từ đầu hàm
        yield f"data: {json.dumps({'type': 'status', 'content': 'Đang phân tích câu hỏi và truy xuất tài liệu pháp lý...'})}\n\n"
        
        retrieval_result = await asyncio.to_thread(self.retrieval.run, query=query, history=history)
        
        # GUARDRAILS
        if retrieval_result.query_intent.loai_yeu_cau == "out_of_scope":
            answer = LegalAnswer(
                query=query,
                short_answer="Xin lỗi, câu hỏi của bạn có chứa nội dung không phù hợp, nằm ngoài phạm vi pháp luật Việt Nam, hoặc vi phạm chính sách an toàn. Tôi chỉ có thể trả lời các vấn đề pháp lý hợp lệ.",
                sections=[],
                citations=[],
                confidence={"level": "high", "note": "Guardrail triggered"},
                disclaimers=[],
                retrieval_debug=retrieval_result.retrieval_debug,
                answer_method="guardrail"
            )
            answer = self._build_guardrail_answer(query, retrieval_result)
            yield f"data: {json.dumps({'type': 'retrieval', 'data': jsonable_encoder(retrieval_result.to_dict())})}\n\n"
            yield f"data: {json.dumps({'type': 'answer', 'data': jsonable_encoder(answer.to_dict())})}\n\n"
            return
            
        yield f"data: {json.dumps({'type': 'retrieval', 'data': jsonable_encoder(retrieval_result.to_dict())})}\n\n"
        yield f"data: {json.dumps({'type': 'status', 'content': 'Đang tổng hợp câu trả lời từ AI...'})}\n\n"
        
        t0 = time.time()
        fallback_answer = await asyncio.to_thread(self.rule_based.generate, query, retrieval_result)
        latency_fallback = round(time.time() - t0, 3)
        
        t1 = time.time()
        answer = await asyncio.to_thread(self.llm.generate, query, retrieval_result, history) if self.llm else None
        latency_llm = round(time.time() - t1, 3)
        
        retrieval_result.retrieval_debug["latency_generation_llm"] = latency_llm
        retrieval_result.retrieval_debug["latency_generation_fallback"] = latency_fallback
        # BUG-06 FIX: Tính total pipeline từ t_pipeline_start (trước cả retrieval)
        retrieval_result.retrieval_debug["latency_total_pipeline"] = round(time.time() - t_pipeline_start, 3)
        
        if answer is None:
            answer = fallback_answer
        else:
            if not answer.citations:
                answer.citations = fallback_answer.citations
            if not answer.disclaimers:
                answer.disclaimers = fallback_answer.disclaimers
                
        answer.retrieval_debug = retrieval_result.retrieval_debug
        answer.confidence = {**retrieval_result.confidence, **answer.confidence}
        self._apply_grounding_gate(answer)
        
        yield f"data: {json.dumps({'type': 'answer', 'data': jsonable_encoder(answer.to_dict())})}\n\n"

    @staticmethod
    def _build_guardrail_answer(query: str, retrieval_result: RetrievalResult) -> LegalAnswer:
        """Build a clear abstention that is useful to users and evaluators."""
        return LegalAnswer(
            query=query,
            short_answer=(
                "Xin lỗi, câu hỏi này không phù hợp hoặc nằm ngoài phạm vi dữ liệu pháp luật hiện có. "
                "Hệ thống chưa cập nhật đủ căn cứ để đưa ra kết luận đáng tin cậy và chỉ hỗ trợ các vấn đề pháp lý "
                "có nguồn phù hợp trong kho dữ liệu."
            ),
            sections=[
                AnswerSection(
                    title="Phạm vi hỗ trợ",
                    content=(
                        "Vui lòng đặt câu hỏi thuộc nhóm văn bản pháp luật mà hệ thống đang hỗ trợ. "
                        "Không nên dùng câu trả lời này thay cho tư vấn pháp lý chính thức."
                    ),
                )
            ],
            citations=[],
            confidence={"level": "high", "note": "Guardrail triggered"},
            disclaimers=[
                "Câu hỏi nằm ngoài phạm vi hỗ trợ hoặc chưa đủ căn cứ pháp luật trong hệ thống.",
                "Hệ thống không đưa ra kết luận pháp lý cho nội dung này.",
            ],
            retrieval_debug=retrieval_result.retrieval_debug,
            answer_method="guardrail",
        )

    @staticmethod
    def _apply_grounding_gate(answer: LegalAnswer) -> None:
        """Prevent unsupported legal conclusions from reaching the user.

        A generator may return fluent text even when it omitted evidence IDs,
        referenced invalid evidence, or had no retrieved citations. In those
        cases the UI must show an abstention instead of presenting the text as
        a legal conclusion.
        """
        confidence = answer.confidence or {}
        gate_reasons = []
        if confidence.get("claims_without_evidence"):
            gate_reasons.append("claims_without_evidence")
        if confidence.get("invalid_evidence_used"):
            gate_reasons.append("invalid_evidence_used")
        if confidence.get("short_answer_not_grounded"):
            gate_reasons.append("short_answer_not_grounded")
        if not answer.citations:
            gate_reasons.append("no_legal_citation")

        if not gate_reasons:
            return

        answer.short_answer = (
            "Chưa đủ căn cứ pháp lý được truy xuất để đưa ra kết luận đáng tin cậy. "
            "Vui lòng bổ sung thông tin hoặc kiểm tra trực tiếp văn bản pháp luật liên quan."
        )
        answer.sections = [
            AnswerSection(
                title="Chưa đủ căn cứ pháp lý",
                content=(
                    "Hệ thống không tìm thấy căn cứ hợp lệ gắn với nhận định này. "
                    "Không nên sử dụng câu trả lời như kết luận pháp lý cuối cùng."
                ),
            )
        ]
        answer.confidence = {
            **confidence,
            "level": "low",
            "grounding_gate_triggered": True,
            "grounding_gate_reasons": gate_reasons,
            "human_review_required": True,
        }
        disclaimer = (
            "Câu trả lời đã được chặn vì chưa có căn cứ pháp lý hợp lệ gắn với nội dung kết luận."
        )
        if disclaimer not in answer.disclaimers:
            answer.disclaimers.append(disclaimer)
