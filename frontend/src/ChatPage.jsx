import { useState, useRef, useEffect } from 'react';
import ChatContainer from './components/ChatContainer';
import { sendChatQueryStream, createConversation, getConversationMessages } from './api';
import Sidebar from './components/Sidebar';

const DEFAULT_MESSAGE = {
  role: 'ai',
  content: 'Xin chào! Tôi là Trợ lý Pháp lý AI. Tôi có thể giúp bạn tra cứu các quy định, luật định và giải đáp các thắc mắc về pháp luật Việt Nam. Bạn cần tôi giúp gì hôm nay?'
};

function App() {
  const [messages, setMessages] = useState([DEFAULT_MESSAGE]);
  const [conversationId, setConversationId] = useState(localStorage.getItem('legal_assistant_conversation_id'));

  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isInputFocused, setIsInputFocused] = useState(false);
  const textareaRef = useRef(null);
  const justCreatedRef = useRef(false);

  useEffect(() => {
    const initChat = async () => {
      if (conversationId) {
        if (justCreatedRef.current) {
          justCreatedRef.current = false;
          return;
        }
        try {
          const msgs = await getConversationMessages(conversationId);
          if (msgs && msgs.length > 0) {
            setMessages(msgs);
          } else {
            setMessages([DEFAULT_MESSAGE]);
          }
        } catch (e) {
          console.error(e);
          // Fallback if conversation not found
          localStorage.removeItem('legal_assistant_conversation_id');
          setConversationId(null);
        }
      } else {
        setMessages([DEFAULT_MESSAGE]);
      }
    };
    initChat();
  }, [conversationId]);

  const handleInput = (e) => {
    setInputValue(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  };

  const handleSendMessage = async (e) => {
    e?.preventDefault();

    if (!inputValue.trim() || isLoading) return;

    let targetConversationId = conversationId;
    if (!targetConversationId) {
      try {
        const conv = await createConversation();
        targetConversationId = conv.id;
        justCreatedRef.current = true;
        setConversationId(conv.id);
        localStorage.setItem('legal_assistant_conversation_id', conv.id);
      } catch (e) {
        console.error("Failed to create conversation on send", e);
        return;
      }
    }

    const userQuery = inputValue.trim();
    setInputValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    // Add user message
    setMessages(prev => [...prev, { role: 'user', content: userQuery }]);
    setIsLoading(true);

    try {
      const tempMessageId = Date.now();
      setMessages(prev => [...prev, {
        id: tempMessageId,
        role: 'ai',
        isLoading: true,
        content: 'Khởi tạo...',
        query: userQuery
      }]);

      let latestCandidates = [];
      await sendChatQueryStream(userQuery, targetConversationId, (event) => {
        if (event.type === 'status') {
          setMessages(prev => prev.map(msg =>
            msg.id === tempMessageId ? { ...msg, content: event.content } : msg
          ));
        } else if (event.type === 'retrieval') {
          latestCandidates = event.data.candidates || [];
        } else if (event.type === 'answer') {
          setMessages(prev => prev.map(msg =>
            msg.id === tempMessageId ? { ...msg, role: 'ai', isLoading: false, data: { answer: event.data, retrieval: event.data.retrieval_debug ? { candidates: latestCandidates } : null } } : msg
          ));
        }
      });

    } catch (error) {
      let errorMessage = 'Xin lỗi, đã có lỗi xảy ra khi kết nối đến máy chủ. Vui lòng thử lại sau.';
      if (error.status === 429) {
        errorMessage = 'Bạn đã gửi quá nhiều yêu cầu trong thời gian ngắn. Vui lòng thử lại sau một lát.';
      } else if (error.status === 401) {
        errorMessage = 'Lỗi xác thực: Vui lòng kiểm tra lại API Key.';
      }

      setMessages(prev => [
        ...prev.filter(msg => !msg.isLoading), // remove temp message on error
        {
          role: 'ai',
          error: true,
          content: errorMessage
        }
      ]);
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="bg-surface font-body-md text-on-surface flex">
      <Sidebar 
        currentConversationId={conversationId} 
        onSelectConversation={setConversationId}
      />
      
      <div className="pl-sidebar-width flex flex-col min-h-screen w-full">
        <main className="flex-1 pt-16 bg-surface">
          <div className="flex flex-col w-full">
            <ChatContainer
              messages={messages}
              isLoading={isLoading}
            />
          </div>
        </main>

        <div className="fixed bottom-8 left-sidebar-width right-0 px-gutter z-30 pointer-events-none">
          <div className="max-w-2xl mx-auto pointer-events-auto">
            <div 
              className={`bg-surface-container-highest/90 backdrop-blur-2xl rounded-2xl p-2 shadow-floating border transition-all flex flex-col gap-2 ${isInputFocused ? 'ring-2' : ''}`}
              style={{
                borderColor: isInputFocused ? 'rgba(233, 193, 118, 0.5)' : 'rgba(68, 71, 77, 0.4)',
                '--tw-ring-color': 'rgba(233, 193, 118, 0.5)'
              }}
            >
              <form 
                onSubmit={handleSendMessage}
                className="flex items-end gap-2"
              >
                <div className="flex-1 px-3 py-2 flex items-center min-h-[40px]">
                  <textarea
                    ref={textareaRef}
                    className="input-textarea"
                    placeholder="Nhập câu hỏi pháp lý của bạn vào đây..."
                    value={inputValue}
                    onChange={handleInput}
                    onKeyDown={handleKeyDown}
                    onFocus={() => setIsInputFocused(true)}
                    onBlur={() => setIsInputFocused(false)}
                    rows={1}
                    disabled={isLoading}
                  />
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    type="submit"
                    className="bg-secondary text-on-secondary h-10 px-4 rounded-xl font-label-md flex items-center justify-center gap-2 hover:brightness-110 transition-all shadow-lg active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
                    disabled={!inputValue.trim() || isLoading}
                    aria-label="Gửi câu hỏi"
                  >
                    <span className="hidden md:inline">Gửi</span>
                    <span className="material-symbols-outlined text-sm">send</span>
                  </button>
                </div>
              </form>
              <div className="text-center pb-1 px-2">
                <span className="text-[9px] text-on-surface-variant uppercase tracking-widest opacity-60">
                  AI có thể mắc lỗi. Vui lòng kiểm tra lại các tài liệu trích dẫn để đảm bảo tính chính xác.
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
