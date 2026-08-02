from types import SimpleNamespace

from ingestion.indexing.indexer import QdrantIndexer


def test_cleanup_old_staging_collections_preserves_active_and_alias_targets():
    class FakeClient:
        def __init__(self):
            self.deleted = []

        def get_aliases(self):
            return SimpleNamespace(
                aliases=[
                    SimpleNamespace(
                        alias_name="legal_docs",
                        collection_name="legal_docs_staging_active",
                    )
                ]
            )

        def get_collections(self):
            return SimpleNamespace(
                collections=[
                    SimpleNamespace(name="legal_docs_staging_active"),
                    SimpleNamespace(name="legal_docs_staging_previous"),
                    SimpleNamespace(name="legal_docs_staging_other"),
                    SimpleNamespace(name="unrelated_collection"),
                ]
            )

        def delete_collection(self, collection_name, timeout):
            assert timeout == 60
            self.deleted.append(collection_name)

    indexer = QdrantIndexer.__new__(QdrantIndexer)
    indexer.collection_name = "legal_docs"
    indexer.staging_collection = "legal_docs_staging_new"
    indexer.client = FakeClient()

    deleted = indexer.cleanup_old_staging_collections()

    assert deleted == [
        "legal_docs_staging_previous",
        "legal_docs_staging_other",
    ]
    assert indexer.client.deleted == deleted
