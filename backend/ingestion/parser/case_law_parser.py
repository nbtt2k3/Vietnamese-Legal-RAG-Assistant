"""
Parser cho An le - khong ke thua LegalParser vi cau truc khac hoan toan.

Van ban an le thuong den tu PDF nen de dinh page number, footnote va
line-break artifact. Parser nay uu tien lam sach nhung artifact do ngay
tu dau ra parsed de retrieval va citation on dinh hon.
"""
import re
import unicodedata

from .structure import AnLe, LoaiVanBan


class CaseLawParser:
    LOAI_VAN_BAN = LoaiVanBan.AN_LE

    RE_SO_AN_LE = re.compile(r"Án lệ\s+số\s+([\d]+/\d{4}/AL)", re.IGNORECASE)
    RE_NGUON = re.compile(
        r"Nguồn án lệ[:\s]*\n?(.*?)(?=\n\s*Vị trí nội dung|\n\s*Khái quát nội dung|\n\s*-?\s*Tình huống|\n\n)",
        re.DOTALL | re.IGNORECASE,
    )
    RE_TOA_AN = re.compile(
        r"(?:được\s+)?(?:Hội đồng Thẩm phán|Toà án|Tòa án).*?(?:thông qua|xét xử).*?(?=\n\s*Nguồn án lệ|\n\s*Vị trí|\n\s*Khái quát|\n\n)",
        re.IGNORECASE | re.DOTALL,
    )
    RE_NGAY_CONG_BO = re.compile(
        r"công bố.*?ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
        re.IGNORECASE | re.DOTALL,
    )
    RE_VI_TRI = re.compile(
        r"Vị trí nội dung án lệ[:\s]*\n?(.*?)(?=\n\s*Khái quát|\n\s*-?\s*Tình huống|\n\n)",
        re.DOTALL | re.IGNORECASE,
    )
    RE_KHAI_QUAT = re.compile(
        r"Khái quát nội dung(?:\s+của)?(?:\s+án lệ)?[:\s]*\n?(.*?)(?=\n\s*-?\s*Tình huống|\n\s*Giải pháp|\n\n)",
        re.DOTALL | re.IGNORECASE,
    )
    RE_TINH_HUONG = re.compile(
        r"Tình huống (?:pháp lý|án lệ)[:\s]*\n?(.*?)(?=\n\s*-?\s*Giải pháp)",
        re.DOTALL | re.IGNORECASE,
    )
    RE_GIAI_PHAP = re.compile(
        r"Giải pháp pháp lý[:\s]*\n?(.*?)(?=\n\s*Quy định|\n\s*Từ kh[oó]a|\n\s*NỘI DUNG VỤ (?:ÁN|VIỆC))",
        re.DOTALL | re.IGNORECASE,
    )
    RE_QUY_DINH_SECTION = re.compile(
        r"Quy định của pháp luật(?: có)? liên quan[^\n:]*:[:\s]*\n?(.*?)(?=\n\s*Từ kh(?:óa|oá)|\n\s*NỘI DUNG)",
        re.DOTALL | re.IGNORECASE,
    )
    RE_TU_KHOA = re.compile(
        r"Từ kh(?:óa|oá)(?:\s+của\s+án lệ)?[:\s]*\n?(.*?)(?=\n\s*NỘI DUNG VỤ (?:ÁN|VIỆC)|\n\s*NỘI DUNG ÁN LỆ|\n\n)",
        re.DOTALL | re.IGNORECASE,
    )
    RE_NOI_DUNG_VU_AN = re.compile(
        r"NỘI DUNG VỤ (?:ÁN|VIỆC)[:\s]*\n?(.*?)(?=\n\s*NHẬN ĐỊNH CỦA|\n\s*NỘI DUNG ÁN LỆ)",
        re.DOTALL | re.IGNORECASE,
    )
    RE_NOI_DUNG_AN_LE_HEADING = re.compile(r"^NỘI DUNG ÁN LỆ[:\s]*$", re.MULTILINE | re.IGNORECASE)

    RE_PAGE_ARTIFACT = re.compile(r"(?:\n|^)\s*\d+\s*\n\s*\n", re.MULTILINE)
    RE_FOOTNOTE_LINE = re.compile(r"^\s*\d+\s+Án lệ này do .*$", re.MULTILINE)
    RE_STANDALONE_NUMBER_LINE = re.compile(r"^\s*\d+\s*$", re.MULTILINE)

    def parse(self, raw_text: str, doc_id: str) -> AnLe:
        text = self._normalize_text(raw_text)

        so_an_le = self._search(self.RE_SO_AN_LE, text) or "unknown"
        ten = self._extract_ten(text)
        toa_an = self._search(self.RE_TOA_AN, text)

        an_le = AnLe(
            doc_id=doc_id,
            so_an_le=so_an_le,
            ten=ten,
            nguon_an_le=self._clean_extracted_text(self._search(self.RE_NGUON, text)),
            toa_an_ra_quyet_dinh=self._clean_extracted_text(toa_an),
            ngay_cong_bo=self._extract_ngay_cong_bo(toa_an),
            vi_tri_noi_dung=self._clean_extracted_text(self._search(self.RE_VI_TRI, text)),
            khai_quat_noi_dung=self._clean_extracted_text(self._search(self.RE_KHAI_QUAT, text)),
            noi_dung_vu_an=self._clean_extracted_text(self._search(self.RE_NOI_DUNG_VU_AN, text) or ""),
            tinh_huong_phap_ly=self._clean_extracted_text(self._search(self.RE_TINH_HUONG, text) or ""),
            giai_phap_phap_ly=self._clean_extracted_text(self._search(self.RE_GIAI_PHAP, text) or ""),
        )
        an_le.dieu_luat_lien_quan = self._extract_dieu_lien_quan(text)
        an_le.tu_khoa = self._extract_tu_khoa(text)
        an_le.noi_dung_an_le_trich_dan = self._extract_noi_dung_an_le(text)
        return an_le

    def _normalize_text(self, text: str) -> str:
        text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
        text = self.RE_FOOTNOTE_LINE.sub("", text)
        text = self.RE_PAGE_ARTIFACT.sub("\n", text)
        text = self.RE_STANDALONE_NUMBER_LINE.sub("", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _clean_extracted_text(self, text: str | None) -> str | None:
        if not text:
            return text
        text = unicodedata.normalize("NFC", text)
        text = self.RE_FOOTNOTE_LINE.sub("", text)
        text = self.RE_PAGE_ARTIFACT.sub("\n", text)
        text = self.RE_STANDALONE_NUMBER_LINE.sub("", text)
        text = re.sub(r"\s*\n\s*", " ", text)
        text = re.sub(r"\s{2,}", " ", text)
        return text.strip()

    def _search(self, pattern: re.Pattern, text: str) -> str | None:
        match = pattern.search(text)
        if not match:
            return None
        result = match.group(1) if match.groups() else match.group(0)
        return result.strip() if result else None

    def _extract_ten(self, text: str) -> str:
        match = self.RE_SO_AN_LE.search(text)
        if not match:
            return ""

        start = match.end()
        end_candidates = []

        match_toa_an = self.RE_TOA_AN.search(text)
        match_nguon = self.RE_NGUON.search(text)
        if match_toa_an and match_toa_an.start() > start:
            end_candidates.append(match_toa_an.start())
        if match_nguon and match_nguon.start() > start:
            end_candidates.append(match_nguon.start())

        end = min(end_candidates) if end_candidates else len(text)
        ten = text[start:end].strip()
        ten = re.sub(r"^\d+\s*\n", "", ten)
        ten = re.sub(r"\s+", " ", ten).strip()
        ten = re.sub(r"^[\.\-\:]+", "", ten).strip()
        return unicodedata.normalize("NFC", ten)

    def _extract_ngay_cong_bo(self, toa_an_text: str | None) -> str | None:
        if not toa_an_text:
            return None
        match = self.RE_NGAY_CONG_BO.search(toa_an_text)
        if not match:
            return None
        from datetime import date

        day, month, year = match.groups()
        try:
            return date(int(year), int(month), int(day)).isoformat()
        except ValueError:
            return None

    def _extract_dieu_lien_quan(self, text: str) -> list[str]:
        section = self._search(self.RE_QUY_DINH_SECTION, text)
        if not section:
            return []

        bullets = []
        for raw_line in section.split("\n"):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("-"):
                bullets.append(line.lstrip("-").strip())
            elif bullets:
                bullets[-1] += " " + line
            else:
                bullets.append(line)

        result = []
        for bullet in bullets:
            cleaned = self._clean_extracted_text(bullet.rstrip(";").strip())
            if cleaned and re.search(r"(?i)điều\s+\d+|khoản\s+\d+", cleaned):
                result.append(cleaned)
        return result

    def _extract_tu_khoa(self, text: str) -> list[str]:
        section = self._search(self.RE_TU_KHOA, text)
        if not section:
            return []

        section = re.sub(r"^\s*\d+.*$", "", section, flags=re.MULTILINE)
        section = re.sub(r"\s+", " ", section).strip()

        keywords = []
        for item in re.split(r";", section):
            cleaned = self._clean_extracted_text(item.strip(' “”".'))
            if cleaned:
                keywords.append(cleaned)
        return keywords

    def _extract_noi_dung_an_le(self, text: str) -> str:
        match = self.RE_NOI_DUNG_AN_LE_HEADING.search(text)
        if not match:
            return ""
        return self._clean_extracted_text(text[match.end():].strip()) or ""
