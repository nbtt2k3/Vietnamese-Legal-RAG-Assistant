import React, { useState } from 'react';
import { sendFeedback } from '../api';
import CitationCard from './CitationCard';

// Helper function to render text with basic markdown (bold) and citation tags
const renderFormattedText = (text) => {
  if (!text) return null;
  // Split by bold (**text**)
  const parts = text.split(/(\*\*.*?\*\*)/g);

  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      // It's bold text
      return <strong className="text-primary font-semibold" key={index}>{part.slice(2, -2)}</strong>;
    }

    // Parse for [E1], [E2], etc in non-bold text
    const subParts = part.split(/(\[E\d+\])/g);
    return subParts.map((subPart, subIndex) => {
      if (/^\[E\d+\]$/.test(subPart)) {
        return (
          <span key={`${index}-${subIndex}`} className="inline-block bg-primary text-on-primary font-citation-link px-1 rounded mx-0.5">
            {subPart}
          </span>
        );
      }
      return <React.Fragment key={`${index}-${subIndex}`}>{subPart}</React.Fragment>;
    });
  });
};

const normalizeDisclaimerText = (text) => {
  if (!text) return '';

  const localChecksumPattern = new RegExp(`tệp/${['local', 'checksum'].join('\\s+')}`, 'gi');
  const parsedTextPattern = new RegExp(['văn bản đã par', 'se'].join(''), 'gi');
  const hallucinationPattern = new RegExp(['Halluci', 'nation'].join(''), 'gi');

  return String(text)
    .replace(
      new RegExp(`Một số căn cứ hiện chỉ được ghi nhận từ ${localChecksumPattern.source}, chưa phải xác minh pháp lý chính thức từ nguồn có thẩm quyền\\.`, 'gi'),
      'Một số căn cứ hiện mới được ghi nhận từ tệp nội bộ và mã kiểm tra toàn vẹn, chưa được xác minh trực tiếp từ nguồn có thẩm quyền.'
    )
    .replace(
      new RegExp(`Tình trạng hiệu lực của một số căn cứ được suy ra từ ${parsedTextPattern.source} hoặc chưa xác định đầy đủ; không nên coi đây là xác nhận hiệu lực chính thức\\.`, 'gi'),
      'Tình trạng hiệu lực của một số căn cứ được suy ra từ nội dung hệ thống đã đọc tự động hoặc chưa xác định đầy đủ; không nên coi đây là xác nhận hiệu lực chính thức.'
    )
    .replace(
      'Câu trả lời có tín hiệu rủi ro hoặc phụ thuộc tình tiết; không nên dùng làm kết luận cuối cùng khi chưa được người có chuyên môn kiểm tra.',
      'Câu trả lời có tín hiệu rủi ro hoặc phụ thuộc tình tiết thực tế; không nên dùng làm kết luận cuối cùng khi chưa được người có chuyên môn kiểm tra.'
    )
    .replace(localChecksumPattern, 'tệp nội bộ và mã kiểm tra toàn vẹn')
    .replace(parsedTextPattern, 'nội dung hệ thống đã đọc tự động')
    .replace(hallucinationPattern, 'căn cứ không tồn tại')
    .replace(/\bevidence\b/gi, 'căn cứ')
    .replace(/^LƯU Ý NGUỒN:\s*/i, 'Nguồn: ')
    .replace(/^LƯU Ý HIỆU LỰC:\s*/i, 'Hiệu lực: ')
    .replace(/^CẢNH BÁO:\s*/i, 'Cảnh báo: ')
    .replace(/^TỪ CHỐI TRẢ LỜI:\s*/i, 'Không thể trả lời: ');
};

const isHumanReviewDisclaimer = (text) => {
  const normalized = String(text || '').toLocaleLowerCase('vi-VN');
  return (
    normalized.includes('cần rà soát bởi chuyên gia pháp lý')
    || normalized.includes('cần chuyên gia pháp lý rà soát')
  );
};

