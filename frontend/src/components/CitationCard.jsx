const RELEVANCE_TEXT = {
  high: 'Cao',
  medium: 'Trung bình',
  low: 'Thấp',
};

const fallbackRelevanceText = (rawScore) => {
  if (rawScore > 5) return 'Cao';
  if (rawScore >= 2) return 'Trung bình';
  return 'Thấp';
};

const getSourceTagStyle = (sourceType) => {
  const type = sourceType.toLowerCase();
  if (type.includes('luật') || type.includes('luat')) {
    return 'bg-secondary/20 text-secondary';
  } else if (type.includes('nghị định') || type.includes('nghi_dinh')) {
    return 'bg-tertiary/20 text-tertiary';
  } else {
    return 'bg-outline/20 text-on-surface-variant';
  }
};

const formatSourceType = (sourceType) => {
  const mapping = {
    'bo_luat': 'Bộ Luật',
    'luat': 'Luật',
    'nghi_dinh': 'Nghị Định',
    'thong_tu': 'Thông Tư',
    'hien_phap': 'Hiến Pháp',
    'nghi_quyet': 'Nghị Quyết',
    'quyet_dinh': 'Quyết Định',
    'chi_thi': 'Chỉ Thị',
    'an_le': 'Án Lệ',
    'cong_van': 'Công Văn'
  };
  const key = sourceType.toLowerCase().trim();
  return mapping[key] || sourceType;
};

const formatLegalRole = (role) => {
  const mapping = {
    'rule': 'Quy tắc chung',
    'condition_exception': 'Điều kiện / Ngoại lệ',
    'definition': 'Định nghĩa',
    'punishment': 'Chế tài',
    'procedure': 'Thủ tục',
    'principle': 'Nguyên tắc',
    'rights_obligations': 'Quyền và Nghĩa vụ',
    'responsibility': 'Trách nhiệm',
    'scope': 'Phạm vi điều chỉnh',
    'legal_effect': 'Hiệu lực pháp lý',
    'appendix_form': 'Phụ lục / Biểu mẫu',
    'case_issue': 'Vấn đề pháp lý',
    'case_holding': 'Phán quyết',
    'case_reasoning': 'Lập luận pháp lý',
    'case_facts': 'Tình tiết sự kiện'
  };
  const key = role.toLowerCase().trim();
  return mapping[key] || role;
};

const CitationCard = ({ source }) => {
  const rawScore = source.relevance_score !== undefined ? source.relevance_score : (source.scores?.final || 0);
  const relevanceLabel = source.relevance_label || source.relevanceLabel;
  const relevanceText = RELEVANCE_TEXT[relevanceLabel] || fallbackRelevanceText(rawScore);

  // Extract fields whether they are flat (CitationRecord) or nested in metadata (RetrievedChunk)
  const citationTitle = source.citation || source.metadata?.citation || source.chunk_id || 'Nguồn không xác định';
  const snippet = source.snippet || source.text;
  const sourceType = source.source_type || source.metadata?.loai_van_ban || 'Văn bản';
  const evidenceId = source.evidence_id;
  const legalRole = source.legal_role || source.metadata?.legal_role;

  const tagStyle = getSourceTagStyle(sourceType);
  const formattedSourceType = formatSourceType(sourceType);

  return (
    <div className="group bg-surface-container-low p-4 rounded-xl hover:bg-surface-container-high transition-all cursor-pointer">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          {evidenceId && (
            <span className="bg-secondary text-on-secondary text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider">
              [{evidenceId}]
            </span>
          )}
          <span className={`${tagStyle} text-[9px] font-bold px-2 py-0.5 rounded uppercase tracking-wider`}>
            {formattedSourceType}
          </span>
        </div>

        {(relevanceLabel || rawScore > 0) && (
          <span className="text-[9px] text-on-surface-variant uppercase opacity-70">
            Mức độ: {relevanceText}
          </span>
        )}
      </div>

      <h5 className="text-label-md text-on-surface mb-1 line-clamp-2" title={citationTitle}>
        {citationTitle}
      </h5>

      {legalRole && (
        <div className="flex items-center gap-1 mb-2 text-primary opacity-80">
          <span className="material-symbols-outlined text-[12px]">info</span>
          <span className="text-[10px] font-semibold uppercase">{formatLegalRole(legalRole)}</span>
        </div>
      )}

      {snippet && (
        <p className="text-[11px] text-on-surface-variant m-0 line-clamp-3 italic">
          &quot;{snippet}&quot;
        </p>
      )}
    </div>
  );
};

export default CitationCard;
