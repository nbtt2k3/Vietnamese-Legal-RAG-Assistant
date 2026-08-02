"""
Glue toàn bộ: loader -> parser -> lưu processed.
data/raw/<loai_van_ban>/*.pdf|*.docx  ->  data/processed/<loai_van_ban>/<doc_id>.json
"""
import json
import re
import unicodedata
import hashlib
from pathlib import Path
from datetime import date
from dataclasses import asdict, is_dataclass

from ingestion.loader.loader_factory import LoaderFactory
from ingestion.parser.parser_factory import ParserFactory
from ingestion.cleaner.cleaner_factory import CleanerFactory
from ingestion.metadata.metadata_factory import MetadataFactory
from ingestion.source_registry import apply_source_registry
from ingestion.parser.structure import LoaiVanBan, VanBan, AnLe
from app.core.config import settings
from app.core.logging import logger
from app.db.models import Document, DocumentRelationship
from app.db.session import SessionLocal
import copy

RAW_DIR = settings.raw_dir
PARSED_DIR = settings.parsed_dir
CLEANED_DIR = settings.cleaned_dir
METADATA_DIR = settings.metadata_dir

# "Luật số:", "Bộ luật số:", "Nghị định số:"... hoặc chỉ "Số:" trơn (Nghị định/Thông tư thường ghi kiểu này)
RE_SO_HIEU = re.compile(
    r'(?:(?:Luật|Bộ luật|Nghị định|Thông tư|Nghị quyết|Quyết định|Chỉ thị|Pháp lệnh|Lệnh)\s+)?[Ss]ố[:\s]*([\d]+[a-zA-Z]?/\d{4}/[A-ZĐ0-9\-]+)'
)

# "...được Quốc hội ... thông qua ngày 24 tháng 11 năm 2015." — dùng cho Luật/Bộ luật
RE_NGAY_BAN_HANH_LUAT = re.compile(
    r'thông qua\s+ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})',
    re.IGNORECASE
)

# "Hà Nội, ngày 09 tháng 01 năm 2026" — dùng cho Nghị định/Thông tư (không có chữ "thông qua",
# ngày ký nằm trong bảng quốc hiệu ở đầu văn bản)
RE_NGAY_KY = re.compile(
    r'ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})'
)

RE_NGAY_HIEU_LUC = [
    re.compile(
        r'có hiệu lực thi hành từ ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})',
        re.IGNORECASE
    ),
    re.compile(
        r'có hiệu lực thi hành kể từ ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})',
        re.IGNORECASE
    ),
    re.compile(
        r'có hiệu lực kể từ ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})',
        re.IGNORECASE
    ),
    re.compile(
        r'có hiệu lực từ ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})',
        re.IGNORECASE
    ),
    re.compile(
        r'bắt đầu có hiệu lực(?: thi hành)?\s+từ ngày\s+(\d{1,2})[-/](\d{1,2})[-/](\d{4})',
        re.IGNORECASE
    ),
]


def build_raw_text(loaded: dict) -> str:
    """Nối toàn bộ các trang/document thành 1 chuỗi text duy nhất cho parser."""
    text = "\n".join(d["text"] for d in loaded["documents"] if d["text"].strip())
    return unicodedata.normalize("NFC", text)


def _page_ranges(loaded: dict) -> list[tuple[int, int, int]]:
    """Return (page_number, start_offset, end_offset) in the parser input."""
    ranges = []
    cursor = 0
    for item in loaded.get("documents", []):
        page_text = str(item.get("text", "") or "")
        start = cursor
        end = start + len(page_text)
        page_number = item.get("page") or len(ranges) + 1
        ranges.append((int(page_number), start, end))
        cursor = end + 1  # build_raw_text joins pages with one newline
    return ranges


def _page_for_offset(ranges: list[tuple[int, int, int]], offset: int) -> int | None:
    for page_number, start, end in ranges:
        if start <= offset <= end:
            return page_number
    return None


def _find_text_offset(raw_text: str, value: str) -> int | None:
    """Find a section in parser text, tolerating line wrapping differences."""
    value = str(value or "").strip()
    if not value:
        return None
    direct = raw_text.find(value[:160])
    if direct >= 0:
        return direct
    prefix = re.sub(r"\s+", " ", value[:120]).strip()
    if len(prefix) < 20:
        return None
    pattern = re.escape(prefix).replace(r"\ ", r"\s+")
    match = re.search(pattern, raw_text, flags=re.IGNORECASE)
    return match.start() if match else None


