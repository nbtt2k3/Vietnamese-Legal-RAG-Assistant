import re
from typing import List, Optional

class RecursiveCharacterTextSplitter:
    """
    Splits text recursively by trying to split on large semantic boundaries (paragraphs, sentences)
    before falling back to character counts. 
    Inspired by LangChain's RecursiveCharacterTextSplitter.
    """
    def __init__(
        self,
        chunk_size: int = 1500,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        # Default separators: double newline (paragraphs), single newline (lines), dot (sentences), space (words)
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]

    def split_text(self, text: str) -> List[str]:
        if not text:
            return []
        
        final_chunks = []
        separator = self.separators[-1]
        new_separators = []
        
        for i, s in enumerate(self.separators):
            if s == "":
                separator = s
                break
            if s in text:
                separator = s
                new_separators = self.separators[i + 1:]
                break

        # Splitting by the best found separator
        if separator:
            splits = text.split(separator)
        else:
            splits = list(text)

        # Merge splits up to chunk_size
        good_splits = []
        _merge_splits(splits, separator, self.chunk_size, self.chunk_overlap, good_splits, new_separators, self)
        
        return good_splits

def _merge_splits(
    splits: List[str],
    separator: str,
    chunk_size: int,
    chunk_overlap: int,
    final_chunks: List[str],
    new_separators: List[str],
    splitter: RecursiveCharacterTextSplitter
):
    current_doc = []
    current_length = 0

    for s in splits:
        if separator != "":
            # Reattach separator correctly based on semantic meaning.
            # E.g. ". " should be appended to the end of the previous string.
            if separator == ". ":
                content = s + "."
            else:
                content = s
        else:
            content = s

        content_len = len(content)
        
        if current_length + content_len > chunk_size and current_length > 0:
            joined_doc = _join_docs(current_doc, separator)
            if joined_doc:
                final_chunks.append(joined_doc)
            
            # Start a new doc with overlap
            while current_length > chunk_overlap or (current_length + content_len > chunk_size and current_length > 0):
                pop_len = len(current_doc[0]) + (len(separator) if len(current_doc) > 1 else 0)
                current_length -= pop_len
                current_doc.pop(0)
            
        current_doc.append(content)
        current_length += content_len + (len(separator) if len(current_doc) > 1 else 0)
        
        # If a single split is still larger than chunk_size, we might need to recursively split it
        if content_len > chunk_size and new_separators:
            current_doc.pop() # remove it from current_doc
            sub_splits = splitter.__class__(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=new_separators
            ).split_text(content)
            final_chunks.extend(sub_splits)
            current_length = 0
            
    if current_doc:
        joined_doc = _join_docs(current_doc, separator)
        if joined_doc:
            final_chunks.append(joined_doc)

def _join_docs(docs: List[str], separator: str) -> str:
    if separator == ". ":
        # Already appended "." to the ends
        return " ".join(docs).strip()
    return separator.join(docs).strip()
