import React, { useState, useEffect } from 'react';
import { MessageSquare, Plus, Trash2, Star } from 'lucide-react';

const STORAGE_KEYS = {
  CONVERSATIONS: 'elasticsearch_chat_conversations',
  FAVORITES: 'elasticsearch_chat_favorites'
};

const ConversationManager = ({ 
  currentConversationId, 
  onConversationChange, 
  onNewConversation 
}) => {
  const [conversations, setConversations] = useState({});
  const [favorites, setFavorites] = useState(new Set());
  const [showManager, setShowManager] = useState(false);

  useEffect(() => {
    loadConversations();
  }, []);

  const loadConversations = () => {
    try {
      const conversationsData = localStorage.getItem(STORAGE_KEYS.CONVERSATIONS);
      const favoritesData = localStorage.getItem(STORAGE_KEYS.FAVORITES);
      
      if (conversationsData) {
        setConversations(JSON.parse(conversationsData));
      }
      
      if (favoritesData) {
        setFavorites(new Set(JSON.parse(favoritesData)));
      }
    } catch (error) {
      console.warn('Failed to load conversations:', error);
    }
  };

  const toggleFavorite = (conversationId) => {
    const newFavorites = new Set(favorites);
    if (newFavorites.has(conversationId)) {
      newFavorites.delete(conversationId);
    } else {
      newFavorites.add(conversationId);
    }
    setFavorites(newFavorites);
    localStorage.setItem(STORAGE_KEYS.FAVORITES, JSON.stringify([...newFavorites]));
  };

  const deleteConversation = (conversationId) => {
    if (window.confirm('Are you sure you want to delete this conversation?')) {
      const updatedConversations = { ...conversations };
      delete updatedConversations[conversationId];
      setConversations(updatedConversations);
      localStorage.setItem(STORAGE_KEYS.CONVERSATIONS, JSON.stringify(updatedConversations));
      
      // Remove from favorites if present
      const newFavorites = new Set(favorites);
      newFavorites.delete(conversationId);
      setFavorites(newFavorites);
      localStorage.setItem(STORAGE_KEYS.FAVORITES, JSON.stringify([...newFavorites]));
      
      // If deleting current conversation, start a new one
      if (conversationId === currentConversationId) {
        onNewConversation();
      }
    }
  };

  const formatDate = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else if (diffDays === 1) {
      return 'Yesterday';
    } else if (diffDays < 7) {
      return `${diffDays} days ago`;
    } else {
      return date.toLocaleDateString();
    }
  };

  const sortedConversations = Object.values(conversations).sort((a, b) => {
    // Favorites first, then by last updated
    const aFav = favorites.has(a.id);
    const bFav = favorites.has(b.id);
    if (aFav && !bFav) return -1;
    if (!aFav && bFav) return 1;
    return (b.lastUpdated || 0) - (a.lastUpdated || 0);
  });

  return (
    <div className="relative">
      <button
        onClick={() => setShowManager(!showManager)}
        className="flex items-center space-x-2 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-md"
        title="Manage Conversations"
      >
        <MessageSquare className="h-4 w-4" />
        <span className="hidden sm:inline">Conversations</span>
      </button>

      {showManager && (
        <div className="absolute top-full left-0 mt-2 w-80 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
          <div className="p-4 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-medium">Conversations</h3>
              <button
                onClick={() => {
                  onNewConversation();
                  setShowManager(false);
                }}
                className="flex items-center space-x-1 px-2 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                <Plus className="h-4 w-4" />
                <span>New</span>
              </button>
            </div>
          </div>

          <div className="max-h-80 overflow-y-auto">
            {sortedConversations.length === 0 ? (
              <div className="p-4 text-center text-gray-500">
                No conversations yet
              </div>
            ) : (
              sortedConversations.map((conversation) => (
                <div
                  key={conversation.id}
                  className={`p-3 border-b border-gray-100 hover:bg-gray-50 cursor-pointer ${
                    conversation.id === currentConversationId ? 'bg-blue-50 border-blue-200' : ''
                  }`}
                  onClick={() => {
                    onConversationChange(conversation.id);
                    setShowManager(false);
                  }}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center space-x-2">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {conversation.title || 'Untitled Conversation'}
                        </p>
                        {favorites.has(conversation.id) && (
                          <Star className="h-3 w-3 text-yellow-500 fill-current" />
                        )}
                      </div>
                      <p className="text-xs text-gray-500 mt-1">
                        {conversation.mode === 'elasticsearch' && conversation.index && (
                          <span className="mr-2">📊 {conversation.index}</span>
                        )}
                        {conversation.messages?.length || 0} messages
                      </p>
                      <p className="text-xs text-gray-400">
                        {formatDate(conversation.lastUpdated)}
                      </p>
                    </div>
                    <div className="flex items-center space-x-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleFavorite(conversation.id);
                        }}
                        className="p-1 hover:bg-gray-100 rounded"
                        title={favorites.has(conversation.id) ? 'Remove from favorites' : 'Add to favorites'}
                      >
                        <Star className={`h-3 w-3 ${
                          favorites.has(conversation.id) 
                            ? 'text-yellow-500 fill-current' 
                            : 'text-gray-400'
                        }`} />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteConversation(conversation.id);
                        }}
                        className="p-1 hover:bg-red-100 text-red-600 rounded"
                        title="Delete conversation"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default ConversationManager;
