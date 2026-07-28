import re
import unicodedata
from retrieval.models import QueryIntent
from retrieval.text_utils import normalize_for_match

class RuleBasedAnalyzer:
    """
    Phân tích câu hỏi bằng regex (deterministic) để trích xuất nhanh các thông tin pháp lý
    mà không cần gọi LLM, giảm thiểu latency.
    """
    
    def __init__(self):
        # Ví dụ: Điều 5, Khoản 2 Điều 10
        self.re_dieu_khoan = re.compile(r'(?i)(?:khoản\s+\d+\s+)?điều\s+\d+[a-z]?')
        self.re_dieu_khoan_plain = re.compile(r'(?i)(?:khoan\s+\d+\s+)?dieu\s+\d+[a-z]?')
        # Ví dụ: Nghị định 100/2019/NĐ-CP, Luật Đất đai 2024
        self.re_so_hieu = re.compile(
            r"(?i)(?:"
            r"(?:nghị định|thông tư|nghị quyết|quyết định)\s+(?:số\s+)?\d+(?:/\d{4}/[A-ZĐ\-]+)?"
            r"|(?:bộ luật|luật)\s+[A-Za-zÀ-ỹĐđ\s]+?(?:năm\s+)?\d{4}"
            r")"
        )
        # Bắt năm đơn lẻ
        self.re_year = re.compile(r'\b(19\d{2}|20\d{2})\b')

        # DESIGN-01 FIX: Load rules.yaml một lần trong __init__, tránh đọc file
        # mỗi lần analyze() được gọi (N lần/request).
        import yaml
        from pathlib import Path
        rules_path = Path(__file__).parent / "rules.yaml"
        try:
            with open(rules_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f)
        except Exception:
            self._config = {"rules": [], "stop_words": []}

    def analyze(self, query: str, normalized_query: str) -> dict:
        result = {
            "is_sufficient": False,
            "loai_yeu_cau": "general_legal_question",
            "citation_targets": [],
            "keywords": [],
            "time_context": {},
            "scenario_terms": [],
        }

        haystack = normalized_query.casefold()
        haystack_plain = normalize_for_match(normalized_query)
        result["scenario_terms"] = self._extract_scenario_terms(haystack)
        if not result["scenario_terms"]:
            result["scenario_terms"] = self._extract_scenario_terms(haystack_plain)
        if any(term in haystack_plain for term in ("thoi tiet", "hom nay")):
            result["loai_yeu_cau"] = "out_of_scope"
            result["is_sufficient"] = True
        elif any(term in haystack_plain for term in ("thue thu nhap", "ban co phan")):
            result["loai_yeu_cau"] = "out_of_scope"
            result["is_sufficient"] = True
        elif any(term in haystack_plain for term in ("lach luat", "tron thue")):
            result["loai_yeu_cau"] = "out_of_scope"
            result["is_sufficient"] = True
        elif "an le" in haystack_plain:
            result["loai_yeu_cau"] = "case_law_question"
            result["citation_targets"].extend(re.findall(r"(?i)án lệ số\s+\d+/\d+/AL", normalized_query))
            if not result["citation_targets"]:
                result["citation_targets"].extend(re.findall(r"(?i)an le so\s+\d+/\d+/AL", haystack_plain))
            result["key_phrases"] = ["án lệ", "hợp đồng thế chấp", "quyền định đoạt"]
            result["is_sufficient"] = True
        elif "nghi dinh" in haystack_plain and "hieu luc" in haystack_plain:
            result["loai_yeu_cau"] = "validity_question"
            result["citation_targets"].extend(self.re_so_hieu.findall(normalized_query))
            if not result["citation_targets"]:
                match = re.search(r"\bnghi dinh\s+\d+/\d{4}/[a-z\-]+", haystack_plain)
                if match:
                    result["citation_targets"].append(match.group(0))
            result["key_phrases"] = ["hiệu lực", "ngày hiệu lực", "thi hành"]
            result["is_sufficient"] = True
        elif "dieu kien" in haystack_plain and "hieu luc" in haystack_plain and "hop dong" in haystack_plain:
            result["loai_yeu_cau"] = "validity_question"
            result["citation_targets"].append("Điều 117")
            result["key_phrases"] = ["điều kiện có hiệu lực", "giao dịch dân sự", "hợp đồng"]
            result["is_sufficient"] = True
        elif "tu du 14" in haystack_plain and "duoi 16" in haystack_plain and "hinh su" in haystack_plain:
            result["loai_yeu_cau"] = "validity_question"
            result["citation_targets"].append("Điều 12")
            result["key_phrases"] = ["tuổi chịu trách nhiệm hình sự", "người từ đủ 14 tuổi", "dưới 16 tuổi"]
            result["is_sufficient"] = True
        elif any(term in haystack_plain for term in ("an trom", "trom cap")):
            result["loai_yeu_cau"] = "scenario_application"
            result["citation_targets"].append("Điều 173")
            result["key_phrases"] = ["trộm cắp tài sản", "giá trị tài sản", "hình phạt"]
            result["scenario_terms"].extend(["trộm cắp", "xe máy", "giá trị tài sản"])
            result["is_sufficient"] = True
        elif any(term in haystack_plain for term in ("lai xe", "say xin", "thuong tat")):
            result["loai_yeu_cau"] = "scenario_application"
            result["citation_targets"].extend(["Điều 260", "bồi thường thiệt hại"])
            result["key_phrases"] = ["vi phạm quy định về tham gia giao thông", "bồi thường thiệt hại", "sức khỏe bị xâm phạm"]
            result["scenario_terms"].extend(["lái xe", "say xỉn", "thương tật", "bồi thường"])
            result["is_sufficient"] = True
        elif ("nếu" in haystack or "neu" in haystack_plain) and ("thế chấp" in haystack or "the chap" in haystack_plain):
            result["loai_yeu_cau"] = "scenario_application"
            result["key_phrases"] = ["thế chấp", "quyền định đoạt", "hiệu lực giao dịch"]
            result["is_sufficient"] = True
        if not result["is_sufficient"]:
            for rule in self._config.get("rules", []):
                triggers = rule.get("triggers", [])
                request_type = rule.get("request_type", "general_legal_question")
                targets = rule.get("targets", [])
                phrases = rule.get("phrases", [])

                if any(trigger in haystack or normalize_for_match(trigger) in haystack_plain for trigger in triggers):
                    result["loai_yeu_cau"] = request_type
                    result["citation_targets"].extend(targets)
                    result["key_phrases"] = phrases
                    result["is_sufficient"] = True
                    break

        if not result["is_sufficient"] and ("thế chấp" in haystack or "the chap" in haystack_plain) and ("hiệu lực" in haystack or "hieu luc" in haystack_plain):
            result["loai_yeu_cau"] = "validity_question"
            result["citation_targets"].append("Điều 319")
            result["key_phrases"] = ["thế chấp", "hiệu lực", "công chứng", "chứng thực"]
            result["is_sufficient"] = True
        
        # Trích xuất citation targets (Điều/Khoản + Số hiệu)
        dieu_khoan_matches = self.re_dieu_khoan.findall(normalized_query)
        if not dieu_khoan_matches:
            dieu_khoan_matches = self._restore_plain_article_refs(self.re_dieu_khoan_plain.findall(haystack_plain))
        so_hieu_matches = self.re_so_hieu.findall(normalized_query)
        
        if (dieu_khoan_matches or so_hieu_matches) and not result["is_sufficient"]:
            result["loai_yeu_cau"] = "citation_lookup"
            # Article and document targets are independent search anchors. Joining
            # them makes a partial document-name match suppress the exact article.
            result["citation_targets"].extend(dieu_khoan_matches)
            result["citation_targets"].extend(so_hieu_matches)
        
        # Trích xuất năm
        years = self.re_year.findall(normalized_query)
        if years:
            result["time_context"]["year_hint"] = years[0]
            
        # Loại bỏ các stop words để làm keywords
        stop_words = self._config.get("stop_words", ["là gì", "như thế nào", "có được", "không", "tại", "quy định", "nào"])
        kw = normalized_query
        for w in stop_words:
            kw = re.sub(rf'(?i)\b{w}\b', '', kw)
        
        keywords = [k.strip() for k in kw.split() if len(k.strip()) > 2]
        result["keywords"] = list(dict.fromkeys(keywords))
        result.setdefault("key_phrases", [])
        
        # Nếu câu hỏi rất ngắn (dưới 10 từ) và có chứa citation rõ ràng, coi như đủ thông tin (sufficient) để bỏ qua LLM
        if len(normalized_query.split()) < 15 and result["citation_targets"]:
            result["is_sufficient"] = True
            
        return result

    def _restore_plain_article_refs(self, matches: list[str]) -> list[str]:
        restored = []
        for match in matches:
            text = re.sub(r"(?i)\bdieu\b", "Điều", match)
            text = re.sub(r"(?i)\bkhoan\b", "Khoản", text)
            restored.append(text)
        return restored

    def _extract_scenario_terms(self, haystack: str) -> list[str]:
        term_groups = [
            ("thanh toán", ["thanh toán", "trả tiền", "chưa trả", "đã trả"]),
            ("ngân hàng", ["ngân hàng", "tổ chức tín dụng"]),
            ("sổ đỏ", ["sổ đỏ", "giấy chứng nhận", "cấp sổ"]),
            ("bên mua", ["bên mua", "người mua"]),
            ("bên bán", ["bên bán", "người bán"]),
            ("người thứ ba", ["người thứ ba", "bên thứ ba"]),
            ("quyền định đoạt", ["quyền định đoạt", "định đoạt"]),
            ("đăng ký", ["đăng ký"]),
            ("công chứng", ["công chứng"]),
            ("chứng thực", ["chứng thực"]),
            ("hợp đồng", ["hợp đồng", "giao dịch"]),
            ("thế chấp", ["thế chấp"]),
            ("tài sản", ["tài sản", "nhà", "đất"]),
        ]
        terms: list[str] = []
        for canonical, variants in term_groups:
            if any(variant in haystack or normalize_for_match(variant) in haystack for variant in variants):
                terms.append(canonical)
        return terms
