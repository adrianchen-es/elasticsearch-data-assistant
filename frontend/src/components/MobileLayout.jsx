import React, { useState } from 'react';
import { Database, X, Menu } from 'lucide-react';

export default function MobileLayout({ children }) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white shadow-sm border-b border-gray-200 lg:hidden">
        <div className="flex items-center justify-between h-16 px-4">
          <div className="flex items-center">
            <Database className="h-6 w-6 text-blue-600 mr-2" />
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-semibold text-gray-900">ES AI Assistant</h1>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <button className="p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
              {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </button>
          </div>
        </div>
        {mobileMenuOpen && (
          <div className="border-t border-gray-200 bg-white">
            <div className="px-2 pt-2 pb-3 space-y-1">
              <a className="px-3 py-2 rounded-md text-sm hover:bg-gray-50 block">Chats</a>
              <a className="px-3 py-2 rounded-md text-sm hover:bg-gray-50 block">Indexes</a>
            </div>
          </div>
        )}
      </header>
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
}
