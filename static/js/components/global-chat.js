'use strict';
import React, { useState, useEffect, useRef } from 'react';

function formatDate(ts) {
  if (!ts) return '';
  const d = new Date(ts * 1000);
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function ChatContext({ context, chatId, ES }) {
  const [collapsed, setCollapsed] = useState(true);
  if (!context || context.type === 'empty' || !context.text) return null;

  return (
    <div className="chat-context">
      <div className="chat-context-header" onClick={() => setCollapsed(!collapsed)}>
        <span className="chat-context-toggle">{collapsed ? '▶' : '▼'}</span>
        <span className="chat-context-label">Context ({context.type})</span>
      </div>
      {!collapsed && (
        <div className="chat-context-body">
          <div className="chat-context-text">{context.text}</div>
          {context.source_url && (
            <div className="chat-context-source">
              Source: <a href={context.source_url} target="_blank" rel="noopener noreferrer">{context.source_url}</a>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function MessageBubble({ message, index, onFork }) {
  const isUser = message.role === 'user';
  return (
    <div className={`chat-message ${isUser ? 'user' : 'assistant'}`}>
      <div className="chat-message-content">{message.content}</div>
      <div className="chat-message-meta">
        <span className="chat-message-time">{formatDate(message.timestamp)}</span>
        <button
          className="chat-fork-btn"
          title="Fork conversation from here"
          onClick={() => onFork(index)}
        >
          ⑂
        </button>
      </div>
    </div>
  );
}

function ChatView({ chat, onBack, ES }) {
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleValue, setTitleValue] = useState(chat.title || 'Chat');
  const messagesEndRef = useRef(null);

  useEffect(() => {
    setTitleValue(chat.title || 'Chat');
  }, [chat.title]);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chat.messages]);

  const handleSend = async () => {
    const content = inputValue.trim();
    if (!content || isLoading) return;
    setInputValue('');
    setIsLoading(true);

    // Optimistically add user message to local state
    const tempMsg = { role: 'user', content, timestamp: Date.now() / 1000 };
    // We'll rely on ES reload

    try {
      const response = await fetch(`/api/chats/${chat._id}/messages`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      });
      const data = await response.json();
      if (data.error) {
        console.error('Send message error:', data.error);
      }
    } catch (err) {
      console.error('Send message failed:', err);
    }

    // Reload chat
    try {
      const resp = await fetch(`/api/chats/${chat._id}`, { credentials: 'include' });
      const data = await resp.json();
      if (data.data) {
        ES.trigger(ES.CHAT_UPDATED, { activeChat: data.data });
      }
    } catch (err) {
      console.error('Reload chat failed:', err);
    }

    setIsLoading(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFork = async (messageIndex) => {
    try {
      const response = await fetch(`/api/chats/${chat._id}/fork`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_index: messageIndex }),
      });
      const data = await response.json();
      if (data.data) {
        // Load the new forked chat
        const resp = await fetch(`/api/chats/${data.data.chat_id}`, { credentials: 'include' });
        const chatData = await resp.json();
        if (chatData.data) {
          ES.trigger(ES.CHAT_UPDATED, { activeChat: chatData.data });
        }
        // Refresh list
        const listResp = await fetch('/api/chats', { credentials: 'include' });
        const listData = await listResp.json();
        if (listData.data) {
          ES.trigger(ES.CHAT_LIST_UPDATED, { chats: listData.data });
        }
      }
    } catch (err) {
      console.error('Fork failed:', err);
    }
  };

  const handleRenameSubmit = async () => {
    if (!titleValue.trim()) return;
    try {
      await fetch(`/api/chats/${chat._id}/rename`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: titleValue }),
      });
      ES.trigger(ES.CHAT_UPDATED, { activeChat: { ...chat, title: titleValue } });
    } catch (err) {
      console.error('Rename failed:', err);
    }
    setEditingTitle(false);
  };

  const messages = chat.messages || [];

  return (
    <div className="chat-view">
      <div className="chat-view-header">
        <button className="chat-back-btn" onClick={onBack}>←</button>
        {editingTitle ? (
          <input
            className="chat-title-input"
            value={titleValue}
            onChange={(e) => setTitleValue(e.target.value)}
            onBlur={handleRenameSubmit}
            onKeyDown={(e) => { if (e.key === 'Enter') handleRenameSubmit(); if (e.key === 'Escape') setEditingTitle(false); }}
            autoFocus
          />
        ) : (
          <span className="chat-view-title" onClick={() => setEditingTitle(true)} title="Click to rename">
            {chat.title || 'Chat'}
          </span>
        )}
      </div>
      <ChatContext context={chat.context} chatId={chat._id} ES={ES} />
      <div className="chat-messages">
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} index={i} onFork={handleFork} />
        ))}
        {isLoading && (
          <div className="chat-message assistant">
            <div className="chat-message-content chat-thinking">Thinking...</div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      <div className="chat-input-area">
        <textarea
          className="chat-input"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message... (Enter to send, Shift+Enter for newline)"
          rows={3}
          disabled={isLoading}
        />
        <button className="chat-send-btn" onClick={handleSend} disabled={isLoading || !inputValue.trim()}>
          {isLoading ? '...' : 'Send'}
        </button>
      </div>
    </div>
  );
}