def _set_source_location(node, location: dict):
    if not hasattr(node, "metadata") or node.metadata is None:
        node.metadata = {}
    node.metadata["source_location"] = dict(location)


def attach_source_locations(document, raw_text: str, loaded: dict):
    """Attach page-level provenance to legal nodes without changing node text."""
    ranges = _page_ranges(loaded)
    if not ranges:
        return

    document_location = {
        "source_format": loaded.get("file_type"),
        "page_start": ranges[0][0],
        "page_end": ranges[-1][0],
        "locator_confidence": "document_span",
    }
    _set_source_location(document, document_location)

    if isinstance(document, AnLe):
        # Án lệ has no Điều/Khoản tree, so locate its semantic sections directly.
        for field_name in (
            "tinh_huong_phap_ly",
            "giai_phap_phap_ly",
            "noi_dung_an_le_trich_dan",
            "noi_dung_vu_an",
        ):
            offset = _find_text_offset(raw_text, getattr(document, field_name, ""))
            location = dict(document_location)
            page = _page_for_offset(ranges, offset) if offset is not None else None
            if page is not None:
                location.update({"page_start": page, "page_end": page, "locator_confidence": "section_text"})
            _set_source_location(document, location)
            # Keep field-level locations available to downstream citation code.
            document.metadata.setdefault("section_locations", {})[field_name] = location
        return

    article_label = "\u0110i\u1ec1u"
    article_label_upper = "\u0110I\u1ec0U"
    heading_pattern = re.compile(
        rf"(?im)^[ \t]*(?:{article_label}|{article_label_upper})[ \t]+\d+[A-Za-z]*\b"
    )
    heading_matches = list(heading_pattern.finditer(raw_text))

    for dieu in document.all_dieu() if isinstance(document, VanBan) else []:
        match = re.search(
            rf"(?im)^[ \t]*(?:{article_label}|{article_label_upper})[ \t]+{re.escape(str(dieu.number))}\b",
            raw_text,
        )
        location = dict(document_location)
        if match:
            next_heading = next((item for item in heading_matches if item.start() > match.start()), None)
            end_offset = (next_heading.start() - 1) if next_heading else match.end()
            page_start = _page_for_offset(ranges, match.start())
            page_end = _page_for_offset(ranges, end_offset)
            if page_start is not None:
                location.update({"page_start": page_start, "locator_confidence": "article_span"})
            if page_end is not None:
                location["page_end"] = max(location.get("page_start", page_end), page_end)
        _set_source_location(dieu, location)
        for khoan in dieu.khoan:
            _set_source_location(khoan, location)
            for diem in khoan.diem:
                _set_source_location(diem, location)


def build_source_metadata(file_path: Path, doc_id: str | None = None) -> dict:
    """Record local-source provenance without claiming legal-source verification."""
    resolved_path = file_path.resolve()
    digest = hashlib.sha256()
    with open(resolved_path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)

    try:
        relative_path = resolved_path.relative_to(RAW_DIR.resolve()).as_posix()
    except ValueError:
        relative_path = resolved_path.as_posix()

    metadata = {
        "source_file": relative_path,
        "source_format": file_path.suffix.lower().lstrip("."),
        "source_checksum_sha256": digest.hexdigest(),
        "source_url": None,
        "source_verification_status": "local_checksum_only",
        "source_verified_at": None,
    }
    if doc_id:
        return apply_source_registry(metadata, doc_id=doc_id)
    return metadata


def guess_so_hieu(raw_text: str) -> str:
    """
    Ưu tiên tìm trong phần TRƯỚC dòng 'Căn cứ' đầu tiên, để tránh bắt nhầm
    số hiệu của văn bản khác được trích dẫn trong phần preamble.
    Nếu không có 'Căn cứ' hoặc không tìm thấy, fallback quét toàn văn bản
    (phòng trường hợp số hiệu nằm ở cuối văn bản, chỗ ký tên).
    """
    can_cu_pos = re.search(r'Căn cứ', raw_text)
    search_zone = raw_text[:can_cu_pos.start()] if can_cu_pos else raw_text[:1500]

    m = RE_SO_HIEU.search(search_zone)
    if m:
        return m.group(1)

    m = RE_SO_HIEU.search(raw_text)
    return m.group(1) if m else "unknown"


