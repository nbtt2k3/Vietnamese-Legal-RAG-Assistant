import json

import ollama

from app.config import settings
from app.logger import logger


class LLMJudge:
    def __init__(
        self,
        model_name: str | None = None,
        timeout_seconds: float | None = None,
        max_attempts: int | None = None,
        client=None,
    ):
        self.model_name = model_name or settings.llm_model_name
        self.timeout_seconds = timeout_seconds or settings.llm_judge_timeout_seconds
        self.max_attempts = max(1, max_attempts or settings.llm_judge_max_attempts)
        self.client = client or ollama.Client(timeout=self.timeout_seconds)
        self.last_reasons: dict[str, str] = {}

    def _chat(self, prompt: str) -> dict:
        return self.client.chat(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            format="json",
            options={"temperature": 0.0},
        )

    def _ask_judge(self, prompt: str, metric_name: str) -> dict:
        last_error = ""
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self._chat(prompt)
                payload = json.loads(response["message"]["content"])
                score = self._coerce_score(payload.get("score", 0.0))
                reason = str(payload.get("reason", "")).strip() or "Judge returned no reason"
                self.last_reasons[metric_name] = reason
                return {"score": score, "reason": reason, "available": True}
            except Exception as exc:
                last_error = str(exc)
            logger.warning(
                "LLM Judge failed for %s on attempt %s/%s: %s",
                metric_name,
                attempt,
                self.max_attempts,
                last_error,
            )

        reason = f"LLM judge unavailable: {last_error or 'unknown error'}"
        self.last_reasons[metric_name] = reason
        return {"score": 0.0, "reason": reason, "available": False}

    def _coerce_score(self, value) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0
        return min(1.0, max(0.0, score))

    def is_available(self) -> bool:
        prompt = 'Return JSON only: {"score": 1.0, "reason": "ok"}'
        result = self._ask_judge(prompt, "availability")
        return bool(result.get("available"))

    def evaluate_answer_relevance(self, query: str, answer: str) -> float:
        prompt = f"""
Bạn là giám khảo công bằng. Hãy đánh giá xem câu trả lời sau đây có giải quyết trực tiếp câu hỏi không.
Trả về JSON: {{"score": <float từ 0.0 đến 1.0>, "reason": "<lý do ngắn gọn>"}}

Câu hỏi: {query}
Câu trả lời: {answer}
"""
        result = self._ask_judge(prompt, "answer_relevance")
        return float(result["score"])

    def evaluate_faithfulness(self, answer: str, context: str) -> float:
        prompt = f"""
Bạn là giám khảo công bằng. Hãy đánh giá xem câu trả lời sau đây có hoàn toàn dựa vào văn bản ngữ cảnh được cung cấp không, không tự bịa thêm thông tin.
Trả về JSON: {{"score": <float từ 0.0 đến 1.0>, "reason": "<lý do ngắn gọn>"}}

Ngữ cảnh: {context}
Câu trả lời: {answer}
"""
        result = self._ask_judge(prompt, "faithfulness")
        return float(result["score"])

    def evaluate_context_precision(self, query: str, context: str) -> float:
        prompt = f"""
Bạn là giám khảo công bằng. Hãy đánh giá xem văn bản ngữ cảnh sau đây có chứa thông tin hữu ích và chính xác để trả lời câu hỏi không.
Trả về JSON: {{"score": <float từ 0.0 đến 1.0>, "reason": "<lý do ngắn gọn>"}}

Câu hỏi: {query}
Ngữ cảnh: {context}
"""
        result = self._ask_judge(prompt, "context_precision")
        return float(result["score"])
