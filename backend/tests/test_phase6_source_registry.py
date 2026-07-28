from pathlib import Path

from ingestion.metadata.extractors.legal_retrieval_metadata import LegalRetrievalMetadataExtractor
from ingestion.parser.structure import AnLe, LoaiVanBan, VanBan
from ingestion.source_registry import (
    apply_source_registry,
    audit_source_registry,
    enrich_metadata_from_source_registry,
    load_source_registry,
)
from scripts.validate_source_registry import validate_source_registry_file


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _base_source():
    return {
        "source_file": "bo_luat/dan_su/sample.pdf",
        "source_format": "pdf",
        "source_checksum_sha256": "abc123",
        "source_url": None,
        "source_verification_status": "local_checksum_only",
        "source_verified_at": None,
    }


def test_source_registry_absent_keeps_local_checksum_status():
    enriched = apply_source_registry(_base_source(), doc_id="doc1", registry={"documents": []})

    assert enriched["source_verification_status"] == "local_checksum_only"
    assert enriched["source_registry_status"] == "not_found"
    assert enriched["source_url"] is None


def test_source_registry_applies_official_source_only_when_evidence_is_complete():
    registry = {
        "documents": [
            {
                "doc_id": "doc1",
                "source_checksum_sha256": "abc123",
                "source_url": "https://example.gov.vn/doc1",
                "source_verified_at": "2026-07-28",
                "source_verification_status": "official_verified",
                "validity_status": "dang_co_hieu_luc",
                "source_of_validity": "official_registry",
                "validity_basis": "official_validity_registry",
                "validity_confidence": "high",
                "validity_checked_at": "2026-07-28",
                "effective_from": "2017-01-01",
            }
        ]
    }

    enriched = apply_source_registry(_base_source(), doc_id="doc1", registry=registry)

    assert enriched["source_registry_status"] == "matched"
    assert enriched["source_verification_status"] == "official_verified"
    assert enriched["source_url"] == "https://example.gov.vn/doc1"
    assert enriched["validity_status"] == "dang_co_hieu_luc"
    assert enriched["validity_checked_at"] == "2026-07-28"


def test_source_registry_checksum_mismatch_does_not_claim_official_source():
    registry = {
        "documents": [
            {
                "doc_id": "doc1",
                "source_checksum_sha256": "different",
                "source_url": "https://example.gov.vn/doc1",
                "source_verified_at": "2026-07-28",
                "source_verification_status": "official_verified",
            }
        ]
    }

    enriched = apply_source_registry(_base_source(), doc_id="doc1", registry=registry)

    assert enriched["source_registry_status"] == "checksum_mismatch"
    assert enriched["source_verification_status"] == "local_checksum_only"
    assert enriched["source_url"] is None


def test_source_registry_incomplete_official_source_does_not_apply_validity():
    registry = {
        "documents": [
            {
                "doc_id": "doc1",
                "source_checksum_sha256": "abc123",
                "source_verification_status": "official_verified",
                "validity_status": "dang_co_hieu_luc",
                "source_of_validity": "csdl_quoc_gia_vbpl",
                "validity_basis": "official_validity_registry",
                "validity_confidence": "high",
                "validity_checked_at": "2026-07-28",
            }
        ]
    }

    enriched = apply_source_registry(_base_source(), doc_id="doc1", registry=registry)

    assert enriched["source_registry_status"] == "incomplete_official_evidence"
    assert enriched["source_verification_status"] == "local_checksum_only"
    assert "validity_status" not in enriched
    assert "validity_checked_at" not in enriched


def test_source_registry_official_source_without_complete_validity_does_not_override_validity():
    registry = {
        "documents": [
            {
                "doc_id": "doc1",
                "source_checksum_sha256": "abc123",
                "source_url": "https://example.gov.vn/doc1",
                "source_verified_at": "2026-07-28",
                "source_verification_status": "official_verified",
                "validity_status": "dang_co_hieu_luc",
                "source_of_validity": "unverified_parsed_text",
                "validity_basis": "parsed_effective_clause",
                "validity_confidence": "medium",
                "validity_checked_at": "2026-07-28",
            }
        ]
    }

    enriched = apply_source_registry(_base_source(), doc_id="doc1", registry=registry)

    assert enriched["source_registry_status"] == "matched"
    assert enriched["source_verification_status"] == "official_verified"
    assert "validity_status" not in enriched
    assert "validity_checked_at" not in enriched


def test_retrieval_metadata_enrichment_skips_candidates_without_provenance():
    metadata = {"citation": "Bo luat Dan su, Dieu 1"}

    enriched = enrich_metadata_from_source_registry(
        metadata,
        doc_id="bo_luat_91_2015_QH13",
        registry={
            "documents": [
                {
                    "doc_id": "bo_luat_91_2015_QH13",
                    "source_checksum_sha256": "abc123",
                    "source_url": "https://example.gov.vn/doc1",
                    "source_verified_at": "2026-07-28",
                    "source_verification_status": "official_verified",
                }
            ]
        },
    )

    assert enriched == metadata


