from abc import ABC, abstractmethod
from typing import Union
from ingestion.parser.structure import VanBan, AnLe
import ingestion.cleaner.rules as rules

class BaseCleaner(ABC):
    def __init__(self):
        self.text_rules = [
            rules.normalize_unicode,
            rules.clean_whitespace,
            rules.clean_noise,
            rules.clean_punctuation,
            rules.normalize_citation,
        ]

    def apply_rules(self, text: str) -> str:
        if not text:
            return text
        for rule in self.text_rules:
            text = rule(text)
        return text

    @abstractmethod
    def clean(self, document: Union[VanBan, AnLe]) -> Union[VanBan, AnLe]:
        pass