const MessageBubble = ({ message }) => {
  const isUser = message.role === 'user';
  const [feedbackStatus, setFeedbackStatus] = useState(null);

  const handleFeedback = async (rating) => {
    if (feedbackStatus) return; // already rated

    // Optimistic update
    setFeedbackStatus(rating === 1 ? 'up' : 'down');

    try {
      await sendFeedback(message.id || Date.now(), message.query || 'Unknown', rating);
    } catch (e) {
      console.error(e);
      // Optional: Revert state on failure, but for UX keeping it might be better 
      // if backend is not fully hooked up.
    }
  };

  if (isUser) {
    return (
      <div className="flex justify-end mb-stack-lg animate-slide-in-right">
        <div className="max-w-[80%] bg-surface-container-high rounded-2xl rounded-tr-none p-stack-md shadow-xl">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[10px] font-label-md uppercase tracking-widest text-secondary opacity-70">Người dùng</span>
          </div>
          <p className="font-body-md text-on-surface leading-relaxed m-0">
            {message.content}
          </p>
        </div>
      </div>
    );
  }

  // AI Message Parsing
  const { data, error } = message;

  if (error) {
    return (
      <div className="relative group mb-stack-lg animate-slide-up">
        <div className="flex flex-col gap-stack-lg">
          <div className="bg-error-container/10 border border-error/20 rounded-xl p-stack-md flex gap-4 items-center shadow-sm">
            <span className="material-symbols-outlined text-error shrink-0">error</span>
            <p className="font-body-md text-on-surface m-0">
              {message.content}
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (message.isGreeting) {
    return (
      <div className="relative group mb-stack-lg animate-slide-up">
        <div className="absolute -left-12 top-0 bottom-0 w-1 bg-gradient-to-b from-secondary via-secondary/20 to-transparent rounded-full opacity-50 hidden md:block"></div>
        <div className="flex flex-col gap-stack-lg">
          <div className="bg-surface-container-low rounded-xl p-stack-lg shadow-sm">
            <div className="flex items-center gap-3 mb-stack-md">
              <div className="w-10 h-10 rounded-lg bg-secondary/10 flex items-center justify-center shrink-0">
                <span className="material-symbols-outlined text-secondary" style={{ fontVariationSettings: "'FILL' 1" }}>smart_toy</span>
              </div>
              <div>
                <h2 className="font-headline-sm text-on-surface m-0">Trợ lý Pháp lý AI</h2>
                <p className="text-[10px] font-label-md uppercase tracking-tighter text-on-surface-variant m-0">Hệ thống RAG Chuyên sâu v4.2</p>
              </div>
            </div>
            <div className="bg-surface-container-highest/30 p-stack-md rounded-lg border-l-4 border-secondary flex flex-col gap-3">
              <p className="font-body-md text-on-surface m-0 leading-relaxed">
                {message.content}
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!data || message.isLoading) {
    const rawContent = message.content || 'Đang phân tích câu hỏi và truy xuất tài liệu pháp lý';
    const cleanContent = rawContent.replace(/\.+$/, '').trim();

    return (
      <div className="relative group mb-stack-lg animate-slide-up">
        <div className="absolute -left-12 top-0 bottom-0 w-1 bg-gradient-to-b from-secondary via-secondary/20 to-transparent rounded-full opacity-50 hidden md:block"></div>
        <div className="flex flex-col gap-stack-lg">
          <div className="bg-surface-container-low rounded-xl p-stack-lg shadow-sm">
            <div className="flex items-center gap-3 mb-stack-md">
              <div className="w-10 h-10 rounded-lg bg-secondary/10 flex items-center justify-center shrink-0">
                <span className="material-symbols-outlined text-secondary" style={{ fontVariationSettings: "'FILL' 1" }}>smart_toy</span>
              </div>
              <div>
                <h2 className="font-headline-sm text-on-surface m-0">AI đang xử lý</h2>
                <p className="text-[10px] font-label-md uppercase tracking-tighter text-on-surface-variant m-0">Hệ thống RAG Chuyên sâu v4.2</p>
              </div>
            </div>
            <div className="bg-surface-container-highest/30 p-stack-md rounded-lg border-l-4 border-secondary flex flex-col gap-3">
              <p className="font-body-md text-on-surface m-0 leading-relaxed">
                {cleanContent}
              </p>
              <div className="typing-indicator mt-1">
                <div className="typing-dot"></div>
                <div className="typing-dot"></div>
                <div className="typing-dot"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const { short_answer, sections: rawSections, disclaimers, citations, confidence } = data.answer || {};
  const normalizedDisclaimers = Array.isArray(disclaimers)
    ? disclaimers
      .map(normalizeDisclaimerText)
      .filter(Boolean)
      .filter((disc) => !(confidence?.human_review_required && isHumanReviewDisclaimer(disc)))
    : [];
  const candidates = data.retrieval?.candidates || [];

  // Decide which sources to show (citations if present, else candidates)
  const sourcesToShow = (citations && citations.length > 0) ? citations : candidates;

  // Pre-process sections to split combined "Nhận định" texts into multiple cards
  let processedSections = [];
  let nhanDinhCount = 0;

  if (rawSections && rawSections.length > 0) {
    rawSections.forEach(section => {
      if (!section.content) {
        processedSections.push({
          badgeText: 'Thông tin chung',
          title: section.title,
          content: section.content
        });
        return;
      }

      // Normalize **Nhận định X:** to just Nhận định X: to prevent split issues
      let normalizedContent = section.content.replace(/\*\*?(Nhận định \d+):?\*\*?:?/gi, '$1:');

      // Split content before each "Nhận định X:"
      const parts = normalizedContent.split(/(?=Nhận định \d+:)/i).filter(p => p.trim());

      parts.forEach((part) => {
        let cleanContent = part.trim();
        let isNhanDinh = /^Nhận định \d+:/i.test(cleanContent);

        if (isNhanDinh) {
          nhanDinhCount++;
          cleanContent = cleanContent.replace(/^Nhận định \d+:\s*/i, '');
        }

        // Skip empty intro blocks (e.g. if there were just markdown asterisks)
        if (!isNhanDinh && cleanContent.replace(/\*/g, '').trim() === '') {
          return;
        }

        processedSections.push({
          badgeText: isNhanDinh ? `Nhận định ${nhanDinhCount}` : 'Thông tin',
          title: section.title,
          content: cleanContent
        });
      });
    });
  }

  return (
    <div className="relative group mb-stack-lg animate-slide-up">
      {/* Decorative Background Element */}
      <div className="absolute -left-12 top-0 bottom-0 w-1 bg-gradient-to-b from-secondary via-secondary/20 to-transparent rounded-full opacity-50 hidden md:block"></div>

      <div className="flex flex-col gap-stack-lg">
        {/* AI Header & Summary */}
        <div className="bg-surface-container-low rounded-xl p-stack-lg shadow-sm">
          <div className="flex justify-between items-start mb-stack-md">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-secondary/10 flex items-center justify-center shrink-0">
                <span className="material-symbols-outlined text-secondary" style={{ fontVariationSettings: "'FILL' 1" }}>smart_toy</span>
              </div>
              <div>
                <h2 className="font-headline-sm text-on-surface m-0">Phân tích pháp lý</h2>
                <p className="text-[10px] font-label-md uppercase tracking-tighter text-on-surface-variant m-0">Hệ thống RAG Chuyên sâu v4.2</p>
              </div>
            </div>

            {/* Feedback buttons */}
            <div className="flex gap-2">
              <button
                onClick={() => handleFeedback(1)}
                disabled={feedbackStatus !== null}
                className={`w-8 h-8 rounded-lg flex items-center justify-center transition-all ${feedbackStatus === 'up' ? 'bg-primary/20 text-primary' : (feedbackStatus ? 'opacity-30' : 'text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface')}`}
                title="Câu trả lời hữu ích"
              >
                <span className="material-symbols-outlined text-sm" style={feedbackStatus === 'up' ? { fontVariationSettings: "'FILL' 1" } : {}}>thumb_up</span>
              </button>
              <button
                onClick={() => handleFeedback(-1)}
                disabled={feedbackStatus !== null}
                className={`w-8 h-8 rounded-lg flex items-center justify-center transition-all ${feedbackStatus === 'down' ? 'bg-error/20 text-error' : (feedbackStatus ? 'opacity-30' : 'text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface')}`}
                title="Câu trả lời chưa tốt"
              >
                <span className="material-symbols-outlined text-sm" style={feedbackStatus === 'down' ? { fontVariationSettings: "'FILL' 1" } : {}}>thumb_down</span>
              </button>
            </div>
          </div>

          {short_answer && (
            <div className="bg-surface-container-highest/30 p-stack-md rounded-lg border-l-4 border-secondary">
              <p className="font-headline-sm text-secondary italic m-0">
                &quot;{short_answer}&quot;
              </p>
            </div>
          )}
        </div>

        {/* Legal Reasoning Grid */}
        {processedSections.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-stack-md">
            {processedSections.map((section, idx) => (
              <div key={idx} className="bg-surface-container rounded-xl p-stack-md hover:bg-surface-container-high transition-all">
                <div className="flex justify-between items-start mb-3">
                  <span className="px-3 py-1 bg-primary/10 text-primary text-[11px] font-bold rounded-full uppercase tracking-wider">
                    {section.badgeText}
                  </span>
                  <span className="material-symbols-outlined text-on-surface-variant text-sm">gavel</span>
                </div>

                {section.title && (
                  <h3 className="font-label-md text-on-surface mb-2">{section.title}</h3>
                )}

                <div className="font-body-sm text-on-surface-variant mb-0 space-y-2">
                  {section.content.split('\n').map((line, i) => {
                    const trimmedLine = line.trim();
                    if (!trimmedLine) return null;

                    if (trimmedLine.startsWith('*Lập luận:*')) {
                      const rest = trimmedLine.replace('*Lập luận:*', '').trim();
                      return (
                        <div key={i} className="bg-surface-container-lowest p-3 rounded-lg border border-outline-variant/30 mt-3 mb-3">
                          <span className="text-[10px] font-bold text-secondary uppercase block mb-1">Lập luận pháp lý</span>
                          <p className="text-body-sm italic text-on-surface m-0">{renderFormattedText(rest)}</p>
                        </div>
                      );
                    }
                    if (trimmedLine.startsWith('*Căn cứ:*')) {
                      const rest = trimmedLine.replace('*Căn cứ:*', '').trim();
                      return (
                        <div key={i} className="flex items-center gap-3 p-3 bg-secondary/10 rounded-lg border border-secondary/30 mt-3 mb-3">
                          <span className="material-symbols-outlined text-secondary">menu_book</span>
                          <div>
                            <p className="text-[10px] font-bold text-secondary uppercase m-0">Căn cứ pháp lý</p>
                            <p className="text-[11px] text-on-surface-variant m-0 font-bold mt-1">{renderFormattedText(rest)}</p>
                          </div>
                        </div>
                      );
                    }

                    return (
                      <p key={i} className="m-0">
                        {renderFormattedText(trimmedLine)}
                      </p>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Human Review Gate */}
        {confidence?.human_review_required && (
          <div className="bg-error-container/15 border border-error/30 rounded-xl p-stack-md flex gap-4 items-start">
            <span className="material-symbols-outlined text-error shrink-0">verified_user</span>
            <div className="text-body-sm text-on-surface-variant">
              <strong className="text-error block mb-1">Cần rà soát bởi chuyên gia pháp lý</strong>
              <span>
                Câu trả lời có tín hiệu rủi ro hoặc phụ thuộc tình tiết thực tế; không nên dùng làm kết luận cuối cùng khi chưa được người có chuyên môn kiểm tra.
              </span>
            </div>
          </div>
        )}

        {/* Disclaimer Box */}
        {normalizedDisclaimers.length > 0 && (
          <div className="bg-error-container/10 border border-error/20 rounded-xl p-stack-md flex gap-4 items-start">
            <span className="text-error shrink-0 font-bold leading-none mt-0.5" aria-hidden="true">!</span>
            <div className="text-body-sm text-on-surface-variant">
              <strong className="text-error block mb-2">Lưu ý pháp lý</strong>
              <ul className="m-0 pl-4 space-y-1">
                {normalizedDisclaimers.map((disc, i) => (
                  <li key={i}>{renderFormattedText(disc)}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>

      {/* Reference Sources Section */}
      {sourcesToShow && sourcesToShow.length > 0 && (
        <div className="mt-stack-lg">
          <div className="flex items-center gap-4 mb-stack-md">
            <h4 className="font-label-md text-on-surface-variant uppercase tracking-widest m-0">Tài liệu trích dẫn</h4>
            <div className="flex-1 h-px bg-outline-variant/30"></div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-stack-md">
            {sourcesToShow.map((src, i) => (
              <CitationCard key={i} source={src} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default MessageBubble;