def test_legal_metadata_uses_verified_validity_override_from_source_registry():
    source = apply_source_registry(
        _base_source(),
        doc_id="doc1",
        registry={
            "documents": [
                {
                    "doc_id": "doc1",
                    "source_checksum_sha256": "abc123",
                    "source_url": "https://example.gov.vn/doc1",
                    "source_verified_at": "2026-07-28",
                    "source_verification_status": "official_verified",
                    "validity_status": "dang_co_hieu_luc",
                "source_of_validity": "csdl_quoc_gia_vbpl",
                    "validity_basis": "official_validity_registry",
                    "validity_confidence": "high",
                    "validity_checked_at": "2026-07-28",
                    "effective_from": "2017-01-01",
                }
            ]
        },
    )
    document = VanBan(
        doc_id="doc1",
        loai_van_ban=LoaiVanBan.BO_LUAT,
        so_hieu="91/2015/QH13",
        ten="Bo luat Dan su",
        ngay_hieu_luc="2017-01-01",
        metadata={"source": source},
    )

    LegalRetrievalMetadataExtractor().extract(document)
    legal = document.metadata["legal"]

    assert legal["source_verification_status"] == "official_verified"
    assert legal["validity_status"] == "dang_co_hieu_luc"
    assert legal["source_of_validity"] == "csdl_quoc_gia_vbpl"
    assert legal["validity_basis"] == "official_validity_registry"
    assert legal["validity_confidence"] == "high"
    assert legal["validity_checked_at"] == "2026-07-28"


def test_legal_metadata_keeps_parsed_validity_when_registry_has_no_validity_check():
    document = VanBan(
        doc_id="doc1",
        loai_van_ban=LoaiVanBan.BO_LUAT,
        so_hieu="91/2015/QH13",
        ten="Bo luat Dan su",
        ngay_hieu_luc="2017-01-01",
        metadata={"source": _base_source()},
    )

    LegalRetrievalMetadataExtractor().extract(document)
    legal = document.metadata["legal"]

    assert legal["source_verification_status"] == "local_checksum_only"
    assert legal["validity_status"] == "co_ngay_hieu_luc"
    assert legal["source_of_validity"] == "unverified_parsed_text"
    assert legal["validity_checked_at"] is None


def test_legal_metadata_rejects_non_official_validity_override():
    source = {
        **_base_source(),
        "source_verification_status": "local_checksum_only",
        "validity_status": "dang_co_hieu_luc",
        "source_of_validity": "csdl_quoc_gia_vbpl",
        "validity_basis": "official_validity_registry",
        "validity_confidence": "high",
        "validity_checked_at": "2026-07-28",
        "effective_from": "2017-01-01",
    }
    document = VanBan(
        doc_id="doc1",
        loai_van_ban=LoaiVanBan.BO_LUAT,
        so_hieu="91/2015/QH13",
        ten="Bo luat Dan su",
        ngay_hieu_luc="2017-01-01",
        metadata={"source": source},
    )

    LegalRetrievalMetadataExtractor().extract(document)
    legal = document.metadata["legal"]

    assert legal["validity_status"] == "co_ngay_hieu_luc"
    assert legal["source_of_validity"] == "unverified_parsed_text"
    assert legal["validity_checked_at"] is None


def test_case_law_metadata_keeps_effective_fields_consistent_with_verified_validity():
    source = apply_source_registry(
        _base_source(),
        doc_id="an_le_1",
        registry={
            "documents": [
                {
                    "doc_id": "an_le_1",
                    "source_checksum_sha256": "abc123",
                    "source_url": "https://example.gov.vn/an-le-1",
                    "source_verified_at": "2026-07-28",
                    "source_verification_status": "official_verified",
                    "validity_status": "an_le_bi_bai_bo",
                    "source_of_validity": "csdl_an_le_tandtc",
                    "validity_basis": "official_case_law_registry",
                    "validity_confidence": "high",
                    "validity_checked_at": "2026-07-28",
                    "effective_from": "2020-01-01",
                    "effective_to": "2026-01-01",
                }
            ]
        },
    )
    case_law = AnLe(
        doc_id="an_le_1",
        so_an_le="01/2020/AL",
        ten="An le test",
        ngay_cong_bo="2020-02-01",
        metadata={"source": source},
    )

    LegalRetrievalMetadataExtractor().extract(case_law)
    legal = case_law.metadata["legal"]

    assert legal["validity_status"] == "an_le_bi_bai_bo"
    assert legal["temporal_validity_note"] == "an_le_bi_bai_bo"
    assert legal["effective_date"] == "2020-01-01"
    assert legal["effective_from"] == "2020-01-01"
    assert legal["effective_to"] == "2026-01-01"


def test_bundled_source_registry_has_no_audit_issues():
    registry = load_source_registry()

    assert audit_source_registry(registry) == []
    assert registry["documents"]


def test_source_registry_validation_script_passes_bundled_registry():
    issues = validate_source_registry_file(PROJECT_ROOT / "backend" / "data" / "source_registry.json")

    assert issues == []


def test_source_registry_validation_script_fails_incomplete_official_source(tmp_path):
    registry_path = tmp_path / "source_registry.json"
    registry_path.write_text(
        """
        {
          "documents": [
            {
              "doc_id": "doc1",
              "source_checksum_sha256": "abc123",
              "source_verification_status": "official_verified"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    issues = validate_source_registry_file(registry_path)

    assert any(issue["code"] == "incomplete_official_source" for issue in issues)


def test_source_registry_audit_rejects_invalid_aliases_shape():
    issues = audit_source_registry(
        {
            "documents": [
                {
                    "doc_id": "doc1",
                    "source_verification_status": "local_checksum_only",
                    "aliases": "Bộ luật Dân sự",
                }
            ]
        }
    )

    assert any(issue["code"] == "invalid_aliases" for issue in issues)
