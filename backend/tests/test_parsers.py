import pytest
from ingestion.parser.legal_parser import LegalParser
from ingestion.parser.decree_parser import DecreeParser
from ingestion.parser.circular_parser import CircularParser
from ingestion.parser.structure import LoaiVanBan, VanBan

def test_legal_parser_basic():
    parser = LegalParser()
    raw_text = """CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc
LUẬT
DÂN SỰ
Chương I
QUY ĐỊNH CHUNG
Điều 1. Phạm vi điều chỉnh
Luật này quy định địa vị pháp lý, chuẩn mực pháp lý về cách ứng xử của cá nhân.
Điều 2. Đối tượng áp dụng
Cá nhân, pháp nhân.
"""
    van_ban = parser.parse(raw_text, "doc_123", "91/2015/QH13", "Bộ luật Dân sự 2015")
    
    assert van_ban.so_hieu == "91/2015/QH13"
    assert van_ban.ten == "Bộ luật Dân sự 2015"
    chuong_list = van_ban.chuong
    assert len(chuong_list) == 1
    assert chuong_list[0].number == "I"
    assert len(chuong_list[0].dieu) == 2
    assert chuong_list[0].dieu[0].number == "1"
    assert "Phạm vi điều chỉnh" in chuong_list[0].dieu[0].title

def test_decree_parser_extracts_legal_grounds():
    parser = DecreeParser()
    raw_text = """CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc

NGHỊ ĐỊNH
Quy định chi tiết thi hành một số điều của Luật Đất đai

Căn cứ Luật Tổ chức Chính phủ ngày 19 tháng 6 năm 2015;
Căn cứ Luật Đất đai ngày 29 tháng 11 năm 2013;
Theo đề nghị của Bộ trưởng Bộ Tài nguyên và Môi trường;
Chính phủ ban hành Nghị định.

Chương I
QUY ĐỊNH CHUNG
Điều 1. Phạm vi điều chỉnh
Nghị định này quy định chi tiết.
"""
    van_ban = parser.parse(raw_text, "doc_456", "11/2015", "ND")
    assert van_ban.metadata.get("legal_grounds") is not None
    assert len(van_ban.metadata["legal_grounds"]) == 2
    assert "Căn cứ Luật Đất đai" in van_ban.metadata["legal_grounds"][1]

def test_circular_parser_extracts_legal_grounds():
    parser = CircularParser()
    raw_text = """THÔNG TƯ
Hướng dẫn về đăng ký đất đai

Căn cứ Nghị định số 43/2014/NĐ-CP ngày 15 tháng 5 năm 2014;
Theo đề nghị của Tổng cục trưởng Tổng cục Quản lý đất đai;
Bộ trưởng Bộ Tài nguyên và Môi trường ban hành Thông tư.

Điều 1. Phạm vi điều chỉnh
Thông tư này quy định chi tiết.
"""
    van_ban = parser.parse(raw_text, "doc_789", "22/2014", "TT")
    assert van_ban.metadata.get("legal_grounds") is not None
    assert len(van_ban.metadata["legal_grounds"]) == 2
    assert "Theo đề nghị của Tổng cục trưởng" in van_ban.metadata["legal_grounds"][1]

def test_parser_empty_text():
    parser = LegalParser()
    van_ban = parser.parse("", "doc_empty", "", "")
    assert van_ban.doc_id == "doc_empty"
    assert len(van_ban.all_dieu()) == 0

def test_parser_splits_phu_luc():
    parser = LegalParser()
    raw_text = """LUẬT TEST
Điều 1. Test
Nội dung test
PHỤ LỤC I
DANH MỤC NGÀNH NGHỀ
1. Ngành A
"""
    van_ban = parser.parse(raw_text, "doc_pl", "", "")
    assert len(van_ban.phu_luc) > 0
    assert "PHỤ LỤC I" in van_ban.phu_luc[0].get("noi_dung", "")
