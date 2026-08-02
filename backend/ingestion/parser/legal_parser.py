"""
Base parser dùng chung cho nhóm văn bản Điều/Khoản/Điểm
(Bộ luật, Nghị định, Thông tư, Nghị quyết).
Class con override _extract_preamble() và _post_process() nếu cần đặc thù riêng.
"""
import re
import unicodedata
from .structure import VanBan, Chuong, Muc, Dieu, Khoan, Diem, LoaiVanBan

class LegalParser:
    LOAI_VAN_BAN: LoaiVanBan = None   # override ở class con

    # ---- Regex nhận diện các tầng cấu trúc ----
    RE_PHAN   = re.compile(r'^\s*Phần\s+(?:thứ\s+)?([IVXLCDM]+|\d+|nhất|hai|ba|tư|bốn|năm|sáu|bảy|tám|chín|mười[a-z\s]*)\.?\s*(.*)$', re.MULTILINE | re.IGNORECASE)
    RE_CHUONG = re.compile(r'^\s*Chương\s+([IVXLCDM]+|\d+|nhất|hai|ba|tư|bốn|năm|sáu|bảy|tám|chín|mười[a-z\s]*)\.?\s*(.*)$', re.MULTILINE | re.IGNORECASE)
    RE_MUC    = re.compile(r'^\s*Mục\s+(\d+|[IVXLCDM]+)\.?\s*(.*)$', re.MULTILINE | re.IGNORECASE)
    RE_DIEU   = re.compile(r'^\s*(?:Điều|Ðiều|Diều|Điêù|Điểu)\s+(\d+)[.:]?\s*(.*)$', re.MULTILINE | re.IGNORECASE)

    # Phụ lục: mẫu văn bản, biểu mẫu — thường tự đánh số "Điều 1, Điều 2..."
    # RIÊNG của nó (vd mẫu Điều lệ), cần tách ra TRƯỚC khi parse Điều,
    # nếu không sẽ bị nối nhầm vào Điều của chính văn bản, gây trùng số.
    RE_PHU_LUC = re.compile(r'^\s*(?:Phụ\s+lục\b|Mẫu\s+số\b)', re.MULTILINE | re.IGNORECASE)

    # Khoản: "1. nội dung" — chỉ match khi ở đầu dòng, số + dấu chấm
    RE_KHOAN  = re.compile(r'^\s*(\d{1,3})\.\s+(.*)$')

    # Điểm: "a) nội dung" hoặc "a. nội dung"
    RE_DIEM   = re.compile(r'^\s*([a-zđ])[\)\.]\s+(.*)$')

    # Trích dẫn chéo — vd "quy định tại Điều 465 Bộ luật này", "khoản 2 Điều 12 Nghị định số 43/2014/NĐ-CP"
    RE_CROSS_REF = re.compile(
        r'(?:khoản\s+(\d+)\s+)?[Đđ]iều\s+(\d+)'
        r'(?:\s+(?:của\s+)?(Bộ luật này|Luật này|Nghị định này|'
        r'(?:Bộ luật|Luật|Nghị định|Thông tư)\s+(?:số\s+)?[\d/\-A-ZĐ]+))?'
    )


    # Đánh dấu sửa đổi/bổ sung/bãi bỏ chèn trong ngoặc, vd:
    # "(được sửa đổi bởi khoản 3 Điều 1 Nghị định 91/2015/NĐ-CP)"
    RE_AMEND_MARK = re.compile(
        r'\((được\s+)?(sửa đổi|bổ sung|bãi bỏ|thay thế)\s+(?:bởi|theo)\s+'
        r'(?:khoản\s+(\d+)\s+)?[Đđ]iều\s+(\d+)\s+'
        r'([^\)]+)\)',
        re.IGNORECASE
    )

    def parse(self, raw_text: str, doc_id: str, so_hieu: str, ten: str) -> VanBan:
        text = self._normalize(raw_text)

        # Tách Phụ lục TRƯỚC khi tách preamble/body — xem lý do ở RE_PHU_LUC phía trên.
        main_text, phu_luc_text = self._split_phu_luc(text)
        
        # Tách phần chữ ký, Nơi nhận (thường ở cuối văn bản) để tránh bị gán vào Điều cuối cùng
        main_text, sign_text = self._split_signature_block(main_text)
        
        preamble_text, body_text = self._split_preamble(main_text)

        van_ban = VanBan(
            doc_id=doc_id,
            loai_van_ban=self.LOAI_VAN_BAN,
            so_hieu=so_hieu,
            ten=ten,
        )
        self._extract_preamble(preamble_text, van_ban)
        self._parse_body(body_text, van_ban)

        if phu_luc_text.strip():
            van_ban.phu_luc = self._parse_phu_luc(phu_luc_text)

        self._post_process(van_ban)
        return van_ban

    # ---------- Các bước dùng chung ----------

    def _normalize(self, text: str) -> str:
        """Chuẩn hoá whitespace, nối câu bị xuống dòng giữa chừng (do PDF)."""
        text = unicodedata.normalize("NFC", text.replace('\r\n', '\n').replace('\r', '\n'))
        lines = text.split('\n')
        merged = []
        for line in lines:
            stripped = line.strip()
            if (merged and stripped and not stripped[0].isupper()
                    and not self._is_structure_marker(stripped)
                    and merged[-1] and not merged[-1][-1] in '.:;'):
                merged[-1] = merged[-1] + ' ' + stripped
            else:
                merged.append(stripped)
        return '\n'.join(merged)

    def _is_structure_marker(self, line: str) -> bool:
        return bool(
            self.RE_DIEU.match(line) or self.RE_CHUONG.match(line)
            or self.RE_MUC.match(line) or self.RE_PHAN.match(line)
            or self.RE_KHOAN.match(line) or self.RE_DIEM.match(line)
        )

    def _split_phu_luc(self, text: str) -> tuple[str, str]:
        """Tách Phụ lục (mẫu văn bản, biểu mẫu) khỏi phần nội dung chính."""
        m = self.RE_PHU_LUC.search(text)
        if not m:
            return text, ""
        return text[:m.start()], text[m.start():]

    def _parse_phu_luc(self, text: str) -> list[dict]:
        """Chia khối phụ lục thành mảng các biểu mẫu riêng biệt dựa trên 'Mẫu số...' hoặc 'Phụ lục...'."""
        import re
        # Tách dựa trên từ khóa Mẫu số/Phụ lục nằm ở đầu dòng
        # Phụ lục phải đi kèm số La mã hoặc chữ cái in hoa (VD: Phụ lục I, Phụ lục A) để tránh cắt nhầm câu có chữ "Phụ lục"
        # Bắt thêm trường hợp song ngữ như Mẫu số 05b1 /Form No 05b1
        parts = re.split(r'(?i)\n(Mẫu\s+số[\s:]*[\w\-\.]+(?:\s*/\s*Form\s+No\.?[\s:]*[\w\-\.]+)?|Phụ\s+lục[\s:]*[IVX0-9A-Z]+)\b', '\n' + text)
        result = []
        
        # Phần trước mẫu biểu đầu tiên (thường là Danh mục, Mở đầu phụ lục)
        intro = parts[0].strip()
        current_chung_text = intro
        current_pl = "Phụ lục"
        
        # Thử tìm Phụ lục I, II, A, B... trong đoạn đầu của intro
        import re
        match_pl = re.search(r'(?i)^(Phụ\s+lục[\s:]*[IVX0-9A-Z]+)', intro[:200])
        if match_pl:
            current_pl = match_pl.group(1).strip()
            
        for i in range(1, len(parts), 2):
            ma_mau = parts[i].strip()
            noi_dung = parts[i+1].strip()

            # Some official DOCX files put a long appendix heading around the
            # actual form marker, e.g. "Phụ lục DANH - Mẫu số 01a". Keep the
            # stable form identifier instead of embedding heading noise.
            compact_marker = re.sub(r"\s+", " ", ma_mau).strip()
            form_match = re.search(
                r"Mẫu\s+số\s+([0-9]+[A-Za-z0-9.-]*)",
                compact_marker,
                flags=re.IGNORECASE,
            )
            if form_match:
                ma_mau = f"Mẫu số {form_match.group(1)}"
            
            # Cập nhật current_pl nếu ma_mau là "Phụ lục..." (thường xuất hiện khi chuyển sang phụ lục mới trong bảng danh mục)
            if re.match(r'(?i)^Phụ\s+lục[\s:]*[IVX0-9A-Z]+', ma_mau):
                current_pl = ma_mau
            
            # Kiểm tra xem đây có phải là một dòng trong bảng danh mục hay không
            # Nếu nội dung rất ngắn (<= 3 dòng, hoặc < 300 ký tự), thì gộp vào phần Phụ lục chung
            if len(noi_dung.split('\n')) <= 3 or len(noi_dung) < 300:
                # Gộp vào phụ lục chung
                current_chung_text += "\n" + ma_mau + " " + noi_dung
                continue
                
            # Tìm dòng chữ in hoa làm tên mẫu (bỏ qua dòng CỘNG HÒA XÃ HỘI)
            ten_mau = ""
            for line in noi_dung.split('\n'):
                l_strip = line.strip()
                if l_strip and l_strip.isupper() and "CỘNG H" not in l_strip and "ĐỘC LẬP" not in l_strip:
                    ten_mau = l_strip
                    break
            
            # Nếu không tìm thấy dòng in hoa, lấy dòng đầu tiên không trống
            if not ten_mau:
                for line in noi_dung.split('\n'):
                    l_strip = line.strip()
                    if l_strip and "CỘNG H" not in l_strip.upper() and "ĐỘC LẬP" not in l_strip.upper():
                        ten_mau = l_strip
                        break
                        
            # Giới hạn độ dài ten_mau nếu nó quá dài
            if len(ten_mau) > 150:
                ten_mau = ten_mau[:147] + "..."
                
            # Thêm tiền tố Phụ lục vào mã mẫu nếu văn bản có nhiều Phụ lục (Phụ lục I, Phụ lục II)
            if "Phụ lục" in current_pl and current_pl.lower() != "phụ lục" and "Mẫu" in ma_mau:
                ma_mau_display = f"{current_pl} - {ma_mau}"
            else:
                ma_mau_display = ma_mau
                
            result.append({
                "ma_mau": ma_mau_display,
                "ten_mau": ten_mau,
                "noi_dung": noi_dung
            })
            
        # Thêm phần phụ lục chung vào đầu danh sách nếu có nội dung
        if current_chung_text.strip():
            result.insert(0, {
                "ma_mau": "Chung",
                "ten_mau": "Danh mục / Quy định chung",
                "noi_dung": current_chung_text.strip()
            })
            
        return result

    def _split_preamble(self, text: str) -> tuple[str, str]:
        """
        Tách phần mở đầu (Căn cứ...) khỏi phần nội dung chính.
        Điểm bắt đầu nội dung chính = vị trí SỚM NHẤT trong số Phần / Chương / Điều.
        """
        candidates = []
        for pattern in (self.RE_PHAN, self.RE_CHUONG, self.RE_DIEU):
            m = pattern.search(text)
            if m:
                candidates.append(m.start())

        if not candidates:
            return text, ""

        split_at = min(candidates)
        return text[:split_at], text[split_at:]

    def _split_signature_block(self, text: str) -> tuple[str, str]:
        """
        Tìm và cắt bỏ khối 'Nơi nhận:' và chữ ký ở cuối văn bản.
        """
        footer_patterns = [
            re.compile(r'^\s*Nơi nhận\s*:', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^\s*NƠI NHẬN\s*:', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^\s*TM\.\s*', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^\s*KT\.\s*', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^\s*CHỦ TỊCH\b', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^\s*PHÓ THỦ TƯỚNG\b', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^\s*BỘ TRƯỞNG\b', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^\s*THỨ TRƯỞNG\b', re.IGNORECASE | re.MULTILINE),
        ]

        tail_start = max(0, len(text) - 2500)
        tail_text = text[tail_start:]
        candidate_idx = None

        for pattern in footer_patterns:
            match = pattern.search(tail_text)
            if not match:
                continue

            idx = tail_start + match.start()
            if candidate_idx is None or idx < candidate_idx:
                candidate_idx = idx

        # Official DOCX/PDF sources often flatten the footer into a Markdown-like
        # table line ("| Nơi nhận: ..."), so the anchored patterns above do not
        # match.  Treat the first such line as the start of the administrative
        # footer and keep it out of legal content.
        inline_recipient = re.search(
            r"(?im)(?:^|\n)\s*\|?\s*Nơi\s+nhận\s*:",
            text,
        )
        if inline_recipient:
            idx = inline_recipient.start()
            if text[idx:idx + 1] == "\n":
                idx += 1
            if candidate_idx is None or idx < candidate_idx:
                candidate_idx = idx

        if candidate_idx is not None:
            return text[:candidate_idx].strip(), text[candidate_idx:].strip()

        return text, ""

    def _extract_preamble(self, preamble_text: str, van_ban: VanBan):
        """Extract các dòng 'Căn cứ...'. Override ở class con nếu cần thêm logic."""
        for line in preamble_text.split('\n'):
            line = line.strip()
            if line.lower().startswith('căn cứ'):
                van_ban.can_cu.append(line)

    def _parse_body(self, body_text: str, van_ban: VanBan):
        """Parse phần thân: Phần -> Chương → Mục → Điều."""
        phan_matches = list(self.RE_PHAN.finditer(body_text))
        
        if not phan_matches:
            self._parse_chuong_list(body_text, van_ban)
            return
            
        for i, pm in enumerate(phan_matches):
            start = pm.end()
            end = phan_matches[i + 1].start() if i + 1 < len(phan_matches) else len(body_text)
            phan_body = body_text[start:end]
            
            # Tiêu đề của Phần thường bị match vào group 2 (do \s* match luôn cả newline)
            phan_number = pm.group(1).strip()
            phan_title = pm.group(2).strip() or None
            
            # Fallback nếu regex không bắt được title
            if not phan_title:
                lines = [l.strip() for l in phan_body.split('\n') if l.strip()]
                if lines and not lines[0].lower().startswith('chương') and not lines[0].lower().startswith('điều'):
                    phan_title = lines[0]
                    
            # Nếu tựa đề lấy ra quá dài (có thể bắt nhầm nội dung điều luật), huỷ bỏ
            if phan_title and len(phan_title) > 200:
                phan_title = None
                
            self._parse_chuong_list(phan_body, van_ban, phan_number.upper(), phan_title)

    def _parse_chuong_list(self, text: str, van_ban: VanBan, phan_number=None, phan_title=None):
        chuong_matches = list(self.RE_CHUONG.finditer(text))

        if not chuong_matches:
            van_ban.dieu.extend(self._parse_dieu_list(text, phan_number=phan_number, phan_title=phan_title))
            return

        for i, cm in enumerate(chuong_matches):
            start = cm.end()
            end = chuong_matches[i + 1].start() if i + 1 < len(chuong_matches) else len(text)
            chuong_body = text[start:end]
            
            chuong_number = cm.group(1).strip()
            chuong_title = cm.group(2).strip() or None
            
            if not chuong_title:
                lines = [l.strip() for l in chuong_body.split('\n') if l.strip()]
                if lines and not lines[0].lower().startswith('mục') and not lines[0].lower().startswith('điều'):
                    chuong_title = lines[0]
                    
            if chuong_title and len(chuong_title) > 200:
                chuong_title = None
                
            chuong = Chuong(number=chuong_number.upper(), title=chuong_title, phan_number=phan_number, phan_title=phan_title)

            muc_matches = list(self.RE_MUC.finditer(chuong_body))
            if not muc_matches:
                chuong.dieu = self._parse_dieu_list(chuong_body, phan_number=phan_number, phan_title=phan_title, chuong_number=chuong.number, chuong_title=chuong.title)
            else:
                for j, mm in enumerate(muc_matches):
                    m_start = mm.end()
                    m_end = muc_matches[j + 1].start() if j + 1 < len(muc_matches) else len(chuong_body)
                    muc_body = chuong_body[m_start:m_end]
                    
                    muc_number = mm.group(1).strip()
                    muc_title = mm.group(2).strip() or None
                    
                    if not muc_title:
                        lines = [l.strip() for l in muc_body.split('\n') if l.strip()]
                        if lines and not lines[0].lower().startswith('điều'):
                            muc_title = lines[0]
                            
                    if muc_title and len(muc_title) > 200:
                        muc_title = None
                        
                    muc = Muc(number=muc_number.upper(), title=muc_title)
                    muc.dieu = self._parse_dieu_list(
                        muc_body, phan_number=phan_number, phan_title=phan_title, chuong_number=chuong.number, chuong_title=chuong.title, muc_number=muc.number, muc_title=muc.title
                    )
                    chuong.muc.append(muc)

            van_ban.chuong.append(chuong)

    def _parse_dieu_list(self, text: str, phan_number=None, phan_title=None, chuong_number=None, chuong_title=None, muc_number=None, muc_title=None) -> list[Dieu]:
        matches = list(self.RE_DIEU.finditer(text))
        result = []
        for i, m in enumerate(matches):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            dieu_body = text[start:end]

            dieu = Dieu(
                number=m.group(1),
                title=m.group(2).strip() or None,
                phan_number=phan_number,
                phan_title=phan_title,
                chuong_number=chuong_number,
                chuong_title=chuong_title,
                muc_number=muc_number,
                muc_title=muc_title,
            )
            dieu.text, dieu.khoan = self._parse_khoan_diem(dieu_body)
            self._extract_amendments(dieu_body, dieu)
            result.append(dieu)
        return result

    def _parse_khoan_diem(self, dieu_body: str) -> tuple[str, list[Khoan]]:
        """Tách phần mở đầu (nếu có) và list Khoản/Điểm trong 1 Điều."""
        lines = [l for l in dieu_body.split('\n') if l.strip()]
        intro_lines = []
        khoan_list: list[Khoan] = []
        current_khoan: Khoan | None = None

        for line in lines:
            km = self.RE_KHOAN.match(line)
            dm = self.RE_DIEM.match(line)

            if km and not current_khoan:
                current_khoan = Khoan(number=km.group(1), text=km.group(2).strip())
                khoan_list.append(current_khoan)
            elif km:
                current_khoan = Khoan(number=km.group(1), text=km.group(2).strip())
                khoan_list.append(current_khoan)
            elif dm and current_khoan:
                current_khoan.diem.append(Diem(id=dm.group(1), text=dm.group(2).strip()))
            elif current_khoan:
                if current_khoan.diem:
                    current_khoan.diem[-1].text += '\n' + line.strip()
                else:
                    current_khoan.text += '\n' + line.strip()
            else:
                intro_lines.append(line.strip())

        return '\n'.join(intro_lines).strip(), khoan_list

    def _extract_amendments(self, dieu_body: str, dieu: Dieu):
        for m in self.RE_AMEND_MARK.finditer(dieu_body):
            action, khoan_ref, dieu_ref, source = m.group(2), m.group(3), m.group(4), m.group(5)
            note = f"{action} bởi " + (f"khoản {khoan_ref} " if khoan_ref else "") + f"Điều {dieu_ref} {source.strip()}"
            if 'bãi bỏ' in action.lower():
                dieu.repealed = True
                dieu.repealed_by = note
            else:
                dieu.amended_by.append(note)

    def extract_cross_references(self, text: str) -> list[dict]:
        """Tìm mọi trích dẫn chéo trong 1 đoạn text — dùng cho citation_builder."""
        refs = []
        for m in self.RE_CROSS_REF.finditer(text):
            refs.append({
                "khoan": m.group(1),
                "dieu": m.group(2),
                "van_ban": m.group(3) or "văn bản hiện tại",
            })
        return refs

    def _post_process(self, van_ban: VanBan):
        """Hook cho class con — mặc định không làm gì."""
        pass
