import json
import os

import ollama
from tenacity import retry, stop_after_attempt, wait_exponential

from generation.models import LegalAnswer
from generation.prompt_builder import LegalPromptBuilder
from retrieval.models import RetrievalResult
from generation.base_generator import BaseLLMGenerator

class OllamaLegalGenerator(BaseLLMGenerator):
    def __init__(self, model_name: str | None = None, host: str | None = None):
        self.model_name = model_name or os.getenv("LEGAL_RAG_GENERATION_MODEL", "")
        self.host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.prompt_builder = LegalPromptBuilder()
        self.client = ollama.Client(host=self.host) if self.model_name else None

    def is_available(self) -> bool:
        return bool(self.client and self.model_name)

    def generate(self, query: str, retrieval_result: RetrievalResult, history: list = None) -> LegalAnswer | None:
        if not self.is_available():
            return None

        prompt = self.prompt_builder.build(query, retrieval_result)
        system = (
            "Bạn là trợ lý pháp lý Việt Nam. "
            "Chỉ dùng evidence được cung cấp. "
            "Trả về JSON hợp lệ, không thêm markdown."
        )
        try:
            response = self._call_ollama(system, prompt)
            content = response["message"]["content"]
            
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
            else:
                data = json.loads(content)
        except Exception as e:
            import logging
            logging.error(f"[Ollama Generator] JSON Parse Error: {e} - Content: {content if 'content' in locals() else 'None'}")
            return None



        return self._parse_llm_response(data, query, retrieval_result, "ollama")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    def _call_ollama(self, system: str, prompt: str) -> dict:
        return self.client.chat(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            options={"temperature": 0.1},
            format="json",
        )