def guess_ngay_ban_hanh(raw_text: str) -> str | None:
    """
    Ưu tiên 'thông qua ngày...' (Luật/Bộ luật do Quốc hội thông qua).
    Nếu không có, fallback tìm 'ngày... tháng... năm...' trong ~800 ký tự đầu
    (vùng bảng quốc hiệu) — dùng cho Nghị định/Thông tư/Nghị quyết do cơ quan
    khác ký ban hành, không dùng chữ 'thông qua'.
    """
    m = RE_NGAY_BAN_HANH_LUAT.search(raw_text)
    if not m:
        m = RE_NGAY_KY.search(raw_text[:800])

    if not m:
        return None

    day, month, year = m.groups()
    try:
        return date(int(year), int(month), int(day)).isoformat()   # "2015-11-24"
    except ValueError:
        return None


def guess_ngay_hieu_luc(raw_text: str) -> str | None:
    for pattern in RE_NGAY_HIEU_LUC:
        m = pattern.search(raw_text)
        if not m:
            continue
        day, month, year = m.groups()
        try:
            return date(int(year), int(month), int(day)).isoformat()
        except ValueError:
            continue
    return None


def guess_ten(raw_text: str) -> str:
    """
    Ghép dòng tiêu đề (thường IN HOA, vd 'BỘ LUẬT'/'NGHỊ ĐỊNH') với dòng phụ đề
    ngay sau đó — phụ đề có thể KHÔNG in hoa toàn bộ (vd Nghị định ghi
    'Về tổ chức, hoạt động của quỹ...' chứ không IN HOA như Bộ luật).
    Bỏ qua dòng đầu nếu là letterhead/bảng quốc hiệu (chứa '|' do table join,
    hoặc 'Độc lập'/'CỘNG HÒA').
    """
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]

    start_idx = 0
    for i, l in enumerate(lines[:5]):
        if "|" in l or "Độc lập" in l or "CỘNG HÒA" in l:
            start_idx = i + 1

    stop_words = ("căn cứ", "theo đề nghị", "chính phủ ban hành", "quốc hội ban hành", "ủy ban")
    ten_lines = []
    for l in lines[start_idx:start_idx + 5]:
        if l.lower().startswith(stop_words):
            break
        ten_lines.append(l)
        if len(ten_lines) >= 2:
            break

    ten = " ".join(ten_lines) if ten_lines else (lines[0] if lines else "unknown")
    ten = re.sub(r"\s+", " ", ten).strip()
    return unicodedata.normalize("NFC", ten)


def guess_co_quan_ban_hanh(raw_text: str, loai_van_ban: str) -> str | None:
    """Đoán tên cơ quan ban hành dựa trên loại văn bản hoặc dòng chữ in hoa ở đầu."""
    if loai_van_ban == LoaiVanBan.BO_LUAT.value:
        return "QUỐC HỘI"
    if loai_van_ban == LoaiVanBan.NGHI_DINH.value:
        return "CHÍNH PHỦ"
    if loai_van_ban == LoaiVanBan.NGHI_QUYET.value:
        header = raw_text[:500]
        if "QUỐC HỘI" in header: return "QUỐC HỘI"
        if "HỘI ĐỒNG THẨM PHÁN" in header: return "HỘI ĐỒNG THẨM PHÁN TÒA ÁN NHÂN DÂN TỐI CAO"
        if "ỦY BAN THƯỜNG VỤ" in header: return "ỦY BAN THƯỜNG VỤ QUỐC HỘI"
        if "CHÍNH PHỦ" in header: return "CHÍNH PHỦ"
        
    # Thử quét 10 dòng đầu tìm đoạn in hoa
    lines = raw_text[:1000].split('\n')
    for line in lines[:10]:
        line = line.strip()
        if not line: continue
        if '|' in line:
            left = line.split('|')[0]
            left = re.sub(r'[_]+', '', left)
            left = re.sub(r'[Ss]ố:.*', '', left)
            left = left.strip()
            if left and left != "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM":
                return left
        else:
            if line.isupper() and "CỘNG HÒA" not in line and "ĐỘC LẬP" not in line and "SỐ:" not in line:
                clean_line = re.sub(r'[_]+', '', line).strip()
                if clean_line:
                    return clean_line
    return None


