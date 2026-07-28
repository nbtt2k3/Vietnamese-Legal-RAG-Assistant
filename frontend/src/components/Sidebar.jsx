import { useCallback, useEffect, useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import { getConversations, deleteConversation } from '../api';
import { useAuth } from '../contexts/useAuth';
import { useNavigate } from 'react-router-dom';

const Sidebar = ({ currentConversationId, onSelectConversation }) => {
  const [conversations, setConversations] = useState([]);
  const [deleteConfirmId, setDeleteConfirmId] = useState(null);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const hasMounted = useRef(false);

  const fetchConversations = useCallback(async () => {
    try {
      const data = await getConversations();
      setConversations(data);
      if (data.length > 0 && !currentConversationId && !hasMounted.current) {
        onSelectConversation(data[0].id);
      }
      hasMounted.current = true;
    } catch (e) {
      console.error(e);
    }
  }, [currentConversationId, onSelectConversation]);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  const handleNewChat = () => {
    onSelectConversation(null);
  };

  const confirmDelete = (id, e) => {
    e.stopPropagation();
    setDeleteConfirmId(id);
  };

  const executeDelete = async () => {
    if (!deleteConfirmId) return;
    const id = deleteConfirmId;
    setDeleteConfirmId(null);
    try {
      await deleteConversation(id);
      setConversations(conversations.filter(c => c.id !== id));
      if (currentConversationId === id) {
        onSelectConversation(null);
        fetchConversations();
      }
    } catch (error) {
      console.error(error);
    }
  };

  return (
    <aside className="fixed left-0 top-0 h-full w-sidebar-width glass-sidebar border-r border-outline-variant z-50 flex flex-col">
      <div className="p-stack-md flex items-center justify-center gap-4 mb-stack-md mt-4">
        <span className="material-symbols-outlined text-secondary" style={{ fontSize: '38px' }}>balance</span>
        <span className="font-bold text-primary tracking-tight" style={{ fontSize: '28px' }}>Lexora</span>
      </div>

      <div className="px-3 mb-stack-md">
        <button
          onClick={handleNewChat}
          className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-secondary text-on-secondary rounded-xl font-label-md hover:brightness-110 transition-all shadow-lg"
        >
          <span className="material-symbols-outlined">add</span>Cuộc hội thoại mới
        </button>
      </div>

      <nav className="flex-1 px-3 overflow-y-auto relative">
        <div className="px-3 py-2 text-on-surface-variant/70 text-[11px] font-bold uppercase tracking-wider mb-1">
          Gần đây
        </div>

        {conversations.length === 0 ? (
          <div className="px-4 py-3 text-sm text-on-surface-variant/50 italic">
            Chưa có lịch sử hội thoại
          </div>
        ) : (
          conversations.map(conv => {
            const isActive = currentConversationId === conv.id;
            const titleText = (conv.title && conv.title !== 'New Conversation')
              ? conv.title
              : 'Lịch sử truy vấn';

            return (
              <div
                key={conv.id}
                onClick={() => onSelectConversation(conv.id)}
                className={`group flex items-center px-3 py-3 rounded-xl cursor-pointer mb-1.5 transition-all ${isActive
                  ? 'bg-surface-container-high text-on-surface font-semibold shadow-sm border-l-4 border-secondary'
                  : 'text-on-surface-variant hover:bg-surface-container-high/50 hover:text-on-surface'
                  }`}
              >
                <span className={`material-symbols-outlined mr-3 text-lg shrink-0 ${isActive ? 'text-on-surface' : 'text-on-surface-variant group-hover:text-on-surface'}`}>
                  history
                </span>
                <span className="flex-1 truncate text-sm">
                  {titleText}
                </span>
                <button
                  onClick={(e) => confirmDelete(conv.id, e)}
                  className="p-1.5 rounded-lg transition-all ml-1 shrink-0 flex items-center justify-center"
                  style={{ color: '#8f9097', backgroundColor: 'transparent' }}
                  onMouseOver={(e) => {
                    e.currentTarget.style.color = '#ffb4ab';
                    e.currentTarget.style.backgroundColor = 'rgba(255, 180, 171, 0.2)';
                  }}
                  onMouseOut={(e) => {
                    e.currentTarget.style.color = '#8f9097';
                    e.currentTarget.style.backgroundColor = 'transparent';
                  }}
                  title="Xóa cuộc hội thoại"
                >
                  <span className="material-symbols-outlined text-base">delete</span>
                </button>
              </div>
            );
          })
        )}
      </nav>

      {/* Custom Delete Confirmation Modal */}
      {/* Custom Delete Confirmation Modal */}
      {deleteConfirmId && createPortal(
        <div className="fixed flex items-center justify-center p-6" style={{ top: 0, left: 0, right: 0, bottom: 0, zIndex: 100 }}>
          {/* Backdrop */}
          <div
            className="absolute backdrop-blur-sm"
            style={{ top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(3, 13, 37, 0.8)' }}
            onClick={() => setDeleteConfirmId(null)}
          ></div>

          {/* Modal Container */}
          <div
            className="relative w-full"
            style={{
              maxWidth: '448px',
              backgroundColor: '#1f2942',
              borderRadius: '16px',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
              border: '1px solid rgba(68, 71, 77, 0.3)',
              padding: '32px'
            }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex flex-col items-center text-center">
              {/* Warning Icon */}
              <div
                className="rounded-full flex items-center justify-center"
                style={{ width: '64px', height: '64px', backgroundColor: 'rgba(147, 0, 10, 0.2)', marginBottom: '16px' }}
              >
                <span className="material-symbols-outlined text-3xl" style={{ color: '#ffb4ab' }}>delete_forever</span>
              </div>

              {/* Content */}
              <h3 style={{ fontSize: '20px', fontWeight: '600', lineHeight: '28px', color: '#d9e2ff', marginBottom: '8px', fontFamily: '"Be Vietnam Pro", sans-serif' }}>
                Xóa hội thoại?
              </h3>
              <p style={{ fontSize: '16px', fontWeight: '400', lineHeight: '26px', color: '#c5c6cd', marginBottom: '32px', fontFamily: '"Be Vietnam Pro", sans-serif' }}>
                Bạn sắp xóa vĩnh viễn đoạn hội thoại này. Dữ liệu sẽ không thể khôi phục lại được. Bạn có chắc chắn không?
              </p>

              {/* Actions */}
              <div className="flex flex-row w-full" style={{ gap: '12px' }}>
                <button
                  onClick={() => setDeleteConfirmId(null)}
                  className="flex-1 transition-colors"
                  style={{
                    padding: '12px 16px',
                    borderRadius: '12px',
                    backgroundColor: 'rgba(42, 52, 77, 0.3)',
                    color: '#c5c6cd',
                    fontSize: '14px',
                    fontWeight: '600',
                    lineHeight: '20px',
                    letterSpacing: '0.05em',
                    fontFamily: 'Inter, sans-serif'
                  }}
                  onMouseOver={(e) => e.currentTarget.style.backgroundColor = 'rgba(42, 52, 77, 0.8)'}
                  onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'rgba(42, 52, 77, 0.3)'}
                >
                  Hủy bỏ
                </button>
                <button
                  onClick={executeDelete}
                  className="flex-1 flex items-center justify-center gap-2 hover:brightness-110 active:scale-95 transition-all shadow-lg"
                  style={{
                    padding: '12px 16px',
                    borderRadius: '12px',
                    backgroundColor: '#ffb4ab',
                    color: '#690005',
                    fontSize: '14px',
                    fontWeight: '600',
                    lineHeight: '20px',
                    letterSpacing: '0.05em',
                    fontFamily: 'Inter, sans-serif'
                  }}
                >
                  Xóa ngay
                </button>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}

      <div className="mt-auto p-4 border-t border-outline-variant/30 flex flex-col gap-3">
        {/* Profile Card */}
        <div
          className="flex items-center gap-3 p-3 rounded-2xl"
          style={{ backgroundColor: '#2B2D3C' }}
        >
          <div
            className="w-10 h-10 flex-shrink-0 rounded-full border border-secondary/30 flex items-center justify-center font-bold text-lg"
            style={{ backgroundColor: 'rgba(197, 160, 89, 0.1)', color: '#C5A059' }}
          >
            {(user?.username || 'Luật sư Minh').charAt(0).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-body-sm font-bold text-white truncate">
              {user?.username || 'Luật sư Minh'}
            </div>
          </div>
        </div>

        {/* Logout Button */}
        <button
          onClick={() => {
            logout();
            navigate('/login');
          }}
          className="w-full flex items-center justify-center gap-2 py-3 rounded-xl hover:brightness-110 text-on-surface-variant hover:text-white transition-all"
          style={{ backgroundColor: '#1D1F2A' }}
          title="Đăng xuất"
        >
          <span className="material-symbols-outlined text-[20px]">logout</span>
          <span className="font-label-md">Đăng xuất</span>
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
