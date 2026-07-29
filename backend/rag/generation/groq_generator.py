import json
import os

from groq import Groq

from rag.generation.models import LegalAnswer
from rag.generation.prompt_builder import LegalPromptBuilder
from rag.retrieval.models import RetrievalResult
from rag.generation.base_generator import BaseLLMGenerator


class GroqLegalGenerator(BaseLLMGenerator):
    def __init__(self, model_name: str | None = None, api_key: str | None = None):
        self.model_name = model_name or os.getenv("LEGAL_RAG_GENERATION_MODEL", "llama-3.3-70b-versatile")
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.prompt_builder = LegalPromptBuilder()
        self.client = Groq(api_key=self.api_key) if self.api_key else None

    def is_available(self) -> bool:
        return bool(self.client and self.model_name)

    def generate(self, query: str, retrieval_result: RetrievalResult, history: list = None) -> LegalAnswer | None:
        if not self.is_available():
            print("[WARNING] GROQ_API_KEY không được tìm thấy. Bỏ qua Groq Generator.")
            return None

        prompt = self.prompt_builder.build(query, retrieval_result)
        system = (
            "Bạn là trợ lý pháp lý Việt Nam. "
            "Chỉ dùng các căn cứ được cung cấp. "
            "Trả về JSON hợp lệ với cấu trúc sau: {\"short_answer\": \"\", \"quy_dinh_phap_luat\": [{\"claim\": \"\", \"reasoning\": \"\", \"evidence_ids\": [\"E1\"]}], \"ap_dung_so_bo\": [], \"tinh_tiet_can_bo_sung\": [], \"rui_ro_phap_ly\": [], \"buoc_tiep_theo\": [], \"conflict_detected\": false, \"uncertainty\": \"\"}. "
            "Không xuất thêm markdown, không xuất block ```json."
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            data = json.loads(content)
        except Exception as e:
            print(f"[ERROR] Lỗi khi gọi Groq API: {e}")
            return None

        return self._parse_llm_response(data, query, retrieval_result, "groq_llama3")
