from generation.ollama_generator import OllamaLegalGenerator
from generation.models import LegalAnswer
from generation.rule_based_generator import RuleBasedLegalGenerator
from retrieval.models import RetrievalResult
from retrieval.pipeline import RetrievalPipeline


class GenerationPipeline:
    def __init__(self, use_llm: bool = True):
        self.retrieval = RetrievalPipeline()
        self.rule_based = RuleBasedLegalGenerator()
        
        # Smart Fallback: Online (Groq) -> Offline (Ollama)
        if use_llm:
            try:
                from generation.groq_generator import GroqLegalGenerator
                from app.config import settings
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
            return answer, retrieval_result

        import time
        t0 = time.time()
        fallback_answer = self.rule_based.generate(query, retrieval_result)
        latency_fallback = round(time.time() - t0, 3)
        
        t1 = time.time()
        answer = self.llm.generate(query, retrieval_result, history=history) if self.llm else None
        latency_llm = round(time.time() - t1, 3)
        
        retrieval_result.retrieval_debug["latency_generation_llm"] = latency_llm
        retrieval_result.retrieval_debug["latency_generation_fallback"] = latency_fallback
        retrieval_result.retrieval_debug["latency_total_pipeline"] = round(time.time() - t0 + retrieval_result.retrieval_debug.get("latency_total_retrieval", 0), 3)
        if answer is None:
            answer = fallback_answer
        else:
            if not answer.citations:
                answer.citations = fallback_answer.citations
            if not answer.disclaimers:
                answer.disclaimers = fallback_answer.disclaimers
                
        answer.retrieval_debug = retrieval_result.retrieval_debug
        answer.confidence = {**retrieval_result.confidence, **answer.confidence}
        return answer, retrieval_result

    async def run_stream(self, query: str, history: list = None):
        import json
        import asyncio
        import time
        from fastapi.encoders import jsonable_encoder
        
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
        retrieval_result.retrieval_debug["latency_total_pipeline"] = round(time.time() - t0 + retrieval_result.retrieval_debug.get("latency_total_retrieval", 0), 3)
        
        if answer is None:
            answer = fallback_answer
        else:
            if not answer.citations:
                answer.citations = fallback_answer.citations
            if not answer.disclaimers:
                answer.disclaimers = fallback_answer.disclaimers
                
        answer.retrieval_debug = retrieval_result.retrieval_debug
        answer.confidence = {**retrieval_result.confidence, **answer.confidence}
        
        yield f"data: {json.dumps({'type': 'answer', 'data': jsonable_encoder(answer.to_dict())})}\n\n"
