import { Menu } from 'lucide-react';

interface HeaderProps {
  onToggleSidebar: () => void;
}

function Header({ onToggleSidebar }: HeaderProps) {
  return (
    <header className="bg-white border-b border-gray-200 flex-shrink-0">
      <div className="flex items-center px-4 py-3 gap-3">
        <button
          onClick={onToggleSidebar}
          className="p-1 rounded hover:bg-gray-100 transition-colors text-gray-700"
          aria-label="Toggle sidebar"
        >
          <Menu size={24} />
        </button>
        <span className="text-gray-800 text-lg font-semibold">
          Bw-I Chatbot
        </span>
      </div>
    </header>
  );
}

export default Header;