def to_serializable(obj):
    """Chuyển VanBan/AnLe (nested dataclass) sang dict thuần để json.dump."""
    if isinstance(obj, VanBan):
        return {
            "doc_id": obj.doc_id,
            "loai_van_ban": obj.loai_van_ban.value,
            "so_hieu": obj.so_hieu,
            "ten": obj.ten,
            "ngay_ban_hanh": obj.ngay_ban_hanh,
            "ngay_hieu_luc": obj.ngay_hieu_luc,
            "co_quan_ban_hanh": obj.co_quan_ban_hanh,
            "can_cu": obj.can_cu,
            "sua_doi_bo_sung": obj.sua_doi_bo_sung,
            "co_phu_luc": bool(obj.phu_luc),
            "do_dai_phu_luc_ky_tu": sum(len(p.get("noi_dung", "")) for p in obj.phu_luc),
            "phu_luc": obj.phu_luc,
            "so_luong_dieu": len(obj.all_dieu()),
            "metadata": obj.metadata,
            "dieu": [d.to_dict() for d in obj.all_dieu()],
            "hierarchy": _serialize_hierarchy(obj),
        }
    if isinstance(obj, AnLe):
        return obj.to_dict()
    if is_dataclass(obj):
        return asdict(obj)
    raise TypeError(f"Không serialize được: {type(obj)}")


def _serialize_hierarchy(document: VanBan) -> list[dict]:
    """Persist the legal tree separately from retrieval-oriented flat articles."""
    nodes: list[dict] = []

    def add(node, fallback_type: str):
        meta = dict(getattr(node, "metadata", {}).get("hierarchy", {}) or {})
        if meta:
            nodes.append({
                "node_id": meta.get("node_id"),
                "node_type": meta.get("node_type", fallback_type),
                "parent_id": meta.get("parent_id"),
                "ancestor_ids": meta.get("ancestor_ids", []),
                "path": meta.get("path", []),
                "number": getattr(node, "number", None),
                "title": getattr(node, "title", None),
            })

    def add_article(dieu):
        add(dieu, "dieu")
        for khoan in dieu.khoan:
            add(khoan, "khoan")
            for diem in khoan.diem:
                add(diem, "diem")

    add(document, "document")
    for chuong in document.chuong:
        add(chuong, "chuong")
        for muc in chuong.muc:
            add(muc, "muc")
            for dieu in muc.dieu:
                add_article(dieu)
        for dieu in chuong.dieu:
            add_article(dieu)
    for dieu in document.dieu:
        add_article(dieu)
    return nodes


def process_file(file_path: Path, loai_van_ban: str) -> tuple[dict, dict, dict]:  # parsed, cleaned, metadata
    loader = LoaderFactory.get_loader(str(file_path))
    loaded = loader.load(str(file_path))

    raw_text = build_raw_text(loaded)
    doc_id = file_path.stem   # dùng tên file làm doc_id, đơn giản & dễ trace
    source_metadata = build_source_metadata(file_path, doc_id=doc_id)

    parser = ParserFactory.get_parser(loai_van_ban)

    if loai_van_ban == LoaiVanBan.AN_LE.value:
        parsed = parser.parse(raw_text, doc_id)
    else:
        so_hieu = guess_so_hieu(raw_text)
        ten = guess_ten(raw_text)
        parsed = parser.parse(raw_text, doc_id, so_hieu, ten)
        parsed.ngay_ban_hanh = guess_ngay_ban_hanh(raw_text)
        parsed.ngay_hieu_luc = guess_ngay_hieu_luc(raw_text)
        parsed.co_quan_ban_hanh = guess_co_quan_ban_hanh(raw_text, loai_van_ban)
        
        # Giả lập truy xuất CSDL tình trạng hiệu lực pháp luật
    parsed.metadata.setdefault("source", source_metadata)
    # Preserve page provenance and OCR diagnostics before all copies/enrichment.
    if loaded.get("file_type") == "pdf":
        pages = loaded.get("documents", [])
        source_metadata.update({
            "pdf_page_count": len(pages),
            "pdf_ocr_pages": [p.get("page") for p in pages if p.get("ocr_used")],
            "pdf_ocr_used": any(p.get("ocr_used") for p in pages),
        })
    attach_source_locations(parsed, raw_text, loaded)
    parsed_dict = to_serializable(parsed)

    parsed_copy = copy.deepcopy(parsed)

    cleaner = CleanerFactory.get_cleaner(loai_van_ban)
    cleaned = cleaner.clean(parsed_copy)
    cleaned_dict = to_serializable(cleaned)
    
    # Metadata Enrichment
    metadata_copy = copy.deepcopy(cleaned)
    metadata_builder = MetadataFactory.get_builder(loai_van_ban)
    metadata_builder.build(metadata_copy)
    
    metadata_dict = to_serializable(metadata_copy)
    
    # Sanity check: compare max Dieu number with total parsed
    if "dieu" in parsed_dict and parsed_dict["dieu"]:
        last_dieu_number_str = str(parsed_dict["dieu"][-1].get("number", "0"))
        try:
            # Trích xuất số nếu có chứa chữ cái phụ (vd: 12a -> 12)
            last_dieu_match = re.search(r'^(\d+)', last_dieu_number_str)
            if last_dieu_match:
                last_dieu = int(last_dieu_match.group(1))
                total_dieu = len(parsed_dict["dieu"])
                # Chênh lệch quá lớn (VD: thiếu 10 Điều trở lên)
                if (last_dieu - total_dieu) > 10:
                    logger.warning(f"{doc_id}: Thất thoát Điều! Điều cuối là {last_dieu} nhưng chỉ parse được {total_dieu} Điều.")
        except Exception:
            pass

    return parsed_dict, cleaned_dict, metadata_dict


