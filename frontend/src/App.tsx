import { useState, useRef, useEffect } from 'react';
import {
  AssistantRuntimeProvider,
  useExternalStoreRuntime,
  type AppendMessage,
} from '@assistant-ui/react';
import type { Conversation, Message } from './types';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import Thread from './components/Thread';
import { getStatus } from './api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

function ChatApp() {
  const [status, setStatus] = useState<string>('Verbinde...');
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Use a ref to always have access to the latest conversationId in async handlers
  const currentConversationIdRef = useRef<string | null>(null);
  currentConversationIdRef.current = currentConversationId;

  useEffect(() => {
    getStatus().then(setStatus);
    startNewConversation();
  }, []);

  const currentMessages = currentConversationId
    ? (conversations.find(c => c.id === currentConversationId)?.messages ?? [])
    : [];

  const startNewConversation = () => {
    const newId = Date.now().toString();
    const newConversation: Conversation = {
      id: newId,
      title: 'Neue Konversation',
      messages: [],
      createdAt: new Date(),
    };
    setConversations(prev => [newConversation, ...prev]);
    setCurrentConversationId(newId);
  };

  const deleteConversation = (id: string) => {
    setConversations(prev => prev.filter(c => c.id !== id));
    if (currentConversationId === id) {
      const remaining = conversations.filter(c => c.id !== id);
      setCurrentConversationId(remaining[0]?.id ?? null);
    }
  };

  const handleNew = async (message: AppendMessage) => {
    const conversationId = currentConversationIdRef.current;
    if (!conversationId) return;

    const text = message.content
      .filter((p): p is { type: 'text'; text: string } => p.type === 'text')
      .map(p => p.text)
      .join('\n');

    if (!text.trim()) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      text,
      sender: 'user',
      timestamp: new Date(),
    };

    setConversations(prev =>
      prev.map(c =>
        c.id === conversationId
          ? {
              ...c,
              messages: [...c.messages, userMsg],
              title: c.messages.length === 0 ? text.substring(0, 30) + '...' : c.title,
            }
          : c
      )
    );

    setIsRunning(true);
    try {
      if (abortControllerRef.current) abortControllerRef.current.abort();
      abortControllerRef.current = new AbortController();

      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
        signal: abortControllerRef.current.signal,
      });

      const reader = response.body?.getReader();
      if (!reader) throw new Error('Response body not readable');

      const decoder = new TextDecoder();
      const assistantMsgId = (Date.now() + 1).toString();

      setConversations(prev =>
        prev.map(c =>
          c.id === conversationId
            ? {
                ...c,
                messages: [
                  ...c.messages,
                  { id: assistantMsgId, text: '', sender: 'assistant' as const, timestamp: new Date() },
                ],
              }
            : c
        )
      );

      let accumulated = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        accumulated += decoder.decode(value, { stream: true });
        const snapshot = accumulated;
        setConversations(prev =>
          prev.map(c =>
            c.id === conversationId
              ? {
                  ...c,
                  messages: c.messages.map(m =>
                    m.id === assistantMsgId ? { ...m, text: snapshot } : m
                  ),
                }
              : c
          )
        );
      }
    } catch (error: unknown) {
      if (error instanceof Error && error.name !== 'AbortError') {
        console.error('Chat error:', error);
      }
    } finally {
      abortControllerRef.current = null;
      setIsRunning(false);
    }
  };

  const handleCancel = async () => {
    abortControllerRef.current?.abort();
  };

  const runtime = useExternalStoreRuntime<Message>({
    messages: currentMessages,
    isRunning,
    convertMessage: (msg: Message) => ({
      role: msg.sender === 'user' ? ('user' as const) : ('assistant' as const),
      content: [{ type: 'text' as const, text: msg.text }],
      id: msg.id,
      createdAt: msg.timestamp,
    }),
    onNew: handleNew,
    onCancel: handleCancel,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="flex h-screen overflow-hidden">
        {sidebarOpen && (
          <Sidebar
            conversations={conversations}
            currentConversationId={currentConversationId}
            startNewConversation={startNewConversation}
            selectConversation={setCurrentConversationId}
            deleteConversation={deleteConversation}
            status={status}
          />
        )}
        <div className="flex flex-col flex-1 min-w-0">
          <Header onToggleSidebar={() => setSidebarOpen(prev => !prev)} />
          <div className="flex-1 min-h-0">
            <Thread />
          </div>
        </div>
      </div>
    </AssistantRuntimeProvider>
  );
}

export default ChatApp;
