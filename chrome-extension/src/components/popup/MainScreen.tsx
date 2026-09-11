import React from 'react';
import type { User } from '../../types';

interface MainScreenProps {
  user: User;
  onLogout: () => void;
  onScrape: () => void;
  statusMessage: { message: string; type: 'info' | 'success' | 'error' } | null;
}

/** Signed in view: pulls in the current page and shows the result status. */
const MainScreen: React.FC<MainScreenProps> = ({ user, onLogout, onScrape, statusMessage }) => {
  const statusClasses = {
    success: 'bg-green-500/20 border border-green-500/50 text-green-200',
    error: 'bg-red-500/20 border border-red-500/50 text-red-200',
    info: 'bg-blue-500/20 border border-blue-500/50 text-blue-200',
  };

  const handleSettingsClick = (e: React.MouseEvent) => {
    e.preventDefault();
    chrome.runtime.openOptionsPage();
  };

  return (
    <div className="p-5">
      <div className="mb-6">
        <div className="flex justify-between items-center">
          <span className="font-medium text-white">
            {user.username || user.email || 'User'}
          </span>
          <button
            onClick={onLogout}
            className="text-neutral-400 text-xs hover:text-white transition-colors underline"
          >
            Logout
          </button>
        </div>
      </div>

      <button
        onClick={onScrape}
        className="w-full py-4 px-6 rounded-xl font-semibold text-lg bg-linear-to-br from-white/10 to-white/5 border border-white/20 text-white transition-all duration-300 backdrop-blur-[15px] hover:bg-linear-to-br hover:from-white/20 hover:to-white/10 hover:border-white/30 hover:-translate-y-[3px] hover:shadow-[0_10px_25px_rgba(0,0,0,0.2)] relative overflow-hidden cursor-pointer flex items-center justify-center gap-2"
      >
        <span>📦</span>
        <span>Pull In Current Page</span>
      </button>

      {statusMessage && (
        <div
          className={`mt-4 p-3 border rounded-xl text-sm text-center ${
            statusClasses[statusMessage.type]
          }`}
        >
          {statusMessage.message}
        </div>
      )}

      <div className="mt-6 text-center">
        <a
          href="#"
          onClick={handleSettingsClick}
          className="text-neutral-400 text-sm hover:text-white transition-colors"
        >
          Settings
        </a>
      </div>
    </div>
  );
};

export default MainScreen;