def run_pipeline(raw_dir: Path = RAW_DIR, parsed_dir: Path = PARSED_DIR, cleaned_dir: Path = CLEANED_DIR, metadata_dir: Path = METADATA_DIR, loai_filter: str = None):
    stats = {"success": 0, "failed": 0, "errors": [], "source_review_required": []}

    try:
        from app.db.init import initialize_database
        initialize_database()
        
        for loai_dir in raw_dir.iterdir():
            if not loai_dir.is_dir():
                continue
            loai_van_ban = loai_dir.name

            if loai_filter and loai_van_ban != loai_filter:
                continue

            try:
                LoaiVanBan(loai_van_ban)
            except ValueError:
                logger.info(f"Bỏ qua thư mục không xác định loại văn bản: {loai_dir}")
                continue

            p_dir = parsed_dir / loai_van_ban
            c_dir = cleaned_dir / loai_van_ban
            m_dir = metadata_dir / loai_van_ban
            p_dir.mkdir(parents=True, exist_ok=True)
            c_dir.mkdir(parents=True, exist_ok=True)
            m_dir.mkdir(parents=True, exist_ok=True)

            files = [f for f in loai_dir.rglob("*") if f.is_file() and f.suffix.lower() in (".pdf", ".docx")]
            logger.info(f"[{loai_van_ban}] tìm thấy {len(files)} file")

            for file_path in files:
                rel_path = file_path.relative_to(loai_dir)
                p_out_dir = p_dir / rel_path.parent
                c_out_dir = c_dir / rel_path.parent
                m_out_dir = m_dir / rel_path.parent
                
                p_out_dir.mkdir(parents=True, exist_ok=True)
                c_out_dir.mkdir(parents=True, exist_ok=True)
                m_out_dir.mkdir(parents=True, exist_ok=True)

                p_out = p_out_dir / f"{file_path.stem}.json"
                c_out = c_out_dir / f"{file_path.stem}.json"
                m_out = m_out_dir / f"{file_path.stem}.json"
                try:
                    parsed_res, cleaned_res, metadata_res = process_file(file_path, loai_van_ban)
                    with open(p_out, "w", encoding="utf-8") as f:
                        json.dump(parsed_res, f, ensure_ascii=False, indent=2)
                    with open(c_out, "w", encoding="utf-8") as f:
                        json.dump(cleaned_res, f, ensure_ascii=False, indent=2)
                    with open(m_out, "w", encoding="utf-8") as f:
                        json.dump(metadata_res, f, ensure_ascii=False, indent=2)
                        
                    # Save to Relational DB
                    with SessionLocal() as db:
                        validity_status = metadata_res.get("metadata", {}).get("legal", {}).get("validity_status", "")
                        doc = db.query(Document).filter(Document.doc_id == metadata_res["doc_id"]).first()
                        if not doc:
                            doc = Document(doc_id=metadata_res["doc_id"])
                            db.add(doc)
                        doc.so_hieu = metadata_res.get("so_hieu")
                        doc.ten = metadata_res.get("ten")
                        doc.loai_van_ban = metadata_res.get("loai_van_ban")
                        doc.ngay_ban_hanh = metadata_res.get("ngay_ban_hanh")
                        doc.ngay_hieu_luc = metadata_res.get("ngay_hieu_luc")
                        doc.co_quan_ban_hanh = metadata_res.get("co_quan_ban_hanh")
                        doc.validity_status = validity_status
                        
                        legal_meta = metadata_res.get("metadata", {}).get("legal", {})
                        doc.url = legal_meta.get("source_url") or legal_meta.get("url")
                        doc.checksum = legal_meta.get("source_checksum_sha256") or legal_meta.get("checksum")
                        doc.verified_at = legal_meta.get("source_verified_at") or legal_meta.get("verified_at")
                        doc.effective_from = legal_meta.get("effective_from")
                        doc.effective_to = legal_meta.get("effective_to")
                        doc.repeal_reason = legal_meta.get("repeal_reason")
                        doc.source_of_validity = legal_meta.get("source_of_validity")
                        doc.source_file = legal_meta.get("source_file")
                        doc.source_format = legal_meta.get("source_format")
                        doc.source_url = legal_meta.get("source_url")
                        doc.source_checksum_sha256 = legal_meta.get("source_checksum_sha256")
                        doc.source_verification_status = legal_meta.get("source_verification_status")
                        doc.source_verified_at = legal_meta.get("source_verified_at")
                        doc.validity_basis = legal_meta.get("validity_basis")
                        doc.validity_confidence = legal_meta.get("validity_confidence")
                        doc.validity_checked_at = legal_meta.get("validity_checked_at")

                        db.query(DocumentRelationship).filter(
                            DocumentRelationship.source_doc_id == metadata_res["doc_id"]
                        ).delete()
                        for rel in legal_meta.get("related_documents", []) or []:
                            db.add(DocumentRelationship(
                                source_doc_id=metadata_res["doc_id"],
                                target_doc_ref=rel.get("target_doc"),
                                relationship_type=rel.get("relation_type") or "related",
                                source_article_id=rel.get("source_article_id"),
                                target_article_id=rel.get("target_dieu") or rel.get("target_article_id"),
                                note=rel.get("note"),
                                relation_source=rel.get("relation_source") or "parsed_text",
                            ))
                        db.commit()
                    
                    source = metadata_res.get("metadata", {}).get("source", {})
                    if source.get("source_verification_status") != "official_verified":
                        review_item = {
                            "file": str(file_path),
                            "doc_id": metadata_res.get("doc_id"),
                            "source_registry_status": source.get("source_registry_status"),
                            "source_verification_status": source.get("source_verification_status"),
                        }
                        stats["source_review_required"].append(review_item)
                        logger.warning(
                            f"SOURCE REVIEW REQUIRED: {file_path.name} "
                            f"({source.get('source_registry_status') or 'unknown registry status'})"
                        )
                    stats["success"] += 1
                    logger.info(f"{file_path.name} -> parsed | cleaned | metadata | db")
                except Exception as e:
                    stats["failed"] += 1
                    stats["errors"].append({"file": str(file_path), "error": str(e)})
                    logger.error(f"{file_path.name}: {e}")
    except Exception as e:
        logger.error(f"Lỗi hệ thống trong quá trình xử lý: {e}")

    return stats


def debug_split(file_path: str, loai_van_ban: str = "bo_luat"):
    """Debug tool: xem parser cắt phụ lục/preamble/body ở đâu."""
    loader = LoaderFactory.get_loader(file_path)
    raw_text = build_raw_text(loader.load(file_path))

    parser = ParserFactory.get_parser(loai_van_ban)
    text = parser._normalize(raw_text)

    main_text, phu_luc_text = parser._split_phu_luc(text)
    preamble, body = parser._split_preamble(main_text)

    print("=== CUỐI PREAMBLE (500 ký tự) ===")
    print(preamble[-500:])
    print("\n=== ĐẦU BODY (1000 ký tự) ===")
    print(body[:1000])
    print(f"\n=== PHỤ LỤC: {len(phu_luc_text)} ký tự ===")
    if phu_luc_text:
        print(phu_luc_text[:300])
