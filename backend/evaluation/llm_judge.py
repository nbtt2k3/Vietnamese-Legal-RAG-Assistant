import json
import re

import ollama

from app.core.config import settings
from app.core.logging import logger


class LLMJudge:
    SCORE_SCHEMA = {
        "type": "object",
        "properties": {
            "score": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string"},
        },
        "required": ["score", "reason"],
        "additionalProperties": False,
    }
    TRIAD_SCHEMA = {
        "type": "object",
        "properties": {
            "answer_relevance": {"type": "number", "minimum": 0, "maximum": 1},
            "faithfulness": {"type": "number", "minimum": 0, "maximum": 1},
            "context_precision": {"type": "number", "minimum": 0, "maximum": 1},
            "reasons": {
                "type": "object",
                "properties": {
                    "answer_relevance": {"type": "string"},
                    "faithfulness": {"type": "string"},
                    "context_precision": {"type": "string"},
                },
                "required": ["answer_relevance", "faithfulness", "context_precision"],
                "additionalProperties": False,
            },
        },
        "required": ["answer_relevance", "faithfulness", "context_precision", "reasons"],
        "additionalProperties": False,
    }

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

    def _chat(self, prompt: str, schema: dict | str = "json") -> dict:
        return self.client.chat(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            format=schema,
            options={"temperature": 0.0, "num_predict": 256},
        )

    def _parse_json_response(self, content: str) -> dict:
        """Parse common Ollama JSON deviations without accepting free-form text."""
        text = str(content or "").strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            # Models occasionally emit a trailing comma before a closing
            # object/array even when format="json" is requested.
            repaired = re.sub(r",\s*([}\]])", r"\1", text)
            payload = json.loads(repaired)
        if not isinstance(payload, dict):
            raise ValueError("LLM judge response must be a JSON object")
        return payload

    def _retry_prompt(self, prompt: str, attempt: int) -> str:
        if attempt <= 1:
            return prompt
        return (
            f"{prompt}\n\nIMPORTANT RETRY: Your previous response was not valid JSON. "
            "Return exactly one compact JSON object, with double quotes, no markdown, "
            "no commentary, and no trailing commas."
        )

    def _ask_judge(self, prompt: str, metric_name: str) -> dict:
        last_error = ""
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self._chat(self._retry_prompt(prompt, attempt), self.SCORE_SCHEMA)
                payload = self._parse_json_response(response["message"]["content"])
                score = self._coerce_score(payload.get("score", 0.0))
                reason = str(payload.get("reason", "")).strip() or "Judge returned no reason"
                self.last_reasons[metric_name] = reason
                return {"score": score, "reason": reason, "available": True}
            except Exception as exc:
                last_error = str(exc)
            if attempt == self.max_attempts:
                logger.warning(
                    "LLM Judge failed for %s after %s attempts: %s",
                    metric_name,
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

    def evaluate_triad(self, query: str, answer: str, context: str) -> dict[str, float]:
        """Evaluate the three judge dimensions in one model call.

        This keeps the metrics identical in meaning while reducing benchmark
        cost/latency from three model requests per case to one.
        """
        prompt = f"""
Bạn là giám khảo công bằng cho hệ thống Legal RAG. Hãy chấm độc lập ba tiêu chí
trên thang điểm 0.0 đến 1.0 và chỉ trả về JSON hợp lệ theo mẫu:
{{"answer_relevance": 0.0, "faithfulness": 0.0, "context_precision": 0.0,
"reasons": {{"answer_relevance": "...", "faithfulness": "...", "context_precision": "..."}}}}

Tiêu chí:
- answer_relevance: câu trả lời có trả lời trực tiếp câu hỏi không.
- faithfulness: các nhận định trong câu trả lời có được hỗ trợ bởi context không,
  không tự bịa thông tin.
- context_precision: context có chứa các đoạn hữu ích, liên quan và đủ chính xác
  để trả lời câu hỏi không.

Câu hỏi: {query}
Context:
{context}

Câu trả lời:
{answer}
"""
        last_error = ""
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self._chat(self._retry_prompt(prompt, attempt), self.TRIAD_SCHEMA)
                payload = self._parse_json_response(response["message"]["content"])
                metrics = {}
                reasons = payload.get("reasons", {}) if isinstance(payload, dict) else {}
                for metric in ("answer_relevance", "faithfulness", "context_precision"):
                    metrics[metric] = self._coerce_score(payload.get(metric, 0.0))
                    self.last_reasons[metric] = str(reasons.get(metric, "Judge returned no reason")).strip()
                return metrics
            except Exception as exc:
                last_error = str(exc)
                if attempt == self.max_attempts:
                    logger.warning(
                        "LLM Judge triad failed after %s attempts: %s",
                        self.max_attempts,
                        last_error,
                    )

        reason = f"LLM judge unavailable: {last_error or 'unknown error'}"
        for metric in ("answer_relevance", "faithfulness", "context_precision"):
            self.last_reasons[metric] = reason
        return {metric: 0.0 for metric in ("answer_relevance", "faithfulness", "context_precision")}
