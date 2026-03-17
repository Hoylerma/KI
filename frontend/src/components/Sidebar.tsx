import { Plus, Trash2, MessageSquare, LogOut } from 'lucide-react';
import type { Conversation } from '../types';
import FileUpload from './FileUpload';

interface SidebarProps {
  conversations: Conversation[];
  currentConversationId: string | null;
  startNewConversation: () => void;
  selectConversation: (id: string) => void;
  deleteConversation: (id: string) => void;
  status: string;
}

function Sidebar({
  conversations,
  currentConversationId,
  startNewConversation,
  selectConversation,
  deleteConversation,
  status,
}: SidebarProps) {

  // Die neue Logout-Funktion
  const handleLogout = () => {
    localStorage.removeItem('access_token'); // Token aus dem Browser löschen
    window.location.reload(); // Seite neu laden, um den Türsteher (Login) zu triggern
  };

  return (
    <aside className="w-[260px] flex-shrink-0 flex flex-col h-full bg-[#171717] text-[#f6f6f6] overflow-hidden">
      <div className="p-3">
        <button
          onClick={startNewConversation}
          className="w-full flex items-center justify-center gap-2 bg-[#ffe000] text-black px-3 py-2 rounded font-medium text-sm hover:brightness-95 transition-all"
        >
          <Plus size={18} />
          Neuer Chat
        </button>
      </div>

      <div className="border-t border-[#4a4a4a] mx-3" />

      {/* RAG Dokumente Upload */}
      <FileUpload />

      <div className="border-t border-[#4a4a4a] mx-3 my-1" />

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto px-2 py-1">
        <p className="text-xs text-[#a8a8a8] px-2 mb-2">Konversationen</p>
        <ul className="space-y-1">
          {conversations.map(conv => (
            <li key={conv.id} className="group relative">
              <button
                onClick={() => selectConversation(conv.id)}
                className={[
                  'w-full flex items-center gap-2 px-2 py-2 rounded text-sm text-left pr-8',
                  currentConversationId === conv.id
                    ? 'bg-[#ffe000]/20 text-white'
                    : 'hover:bg-white/10 text-[#f6f6f6]',
                ].join(' ')}
              >
                <MessageSquare size={14} className="flex-shrink-0" />
                <span className="truncate">{conv.title}</span>
              </button>
              <button
                onClick={() => deleteConversation(conv.id)}
                className="absolute right-1 top-1/2 -translate-y-1/2 p-1 rounded opacity-0 group-hover:opacity-60 hover:!opacity-100 transition-opacity text-white"
                aria-label="Konversation löschen"
              >
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="border-t border-white/10 mx-3" />

      {/* Neuer Bereich unten: Abmelden & Status */}
      <div className="p-3 flex flex-col gap-3">
        <button
          onClick={handleLogout}
          className="w-full flex items-center justify-center gap-2 bg-red-500/10 text-red-400 hover:bg-red-500/20 hover:text-red-300 border border-transparent hover:border-red-500/30 px-3 py-2 rounded font-medium text-sm transition-all"
        >
          <LogOut size={16} />
          Abmelden
        </button>
        <p className="text-xs text-[#a8a8a8] text-center">Status: {status}</p>
      </div>
    </aside>
  );
}

export default Sidebar;