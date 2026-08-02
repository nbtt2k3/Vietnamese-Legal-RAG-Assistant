import json
import uuid
from pathlib import Path
from typing import List, Dict, Any

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)
from tqdm import tqdm
from app.core.logging import logger

class QdrantIndexer:
    def __init__(self, db_path: str = "data/qdrant_db", collection_name: str = "legal_docs", vector_size: int = 1024, recreate: bool = False):
        """
        Khởi tạo kết nối Qdrant cục bộ.
        :param db_path: Đường dẫn thư mục lưu trữ DB
        :param collection_name: Tên collection
        :param vector_size: Kích thước vector (bge-m3 default là 1024)
        """
        self.db_path = db_path
        self.collection_name = collection_name
        self.vector_size = vector_size
        
        from app.core.config import settings
        
        # Khởi tạo client lưu vào file cục bộ
        # Nếu muốn dùng in-memory thì truyền location=":memory:"
        if settings.qdrant_url:
            client_kwargs = {"url": settings.qdrant_url}
            if settings.qdrant_api_key:
                client_kwargs["api_key"] = settings.qdrant_api_key
            self.client = QdrantClient(**client_kwargs)
        else:
            self.client = QdrantClient(path=self.db_path)
        
        self._init_collection(recreate=recreate)

    def close(self):
        """Đóng client để giải phóng lock file local Qdrant."""
        if getattr(self, "client", None) is not None:
            self.client.close()
            self.client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        
    def _init_collection(self, recreate: bool = False):
        """Phase 4: Tạo staging collection cho Atomic Alias Swap"""
        self.active_collection = self.collection_name
        self.staging_collection = f"{self.collection_name}_staging_{uuid.uuid4().hex[:8]}"
        
        logger.info(f"Tạo staging collection '{self.staging_collection}' để index atomically...")
        self.client.create_collection(
            collection_name=self.staging_collection,
            vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
        )
        
        from qdrant_client.http.models import PayloadSchemaType
        
        for field, schema in [
            ("doc_id", PayloadSchemaType.KEYWORD),
            ("loai_van_ban", PayloadSchemaType.KEYWORD),
            ("citation", PayloadSchemaType.TEXT),
            ("text", PayloadSchemaType.TEXT),
            ("validity_status", PayloadSchemaType.KEYWORD),
            ("effective_from", PayloadSchemaType.KEYWORD),
            ("effective_to", PayloadSchemaType.KEYWORD),
            ("node_type", PayloadSchemaType.KEYWORD),
            ("parent_id", PayloadSchemaType.KEYWORD),
            ("node_id", PayloadSchemaType.KEYWORD),
            ("ancestor_ids", PayloadSchemaType.KEYWORD)
        ]:
            self.client.create_payload_index(
                collection_name=self.staging_collection,
                field_name=field,
                field_schema=schema,
            )
        logger.info(f"Đã tạo Payload Index cho staging collection '{self.staging_collection}'.")

    def staging_point_count(self) -> int:
        return int(self.client.count(collection_name=self.staging_collection, exact=True).count)

    def finalize_alias(self, allow_legacy_migration: bool = False):
        """Phase 4: Swap alias atomically to point to the new staging collection."""
        from qdrant_client.http.models import CreateAliasOperation, DeleteAliasOperation
        
        old_target = None
        try:
            aliases = self.client.get_aliases()
            for alias_ops in aliases.aliases:
                if alias_ops.alias_name == self.collection_name:
                    old_target = alias_ops.collection_name
                    break
        except Exception:
            pass

        raw_collection_exists = False
        collections_response = self.client.get_collections().collections
        if any(c.name == self.collection_name for c in collections_response):
            raw_collection_exists = True
            
        if raw_collection_exists and not old_target and not allow_legacy_migration:
            raise RuntimeError(
                "Legacy collection uses the live collection name. Re-run with "
                "--migrate-legacy only after verifying the staging snapshot."
            )
        if raw_collection_exists and not old_target:
            logger.warning(f"Dropping raw collection '{self.collection_name}' to convert it to an alias.")
            self.client.delete_collection(self.collection_name)
        
        operations = []
        if old_target:
            operations.append(DeleteAliasOperation(
                delete_alias={"alias_name": self.collection_name}
            ))
            
        operations.append(CreateAliasOperation(
            create_alias={"collection_name": self.staging_collection, "alias_name": self.collection_name}
        ))
        
        self.client.update_collection_aliases(change_aliases_operations=operations)
        logger.info(f"Đã cập nhật alias '{self.collection_name}' trỏ vào '{self.staging_collection}'.")

        # Retrieval opens short-lived repository contexts.  Clear the shared
        # payload/BM25 snapshots after the atomic swap so the next query sees
        # the new legal corpus even when its point count is unchanged.
        from rag.retrieval.repository import clear_payload_cache
        from rag.retrieval.retrievers.lexical_retriever import clear_bm25_cache
        clear_payload_cache(collection_name=self.collection_name)
        clear_bm25_cache()
        logger.info("Đã invalidated payload snapshot và BM25 cache sau khi rebuild index.")
        
        if old_target and old_target != self.staging_collection:
            logger.info(f"Previous collection '{old_target}' will be cleaned after alias swap.")

            # BUG-14 FIX: Tạo Payload Index trên staging_collection (collection thực),
            # KHÔNG phải trên self.collection_name (alias). Alias forward request đến
            # staging_collection, nhưng dùng tên tường minh tránh nhầm khi rollback.
            from qdrant_client.http.models import PayloadSchemaType
            for field, schema in [
                ("doc_id",          PayloadSchemaType.KEYWORD),
                ("loai_van_ban",    PayloadSchemaType.KEYWORD),
                ("citation",        PayloadSchemaType.TEXT),
                ("text",            PayloadSchemaType.TEXT),
                ("validity_status", PayloadSchemaType.KEYWORD),
                ("effective_from",  PayloadSchemaType.KEYWORD),
                ("effective_to",    PayloadSchemaType.KEYWORD),
                ("node_type",       PayloadSchemaType.KEYWORD),
                ("parent_id",       PayloadSchemaType.KEYWORD),
                ("node_id",         PayloadSchemaType.KEYWORD),
                ("ancestor_ids",    PayloadSchemaType.KEYWORD),
            ]:
                self.client.create_payload_index(
                    collection_name=self.staging_collection,
                    field_name=field,
                    field_schema=schema,
                )
            logger.info("Đã tạo Payload Index thành công.")
        else:
            logger.info(f"Collection '{self.collection_name}' đã tồn tại.")

        self.cleanup_old_staging_collections()

    def cleanup_old_staging_collections(self) -> list[str]:
        """Delete stale staging collections while protecting every alias target."""
        prefix = f"{self.collection_name}_staging_"
        try:
            aliases = self.client.get_aliases().aliases
            protected = {alias.collection_name for alias in aliases}
            protected.add(self.staging_collection)
            collections = self.client.get_collections().collections
        except Exception as exc:
            logger.warning("Không thể liệt kê staging collections để cleanup: %s", exc)
            return []

        deleted: list[str] = []
        for collection in collections:
            name = collection.name
            if not name.startswith(prefix) or name in protected:
                continue
            try:
                # Collection deletion can take longer than the Qdrant client's
                # short default timeout while segments are being compacted.
                self.client.delete_collection(collection_name=name, timeout=60)
                deleted.append(name)
                logger.info("Đã dọn staging collection cũ '%s'.", name)
            except Exception as exc:
                logger.warning("Không thể dọn staging collection '%s': %s", name, exc)

        if not deleted:
            logger.info("Không có staging collection cũ cần dọn.")
        return deleted

    def generate_uuid(self, chunk_id: str) -> str:
        """Qdrant yêu cầu ID là UUID hoặc số nguyên nguyên dương. Dùng UUID dựa trên chunk_id."""
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))

    def index_file(self, file_path: Path) -> int:
        """Đọc 1 file JSON chunk có chứa vector, đẩy lên Qdrant."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                chunks: List[Dict[str, Any]] = json.load(f)
        except Exception as e:
            logger.error(f"Không thể đọc file {file_path.name}: {e}")
            return 0

        doc_id = ""
        for chunk in chunks:
            doc_id = chunk.get("doc_id", "") or doc_id
            if doc_id:
                break

        target_collection = getattr(self, "staging_collection", self.collection_name)
        if doc_id:
            self.client.delete(
                collection_name=target_collection,
                points_selector=Filter(
                    must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]
                ),
            )

        points = []
        for chunk in chunks:
            vector = chunk.get("embedding")
            if not vector:
                logger.warning(f"Chunk {chunk.get('chunk_id')} không có embedding. Bỏ qua.")
                continue
                
            chunk_id = str(chunk.get("chunk_id"))
            text = chunk.get("text", "")
            metadata = chunk.get("metadata", {})
            doc_id = chunk.get("doc_id", "")
            
            # Gộp doc_id và chunk_id vào payload (metadata của qdrant)
            payload = {
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "text": text,
                **metadata
            }
            
            point_id = self.generate_uuid(chunk_id)
            point = PointStruct(
                id=point_id,
                vector=vector,
                payload=payload
            )
            points.append(point)
        if points:
            # Batch upload cho nhanh
            batch_size = 100
            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                self.client.upsert(
                    collection_name=target_collection,
                    points=batch
                )
        return len(points)

    def process_directory(self, data_dir: Path):
        """Quét toàn bộ thư mục embeddings, index vào Qdrant."""
        success_count = 0
        failed_count = 0
        
        # Tìm tất cả file json trong các thư mục con (bo_luat, nghi_dinh, ...)
        json_files = list(data_dir.rglob("*.json"))
        
        if not json_files:
            logger.info(f"No JSON files found in {data_dir}")
            return 0, 0
            
        logger.info(f"Bắt đầu index {len(json_files)} files...")
        
        for file_path in tqdm(json_files, desc="Indexing files"):
            indexed = self.index_file(file_path)
            if indexed > 0:
                success_count += indexed
            else:
                failed_count += 1
                
        logger.info(f"Đã index thành công {success_count} chunks.")
        if failed_count > 0:
            logger.warning(f"Có {failed_count} file gặp lỗi hoặc không chứa vector.")
        return success_count, failed_count