function ConversationList({ chats, onSelect, onCreate, onDelete }) {
  return (
    <div className="chat-list">
      <div className="chat-list-toolbar">
        <button className="chat-new-btn" onClick={onCreate}>+ New Chat</button>
      </div>
      {chats.length === 0 && (
        <div className="chat-empty">No conversations yet</div>
      )}
      {chats.map((chat) => (
        <div key={chat._id} className="chat-list-item" onClick={() => onSelect(chat._id)}>
          <div className="chat-list-item-title">{chat.title || 'Untitled'}</div>
          <div className="chat-list-item-meta">
            <span className="chat-list-item-date">{formatDate(chat.updated_at)}</span>
            <span className="chat-list-item-count">{chat.message_count} msgs</span>
          </div>
          <button
            className="chat-list-item-delete"
            title="Delete"
            onClick={(e) => { e.stopPropagation(); onDelete(chat._id); }}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}

export default function GlobalChatPanel({ ES }) {
  const [state, setState] = useState({
    chats: [],
    activeChat: null,
    isOpen: false,
    isLoading: false,
  });

  useEffect(() => {
    const onChatUpdated = (patch) => {
      setState((prev) => {
        if (patch && patch.activeChat !== undefined) {
          return { ...prev, activeChat: patch.activeChat };
        }
        return { ...prev, ...patch };
      });
    };
    const onChatListUpdated = (patch) => {
      setState((prev) => ({ ...prev, chats: patch.chats || patch || prev.chats }));
    };

    ES.bind(ES.CHAT_UPDATED, onChatUpdated);
    ES.bind(ES.CHAT_LIST_UPDATED, onChatListUpdated);
    ES.bind(ES.CHAT_TOGGLE_PANEL, () => {
      setState((prev) => ({ ...prev, isOpen: !prev.isOpen }));
    });

    return () => {
      ES.unbind(ES.CHAT_UPDATED, onChatUpdated);
      ES.unbind(ES.CHAT_LIST_UPDATED, onChatListUpdated);
    };
  }, [ES]);

  const handleToggle = () => {
    ES.trigger(ES.CHAT_TOGGLE_PANEL);
  };

  const handleSelectChat = async (chatId) => {
    try {
      const resp = await fetch(`/api/chats/${chatId}`, { credentials: 'include' });
      const data = await resp.json();
      if (data.data) {
        setState((prev) => ({ ...prev, activeChat: data.data }));
      }
    } catch (err) {
      console.error('Failed to load chat:', err);
    }
  };

  const handleCreateChat = async (context) => {
    try {
      const response = await fetch('/api/chats', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'New Chat', context: context || null }),
      });
      const data = await response.json();
      if (data.data) {
        const chatId = data.data.chat_id;
        await handleSelectChat(chatId);
        // Refresh list
        const listResp = await fetch('/api/chats', { credentials: 'include' });
        const listData = await listResp.json();
        setState((prev) => ({ ...prev, chats: listData.data || prev.chats }));
      }
    } catch (err) {
      console.error('Failed to create chat:', err);
    }
  };

  const handleDeleteChat = async (chatId) => {
    try {
      await fetch(`/api/chats/${chatId}/delete`, {
        method: 'POST',
        credentials: 'include',
      });
      setState((prev) => ({
        ...prev,
        chats: prev.chats.filter((c) => c._id !== chatId),
        activeChat: prev.activeChat && prev.activeChat._id === chatId ? null : prev.activeChat,
      }));
    } catch (err) {
      console.error('Failed to delete chat:', err);
    }
  };

  const handleBack = () => {
    setState((prev) => ({ ...prev, activeChat: null }));
    // Refresh list
    fetch('/api/chats', { credentials: 'include' })
      .then((r) => r.json())
      .then((data) => setState((prev) => ({ ...prev, chats: data.data || prev.chats })))
      .catch(() => {});
  };

  return (
    <>
      <button className="chat-toggle-btn" onClick={handleToggle} title="Open Chat">
        💬
      </button>
      {state.isOpen && (
        <div className="chat-panel">
          <div className="chat-panel-header">
            <span className="chat-panel-title">Chats</span>
            <button className="chat-panel-close" onClick={handleToggle}>×</button>
          </div>
          {state.activeChat ? (
            <ChatView chat={state.activeChat} onBack={handleBack} ES={ES} />
          ) : (
            <ConversationList
              chats={state.chats}
              onSelect={handleSelectChat}
              onCreate={() => handleCreateChat(null)}
              onDelete={handleDeleteChat}
            />
          )}
        </div>
      )}
    </>
  );
}
