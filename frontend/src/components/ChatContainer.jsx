import { useEffect, useRef } from 'react';
import MessageBubble from './MessageBubble';

const ChatContainer = ({ messages, isLoading }) => {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  return (
    <div className="flex-1 max-w-container-max-width mx-auto w-full px-gutter mt-4">
      <div className="flex flex-col gap-stack-lg">
        {messages.map((msg, index) => (
          <MessageBubble key={msg.id || index} message={msg} />
        ))}
      </div>

      {/* Spacer to push content above the fixed input bar when scrolled to bottom */}
      <div style={{ height: '160px' }} />
      <div ref={bottomRef} style={{ height: '1px' }} />
    </div>
  );
};

export default ChatContainer;
