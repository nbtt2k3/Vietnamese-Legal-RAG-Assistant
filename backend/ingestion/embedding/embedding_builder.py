import json
from pathlib import Path
from typing import List, Dict, Any
from ingestion.embedding.ollama_embedder import OllamaEmbedder
from tqdm import tqdm

class EmbeddingBuilder:
    """
    Lớp xử lý việc đọc file JSON trong data/chunks,
    gọi OllamaEmbedder để lấy vector, sau đó xuất ra thư mục đích.
    """
    def __init__(self, model_name: str = "bge-m3:latest"):
        self.embedder = OllamaEmbedder(model_name=model_name)
        
    def process_file(self, input_path: Path, output_path: Path) -> int:
        """
        Đọc 1 file Chunk (ví dụ: bo_luat_91_2015.json),
        bơm thêm vector cho từng chunk, và lưu thành file JSON mới.
        """
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                chunks: List[Dict[str, Any]] = json.load(f)
        except Exception as e:
            print(f"[ERROR] Không thể đọc file chunk {input_path.name}: {e}")
            return 0

        existing_embeddings = self._load_existing_embeddings(output_path)
            
        success_count = 0
        pending_chunks = []
        
        # Dùng tqdm để tạo thanh tiến trình (progress bar) cho từng chunk trong file
        for chunk in tqdm(chunks, desc=f"Embedding {input_path.name}", leave=False):
            text = chunk.get("text", "")
            if not text:
                continue

            reused = self._try_reuse_embedding(chunk, existing_embeddings)
            if reused:
                success_count += 1
                continue
                
            pending_chunks.append(chunk)

        from app.config import settings
        batch_size = settings.embed_batch_size
        for start in range(0, len(pending_chunks), batch_size):
            batch = pending_chunks[start:start + batch_size]
            vectors = self.embedder.embed_batch([chunk["text"] for chunk in batch])
            if len(vectors) != len(batch):
                vectors = [[] for _ in batch]
            for chunk, vector in zip(batch, vectors):
                if vector:
                    chunk["embedding"] = vector
                    success_count += 1
                else:
                    print(f"[WARN] No embedding for chunk {chunk.get('chunk_id')}")

        if success_count != len(chunks):
            raise RuntimeError(
                f"Embedding incomplete for {input_path.name}: {success_count}/{len(chunks)} chunks succeeded."
            )
                
        # Lưu ra file mới
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)
        temp_path.replace(output_path)
            
        return success_count

    def _load_existing_embeddings(self, output_path: Path) -> Dict[str, Dict[str, Any]]:
        if not output_path.exists():
            return {}
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                existing_chunks = json.load(f)
        except Exception:
            return {}

        mapping: Dict[str, Dict[str, Any]] = {}
        for item in existing_chunks:
            chunk_id = item.get("chunk_id")
            if chunk_id:
                mapping[chunk_id] = item
        return mapping

    def _try_reuse_embedding(self, chunk: Dict[str, Any], existing_embeddings: Dict[str, Dict[str, Any]]) -> bool:
        chunk_id = chunk.get("chunk_id")
        if not chunk_id:
            return False

        previous = existing_embeddings.get(chunk_id)
        if not previous:
            return False

        if previous.get("text") != chunk.get("text"):
            return False

        vector = previous.get("embedding")
        if not vector:
            return False

        chunk["embedding"] = vector
        return True
