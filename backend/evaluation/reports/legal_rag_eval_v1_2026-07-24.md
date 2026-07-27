# Evaluation Report: legal_rag_eval_v1

- Total cases: 6
- Pass rate: 100.00%
- Average score: 0.948

## Aggregate Metrics
- request_type_match: 1.000
- retrieval_citation_recall: 1.000
- generation_citation_recall: 0.917
- source_type_recall: 1.000
- answer_term_coverage: 0.825
- disclaimer_presence: 1.000
- confidence_sufficiency: 1.000
- grounded_citation_precision: 0.903

## Case Results

### validity_the_chap_basic [PASS]
- Query: Hợp đồng thế chấp có hiệu lực khi nào theo Bộ luật Dân sự và Nghị định 21/2021/NĐ-CP?
- Score: 0.980
- request_type_match: 1.000
- retrieval_citation_recall: 1.000
- generation_citation_recall: 1.000
- source_type_recall: 1.000
- answer_term_coverage: 1.000
- disclaimer_presence: 1.000
- confidence_sufficiency: 1.000
- grounded_citation_precision: 0.750

### vo_hieu_gia_tao [PASS]
- Query: Căn cứ nào để xác định giao dịch dân sự vô hiệu do giả tạo theo Bộ luật Dân sự 2015?
- Score: 0.870
- request_type_match: 1.000
- retrieval_citation_recall: 1.000
- generation_citation_recall: 0.500
- source_type_recall: 1.000
- answer_term_coverage: 0.750
- disclaimer_presence: 1.000
- confidence_sufficiency: 1.000
- grounded_citation_precision: 1.000
- Notes:
  - Generation chưa trích dẫn đủ căn cứ kỳ vọng.
  - Nội dung trả lời chưa phủ hết thuật ngữ pháp lý hoặc kết luận kỳ vọng.

### scenario_an_le_43 [PASS]
- Query: Nếu bên mua nhà chưa thanh toán đủ tiền nhưng đã được cấp sổ rồi đem thế chấp ngân hàng thì hợp đồng thế chấp có bị vô hiệu không?
- Score: 0.967
- request_type_match: 1.000
- retrieval_citation_recall: 1.000
- generation_citation_recall: 1.000
- source_type_recall: 1.000
- answer_term_coverage: 1.000
- disclaimer_presence: 1.000
- confidence_sufficiency: 1.000
- grounded_citation_precision: 0.667

### doi_khang_nguoi_thu_ba [PASS]
- Query: Thế chấp tài sản phát sinh hiệu lực đối kháng với người thứ ba từ thời điểm nào?
- Score: 1.000
- request_type_match: 1.000
- retrieval_citation_recall: 1.000
- generation_citation_recall: 1.000
- source_type_recall: 1.000
- answer_term_coverage: 1.000
- disclaimer_presence: 1.000
- confidence_sufficiency: 1.000
- grounded_citation_precision: 1.000

### dieu_kien_hieu_luc_giao_dich [PASS]
- Query: Điều kiện có hiệu lực của giao dịch dân sự theo Bộ luật Dân sự 2015 là gì?
- Score: 0.872
- request_type_match: 1.000
- retrieval_citation_recall: 1.000
- generation_citation_recall: 1.000
- source_type_recall: 1.000
- answer_term_coverage: 0.200
- disclaimer_presence: 1.000
- confidence_sufficiency: 1.000
- grounded_citation_precision: 1.000
- Notes:
  - Nội dung trả lời chưa phủ hết thuật ngữ pháp lý hoặc kết luận kỳ vọng.

### hieu_luc_doi_khang_registration [PASS]
- Query: Đăng ký biện pháp bảo đảm có ý nghĩa gì đối với hiệu lực đối kháng của thế chấp?
- Score: 1.000
- request_type_match: 1.000
- retrieval_citation_recall: 1.000
- generation_citation_recall: 1.000
- source_type_recall: 1.000
- answer_term_coverage: 1.000
- disclaimer_presence: 1.000
- confidence_sufficiency: 1.000
- grounded_citation_precision: 1.000