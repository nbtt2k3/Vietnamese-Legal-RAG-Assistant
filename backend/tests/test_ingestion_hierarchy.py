from ingestion.chunker.legal_chunker import LegalChunker
from ingestion.metadata.metadata_factory import MetadataFactory
from ingestion.parser.structure import Chuong, Dieu, Diem, Khoan, LoaiVanBan, Muc, VanBan
from ingestion.pipeline import attach_source_locations, to_serializable


def test_page_locator_propagates_to_article_tree_and_chunks():
    document = _document()
    loaded = {
        "file_type": "pdf",
        "documents": [
            {"page": 1, "text": "Phần mở đầu\n"},
            {"page": 2, "text": "Điều 12. Quyền dân sự\nNội dung khoản 1"},
        ],
    }
    raw_text = "\n".join(page["text"] for page in loaded["documents"])
    attach_source_locations(document, raw_text, loaded)
    MetadataFactory.get_builder("bo_luat").build(document)
    chunks = LegalChunker().chunk(to_serializable(document))

    article = document.chuong[0].muc[0].dieu[0]
    assert article.metadata["source_location"]["page_start"] == 2
    clause = next(chunk for chunk in chunks if chunk.metadata.get("node_type") == "khoan")
    assert clause.metadata["source_location"]["page_start"] == 2
    assert clause.metadata["source_location"]["source_format"] == "pdf"


def _document() -> VanBan:
    diem = Diem(id="a", text="Nội dung điểm a")
    khoan = Khoan(number="1", text="Nội dung khoản 1", diem=[diem])
    dieu = Dieu(number="12", title="Quyền dân sự", khoan=[khoan])
    muc = Muc(number="1", title="Quy định chung", dieu=[dieu])
    chuong = Chuong(number="II", title="Quyền và nghĩa vụ", muc=[muc])
    return VanBan(
        doc_id="bo_luat_test",
        loai_van_ban=LoaiVanBan.BO_LUAT,
        so_hieu="01/2026/QH",
        ten="Bộ luật kiểm thử",
        chuong=[chuong],
    )


def test_hierarchy_metadata_contains_stable_parent_chain():
    document = _document()
    MetadataFactory.get_builder("bo_luat").build(document)

    hierarchy = document.chuong[0].muc[0].dieu[0].khoan[0].diem[0].metadata["hierarchy"]
    assert hierarchy["node_type"] == "diem"
    assert hierarchy["parent_id"].endswith("_khoan_12_1")
    assert hierarchy["ancestor_ids"]
    assert hierarchy["path"][-1] == "Điểm a"


def test_serialized_document_keeps_flat_articles_and_tree():
    document = _document()
    MetadataFactory.get_builder("bo_luat").build(document)
    serialized = to_serializable(document)

    assert len(serialized["dieu"]) == 1
    assert serialized["hierarchy"]
    assert {node["node_type"] for node in serialized["hierarchy"]} == {
        "document", "chuong", "muc", "dieu", "khoan", "diem"
    }


def test_chunks_carry_hierarchy_fields_without_losing_citation():
    document = _document()
    MetadataFactory.get_builder("bo_luat").build(document)
    chunks = LegalChunker().chunk(to_serializable(document))

    clause = next(chunk for chunk in chunks if chunk.metadata.get("node_type") == "khoan")
    assert clause.metadata["node_id"].endswith("_khoan_12_1")
    assert clause.metadata["parent_id"].endswith("_dieu_12")
    assert clause.metadata["ancestor_ids"]
    assert clause.metadata["citation"].endswith("Điều 12, Khoản 1")
