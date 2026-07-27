import re
from datetime import date
from typing import Any

from ingestion.metadata.base_builder import BaseMetadataExtractor
from ingestion.parser.structure import AnLe, Diem, Dieu, Khoan, LoaiVanBan, VanBan


class LegalRetrievalMetadataExtractor(BaseMetadataExtractor):
    DOC_TYPE_PATTERN = r"(?:Bộ luật|Luật|Nghị định|Nghị quyết|Thông tư)"
    RE_DOC_REF = re.compile(
        r"(?P<label>"
        r"Bộ luật Dân sự(?: năm \d{4})?|"
        r"Bộ luật Tố tụng dân sự(?: năm \d{4})?|"
        r"Luật(?: sửa đổi, bổ sung một số điều của)? [A-ZĂÂĐÊÔƠƯÁÀẢÃẠẮẰẲẴẶẤẦẨẪẬÉÈẺẼẸẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌỐỒỔỖỘỚỜỞỠỢÚÙỦŨỤỨỪỬỮỰÝỲỶỸỴ][^;,\n]{4,}|"
        r"Nghị định(?: số)?|"
        r"Nghị quyết(?: số)?|"
        r"Thông tư(?: số)?"
        r")"
        r"(?:\s+số)?\s*(?P<so_hieu>\d+[A-ZĐa-zđ\-]?/\d{4}/[A-ZĐ0-9\-]+)?",
        re.IGNORECASE,
    )
    RE_ARTICLE_REF = re.compile(
        r"(?:Điều|điều)\s+(?P<dieu>\d+[A-Za-z]*)"
        r"(?:\s*,\s*(?:Khoản|khoản)\s+(?P<khoan>\d+))?"
        r"(?:\s*,\s*(?:Điểm|điểm)\s+(?P<diem>[a-zđ]))?",
    )

    def extract(self, node, **kwargs):
        if isinstance(node, VanBan):
            self._ensure_metadata(node)
            node.metadata["legal"] = self._build_document_legal_metadata(node)
        elif isinstance(node, AnLe):
            self._ensure_metadata(node)
            node.metadata["legal"] = self._build_case_law_legal_metadata(node)
        elif isinstance(node, Dieu):
            document = kwargs.get("document")
            self._ensure_metadata(node)
            node.metadata["legal"] = self._build_dieu_legal_metadata(node, document)
        elif isinstance(node, Khoan):
            document = kwargs.get("document")
            dieu = kwargs.get("dieu")
            self._ensure_metadata(node)
            node.metadata["legal"] = self._build_khoan_legal_metadata(node, dieu, document)
        elif isinstance(node, Diem):
            document = kwargs.get("document")
            dieu = kwargs.get("dieu")
            khoan = kwargs.get("khoan")
            self._ensure_metadata(node)
            node.metadata["legal"] = self._build_diem_legal_metadata(node, khoan, dieu, document)

    def _build_document_legal_metadata(self, document: VanBan) -> dict[str, Any]:
        canonical_name = self._canonical_document_name(document.ten, document.loai_van_ban)
        references = self._extract_references_from_strings(document.can_cu)
        related_documents = self._normalize_relationships(document.sua_doi_bo_sung)
        validity = self._extract_validity_metadata(document)
        source = self._source_metadata(document)
        return {
            "citation": f"{canonical_name} ({document.so_hieu})",
            "citation_short": f"{self._display_document_type(document.loai_van_ban)} số {document.so_hieu}",
            "document_role": self._document_role(document.loai_van_ban),
            "legal_domain_tags": self._infer_domain_tags(
                " ".join(filter(None, [document.ten, *document.can_cu]))
            ),
            "cited_authorities": references,
            "related_documents": related_documents + validity["related_documents"],
            "temporal_validity_note": self._temporal_validity_note(document, validity),
            "validity_status": validity["validity_status"],
            "effective_date": validity["effective_from"],
            "replaced_documents": validity["replaced_documents"],
            "transition_notes": validity["transition_notes"],
            "url": source.get("source_url"),
            "checksum": source.get("source_checksum_sha256"),
            "verified_at": source.get("source_verified_at"),
            "source_file": source.get("source_file"),
            "source_format": source.get("source_format"),
            "source_url": source.get("source_url"),
            "source_checksum_sha256": source.get("source_checksum_sha256"),
            "source_verification_status": source.get("source_verification_status"),
            "source_verified_at": source.get("source_verified_at"),
            "effective_from": validity["effective_from"],
            "effective_to": validity["effective_to"],
            "repeal_reason": None,
            "source_of_validity": "unverified_parsed_text",
            "validity_basis": validity["validity_basis"],
            "validity_confidence": validity["validity_confidence"],
            "validity_checked_at": None,
        }

    def _build_case_law_legal_metadata(self, node: AnLe) -> dict[str, Any]:
        joined_refs = list(node.dieu_luat_lien_quan)
        if node.nguon_an_le:
            joined_refs.append(node.nguon_an_le)
        source = self._source_metadata(node)
        return {
            "citation": f"Án lệ số {node.so_an_le}",
            "citation_short": node.so_an_le,
            "document_role": "case_law",
            "legal_domain_tags": self._infer_domain_tags(
                " ".join(
                    filter(
                        None,
                        [
                            node.ten,
                            node.tinh_huong_phap_ly,
                            node.giai_phap_phap_ly,
                            " ".join(node.tu_khoa),
                        ],
                    )
                )
            ),
            "cited_authorities": self._extract_references_from_strings(joined_refs),
            "related_documents": self._normalize_case_law_source(node.nguon_an_le),
            "temporal_validity_note": "an_le_da_cong_bo",
            "validity_status": "an_le_da_cong_bo",
            "effective_date": node.ngay_cong_bo,
            "effective_from": node.ngay_cong_bo,
            "effective_to": None,
            "replaced_documents": [],
            "transition_notes": [],
            "url": source.get("source_url"),
            "checksum": source.get("source_checksum_sha256"),
            "verified_at": source.get("source_verified_at"),
            "source_file": source.get("source_file"),
            "source_format": source.get("source_format"),
            "source_url": source.get("source_url"),
            "source_checksum_sha256": source.get("source_checksum_sha256"),
            "source_verification_status": source.get("source_verification_status"),
            "source_verified_at": source.get("source_verified_at"),
            "source_of_validity": "unverified_parsed_text",
            "validity_basis": "case_law_publication_date_parsed",
            "validity_confidence": "medium",
            "validity_checked_at": None,
            "case_law_role": {
                "issue": "tinh_huong_phap_ly",
                "holding": "giai_phap_phap_ly",
                "source_location": node.vi_tri_noi_dung,
            },
            "case_law_schema": {
                "facts_summary": self._truncate_text(node.noi_dung_vu_an, 400),
                "legal_issue": node.tinh_huong_phap_ly,
                "holding": node.giai_phap_phap_ly,
                "reasoning_excerpt": self._truncate_text(node.noi_dung_an_le_trich_dan, 400),
            },
        }

    def _build_dieu_legal_metadata(self, node: Dieu, document: VanBan | None) -> dict[str, Any]:
        title_and_text = " ".join(filter(None, [node.title, node.text]))
        return {
            "citation": self._build_node_citation(document, node.number),
            "citation_short": f"Điều {node.number}",
            "legal_unit_type": "dieu",
            "legal_role": self._infer_legal_role(node.title or "", node.text),
            "legal_domain_tags": self._infer_domain_tags(title_and_text),
            "cited_authorities": self._extract_references_from_strings([title_and_text]),
            "effective_date": node.effective_date or getattr(document, "ngay_hieu_luc", None),
        }

    def _build_khoan_legal_metadata(
        self, node: Khoan, dieu: Dieu | None, document: VanBan | None
    ) -> dict[str, Any]:
        dieu_number = dieu.number if dieu else None
        title_hint = dieu.title if dieu else ""
        return {
            "citation": self._build_node_citation(document, dieu_number, node.number),
            "citation_short": f"Khoản {node.number}",
            "legal_unit_type": "khoan",
            "legal_role": self._infer_legal_role(title_hint, node.text),
            "legal_domain_tags": self._infer_domain_tags(" ".join(filter(None, [title_hint, node.text]))),
            "cited_authorities": self._extract_references_from_strings([node.text]),
            "effective_date": getattr(dieu, "effective_date", None) or getattr(document, "ngay_hieu_luc", None),
        }

    def _build_diem_legal_metadata(
        self,
        node: Diem,
        khoan: Khoan | None,
        dieu: Dieu | None,
        document: VanBan | None,
    ) -> dict[str, Any]:
        dieu_number = dieu.number if dieu else None
        khoan_number = khoan.number if khoan else None
        title_hint = dieu.title if dieu else ""
        return {
            "citation": self._build_node_citation(document, dieu_number, khoan_number, node.id),
            "citation_short": f"Điểm {node.id}",
            "legal_unit_type": "diem",
            "legal_role": self._infer_legal_role(title_hint, node.text),
            "legal_domain_tags": self._infer_domain_tags(" ".join(filter(None, [title_hint, node.text]))),
            "cited_authorities": self._extract_references_from_strings([node.text]),
            "effective_date": getattr(dieu, "effective_date", None) or getattr(document, "ngay_hieu_luc", None),
        }

    def _build_node_citation(
        self,
        document: VanBan | None,
        dieu_number: str | None,
        khoan_number: str | None = None,
        diem_id: str | None = None,
    ) -> str | None:
        if not document or not dieu_number:
            return None
        parts = [self._canonical_document_name(document.ten, document.loai_van_ban), f"Điều {dieu_number}"]
        if khoan_number:
            parts.append(f"Khoản {khoan_number}")
        if diem_id:
            parts.append(f"Điểm {diem_id}")
        return ", ".join(parts)

    def _canonical_document_name(self, title: str, loai_van_ban: LoaiVanBan | str) -> str:
        if not title:
            return self._display_document_type(loai_van_ban)
        normalized = re.sub(r"\s+", " ", title).strip()
        if normalized.isupper():
            normalized = normalized.title()
            normalized = normalized.replace("Dân Sự", "Dân sự").replace("Nghị Định", "Nghị định")
            normalized = normalized.replace("Nghị Quyết", "Nghị quyết").replace("Thông Tư", "Thông tư")
            normalized = normalized.replace("Bộ Luật", "Bộ luật")
        return normalized

    def _display_document_type(self, loai_van_ban: LoaiVanBan | str) -> str:
        value = loai_van_ban.value if hasattr(loai_van_ban, "value") else str(loai_van_ban)
        mapping = {
            "bo_luat": "Bộ luật",
            "nghi_dinh": "Nghị định",
            "nghi_quyet": "Nghị quyết",
            "thong_tu": "Thông tư",
            "an_le": "Án lệ",
        }
        return mapping.get(value, value)

    def _document_role(self, loai_van_ban: LoaiVanBan | str) -> str:
        value = loai_van_ban.value if hasattr(loai_van_ban, "value") else str(loai_van_ban)
        mapping = {
            "bo_luat": "statute_code",
            "nghi_dinh": "implementation_guidance",
            "nghi_quyet": "judicial_guidance",
            "thong_tu": "administrative_guidance",
            "an_le": "case_law",
        }
        return mapping.get(value, "legal_document")

    def _temporal_validity_note(self, document: VanBan, validity: dict[str, Any]) -> str:
        if validity["validity_status"] != "chua_xac_dinh":
            return validity["validity_status"]
        if document.ngay_hieu_luc:
            return "co_ngay_hieu_luc"
        if document.sua_doi_bo_sung:
            return "co_thong_tin_sua_doi_bo_sung"
        return "chua_xac_dinh"

    def _infer_legal_role(self, title: str, text: str) -> str:
        haystack = f"{title} {text}".lower()
        if "giải thích từ ngữ" in haystack or "khái niệm" in haystack or "định nghĩa" in haystack:
            return "definition"
        if "nguyên tắc" in haystack:
            return "principle"
        if "phạm vi điều chỉnh" in haystack or "đối tượng áp dụng" in haystack:
            return "scope"
        if "quyền" in haystack or "nghĩa vụ" in haystack:
            return "rights_obligations"
        if "trừ trường hợp" in haystack or "trường hợp" in haystack or "điều kiện" in haystack:
            return "condition_exception"
        if "xử lý" in haystack or "hậu quả" in haystack:
            return "legal_effect"
        return "rule"

    def _infer_domain_tags(self, text: str) -> list[str]:
        haystack = text.lower()
        tag_rules = {
            "dan_su": ["dân sự", "giao dịch dân sự", "quan hệ dân sự"],
            "hop_dong": ["hợp đồng"],
            "bao_dam": ["bảo đảm", "thế chấp", "cầm cố", "đặt cọc"],
            "tai_san": ["tài sản", "sở hữu", "quyền sở hữu"],
            "thua_ke": ["thừa kế", "di chúc", "di sản"],
            "to_tung": ["tố tụng", "khởi kiện", "tranh chấp"],
            "an_le": ["án lệ"],
            "hinh_su": ["hình sự", "tội phạm", "truy cứu trách nhiệm hình sự", "phạt tù"],
            "dat_dai": ["đất đai", "thửa đất", "quyền sử dụng đất", "sổ đỏ", "nhà ở"],
            "lao_dong": ["lao động", "người lao động", "hợp đồng lao động", "lương", "sa thải"],
            "doanh_nghiep": ["doanh nghiệp", "công ty", "cổ phần", "đầu tư", "phá sản"],
            "thue": ["thuế", "đóng thuế", "khai thuế", "thuế thu nhập"],
        }
        tags = [tag for tag, keywords in tag_rules.items() if any(keyword in haystack for keyword in keywords)]
        return tags or ["phap_luat_viet_nam"]

    def _extract_references_from_strings(self, texts: list[str]) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        seen: set[str] = set()
        for text in texts:
            if not text:
                continue
            article_refs = list(self.RE_ARTICLE_REF.finditer(text))
            doc_refs = list(self.RE_DOC_REF.finditer(text))
            if article_refs or doc_refs:
                for article_match in article_refs:
                    ref_text = article_match.group(0).strip()
                    key = f"article::{ref_text}"
                    if key in seen:
                        continue
                    seen.add(key)
                    refs.append(
                        {
                            "ref_type": "article",
                            "ref_text": ref_text,
                            "normalized_ref": self._normalize_article_ref(article_match),
                        }
                    )
                for doc_match in doc_refs:
                    ref_text = doc_match.group(0).strip(" ;,.")
                    if len(ref_text) < 8:
                        continue
                    if ref_text.lower().startswith("luật ") and len(ref_text.split()) < 3:
                        continue
                    if ref_text.lower().startswith(
                        (
                            "luật này",
                            "bộ luật này",
                            "nghị định này",
                            "nghị quyết này",
                            "thông tư này",
                        )
                    ):
                        continue
                    if not self._is_likely_legal_doc_reference(ref_text):
                        continue
                    key = f"doc::{ref_text.lower()}"
                    if key in seen:
                        continue
                    seen.add(key)
                    refs.append(
                        {
                            "ref_type": "document",
                            "ref_text": ref_text,
                            "normalized_ref": self._normalize_document_ref(doc_match),
                        }
                    )
            else:
                key = f"raw::{text.strip().lower()}"
                if key in seen:
                    continue
                seen.add(key)
                refs.append({"ref_type": "raw", "ref_text": text.strip(), "normalized_ref": text.strip()})
        return refs

    def _extract_validity_metadata(self, document: VanBan) -> dict[str, Any]:
        related_documents = []
        replaced_documents = []
        transition_notes = []
        parsed_effective_from = document.ngay_hieu_luc
        for dieu in document.all_dieu():
            title = (dieu.title or "").lower()
            body_parts = [dieu.text] + [k.text for k in dieu.khoan]
            combined_text = "\n".join(filter(None, body_parts))
            if "hiệu lực" in title or "điều khoản thi hành" in title:
                parsed_effective_from = parsed_effective_from or self._parse_effective_date_from_text(combined_text)
                for ref in self._extract_references_from_strings([combined_text]):
                    if ref["ref_type"] != "document":
                        continue
                    if "hết hiệu lực" in combined_text.lower() or "thay thế" in combined_text.lower():
                        replaced_documents.append(ref["normalized_ref"])
                        related_documents.append(
                            {
                                "relation_type": "replaces_or_terminates",
                                "target_doc": ref["normalized_ref"],
                                "target_dieu": None,
                                "note": dieu.title,
                                "relation_source": "parsed_effective_clause",
                            }
                        )
            if "chuyển tiếp" in title:
                transition_notes.append(combined_text.strip())

        validity_status = "co_ngay_hieu_luc" if parsed_effective_from else "chua_xac_dinh"
        if replaced_documents:
            validity_status = "co_hieu_luc_va_thay_the_van_ban_khac"
        validity_basis = "parsed_effective_clause" if parsed_effective_from else "not_found_in_parsed_text"
        validity_confidence = "medium" if parsed_effective_from else "low"

        return {
            "validity_status": validity_status,
            "related_documents": related_documents,
            "replaced_documents": sorted(set(replaced_documents)),
            "transition_notes": transition_notes[:3],
            "effective_from": parsed_effective_from,
            "effective_to": None,
            "validity_basis": validity_basis,
            "validity_confidence": validity_confidence,
        }

    def _parse_effective_date_from_text(self, text: str) -> str | None:
        patterns = [
            r"có hiệu lực(?: thi hành)?(?: kể)? từ ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
            r"có hiệu lực(?: thi hành)?(?: kể)? từ ngày\s+(\d{1,2})[-/](\d{1,2})[-/](\d{4})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text or "", re.IGNORECASE)
            if not match:
                continue
            day, month, year = match.groups()
            try:
                return date(int(year), int(month), int(day)).isoformat()
            except ValueError:
                continue
        return None

    def _source_metadata(self, document: VanBan | AnLe) -> dict[str, Any]:
        source = dict(getattr(document, "metadata", {}).get("source", {}) or {})
        return {
            "source_file": source.get("source_file"),
            "source_format": source.get("source_format"),
            "source_checksum_sha256": source.get("source_checksum_sha256"),
            "source_url": source.get("source_url"),
            "source_verification_status": source.get("source_verification_status", "unverified"),
            "source_verified_at": source.get("source_verified_at"),
        }

    def _is_likely_legal_doc_reference(self, ref_text: str) -> bool:
        lowered = ref_text.lower()
        if " số " in lowered:
            return True
        if re.match(rf"^{self.DOC_TYPE_PATTERN}\s+[A-ZĂÂĐÊÔƠƯÁÀẢÃẠẮẰẲẴẶẤẦẨẪẬÉÈẺẼẸẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌỐỒỔỖỘỚỜỞỠỢÚÙỦŨỤỨỪỬỮỰÝỲỶỸỴ]", ref_text):
            return True
        return bool(
            re.match(
                r"^(Bộ luật Dân sự|Bộ luật Tố tụng dân sự)(?: năm \d{4})?$",
                ref_text,
                re.IGNORECASE,
            )
        )

    def _truncate_text(self, text: str | None, max_len: int) -> str | None:
        if not text:
            return text
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) <= max_len:
            return text
        return text[: max_len - 3].rstrip() + "..."

    def _normalize_document_ref(self, match: re.Match[str]) -> str:
        label = re.sub(r"\s+", " ", match.group("label")).strip()
        so_hieu = match.group("so_hieu")
        if so_hieu:
            return f"{label} {so_hieu}"
        return label

    def _normalize_article_ref(self, match: re.Match[str]) -> str:
        parts = [f"Điều {match.group('dieu')}"]
        if match.group("khoan"):
            parts.append(f"Khoản {match.group('khoan')}")
        if match.group("diem"):
            parts.append(f"Điểm {match.group('diem')}")
        return ", ".join(parts)

    def _normalize_relationships(self, relations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = []
        for item in relations:
            target_doc = (
                item.get("target_doc")
                or item.get("target_so_hieu")
                or item.get("target_van_ban")
            )
            relation_type = item.get("type")
            if not target_doc and not relation_type:
                continue
            note_parts = [item.get("note"), item.get("target_type")]
            note = " | ".join([part for part in note_parts if part])
            normalized.append(
                {
                    "relation_type": relation_type or "related",
                    "target_doc": target_doc,
                    "target_dieu": item.get("target_dieu"),
                    "target_khoan": item.get("target_khoan"),
                    "note": note or None,
                    "relation_source": item.get("relation_source") or "parsed_text",
                }
            )
        return normalized

    def _normalize_case_law_source(self, source_text: str | None) -> list[dict[str, Any]]:
        if not source_text:
            return []
        return [{"relation_type": "case_law_source", "target_doc": source_text, "relation_source": "parsed_case_law_source"}]

    def _ensure_metadata(self, node):
        if not hasattr(node, "metadata") or node.metadata is None:
            node.metadata = {}
