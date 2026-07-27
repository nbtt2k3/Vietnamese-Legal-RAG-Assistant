"""
Utility functions for metadata extraction.
"""
import re

def count_words(text: str) -> int:
    if not text:
        return 0
    return len(text.split())

def count_characters(text: str) -> int:
    if not text:
        return 0
    return len(text)
