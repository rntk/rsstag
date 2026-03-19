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
    <div className="p-3 border-b border-outline-variant/10 bg-surface-container-low/50">
      <div className="flex items-center gap-2 cursor-pointer select-none" onClick={() => setCollapsed(!collapsed)}>
        <span className="material-symbols-outlined text-sm text-on-surface-variant transition-transform duration-200" style={{ transform: collapsed ? 'none' : 'rotate(90deg)' }}>chevron_right</span>
        <span className="text-xs font-label font-bold text-on-surface-variant uppercase tracking-wider">Context ({context.type})</span>
      </div>
      {!collapsed && (
        <div className="mt-2 space-y-2">
          <div className="text-sm text-on-surface-variant leading-relaxed bg-surface-container-lowest p-2 rounded border border-outline-variant/10 italic font-body">{context.text}</div>
          {context.source_url && (
            <div className="text-xs text-primary hover:text-primary-container truncate">
              Source: <a href={context.source_url} target="_blank" rel="noopener noreferrer" className="underline font-medium">{context.source_url}</a>
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
    <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} mb-4 group font-body`}>
      <div className={`max-w-[85%] px-4 py-2 rounded-xl shadow-sm ${isUser ? 'bg-primary text-on-primary' : 'bg-surface-container-lowest text-on-surface border border-outline-variant/30'}`}>
        <div className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</div>
      </div>
      <div className={`flex items-center gap-2 mt-1 px-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        <span className="text-[10px] text-on-surface-variant font-medium">{formatDate(message.timestamp)}</span>
        <button
          className="p-1 hover:bg-surface-container-high rounded text-on-surface-variant hover:text-primary transition-colors"
          title="Fork conversation from here"
          onClick={() => onFork(index)}
        >
          <span className="material-symbols-outlined text-sm">fork_right</span>
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
    <div className="flex flex-col h-full bg-surface-container-lowest overflow-hidden font-body">
      <div className="flex items-center gap-3 p-4 bg-surface border-b border-outline-variant/10 shrink-0">
        <button className="p-1.5 hover:bg-surface-container-high rounded-full text-on-surface-variant transition-colors" onClick={onBack}>
          <span className="material-symbols-outlined text-xl">arrow_back</span>
        </button>
        {editingTitle ? (
          <input
            className="flex-1 px-3 py-1.5 bg-surface-container-low border border-primary/20 rounded-lg text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-primary/20"
            value={titleValue}
            onChange={(e) => setTitleValue(e.target.value)}
            onBlur={handleRenameSubmit}
            onKeyDown={(e) => { if (e.key === 'Enter') handleRenameSubmit(); if (e.key === 'Escape') setEditingTitle(false); }}
            autoFocus
          />
        ) : (
          <span className="flex-1 text-sm font-headline font-bold text-on-surface truncate cursor-pointer hover:text-primary transition-colors" onClick={() => setEditingTitle(true)} title="Click to rename">
            {chat.title || 'Chat'}
          </span>
        )}
      </div>
      <ChatContext context={chat.context} chatId={chat._id} ES={ES} />
      <div className="flex-1 overflow-y-auto p-4 custom-scrollbar bg-surface/30">
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} index={i} onFork={handleFork} />
        ))}
        {isLoading && (
          <div className="flex flex-col items-start mb-4">
            <div className="px-4 py-2 bg-surface-container-lowest border border-outline-variant/30 rounded-xl shadow-sm">
              <div className="flex gap-1">
                <span className="w-1.5 h-1.5 bg-primary/40 rounded-full animate-bounce"></span>
                <span className="w-1.5 h-1.5 bg-primary/40 rounded-full animate-bounce [animation-delay:0.2s]"></span>
                <span className="w-1.5 h-1.5 bg-primary/40 rounded-full animate-bounce [animation-delay:0.4s]"></span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      <div className="p-4 bg-surface border-t border-outline-variant/10 shrink-0">
        <div className="relative flex items-end gap-2">
          <textarea
            className="flex-1 min-h-[44px] max-h-32 px-4 py-2.5 bg-surface-container-high border border-outline-variant/30 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all resize-none custom-scrollbar disabled:opacity-50"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message..."
            rows={1}
            disabled={isLoading}
          />
          <button
            className="p-2.5 bg-primary hover:bg-primary-container disabled:bg-surface-variant text-on-primary rounded-lg transition-all shadow-sm hover:shadow-md disabled:shadow-none"
            onClick={handleSend}
            disabled={isLoading || !inputValue.trim()}
          >
            <span className="material-symbols-outlined text-xl">send</span>
          </button>
        </div>
      </div>
    </div>
  );
}

function ConversationList({ chats, onSelect, onCreate, onDelete }) {
  return (
    <div className="flex flex-col h-full bg-surface-container-lowest font-body">
      <div className="p-4 border-b border-outline-variant/10 flex justify-between items-center bg-surface-container-low/30">
        <h2 className="text-sm font-headline font-bold text-on-surface uppercase tracking-wider">Recent Chats</h2>
        <button
          className="flex items-center gap-1.5 px-3 py-1.5 bg-primary hover:bg-primary-container text-on-primary text-xs font-semibold rounded-lg transition-all shadow-sm hover:shadow-md active:scale-95"
          onClick={onCreate}
        >
          <span className="material-symbols-outlined text-sm">add</span>
          New Chat
        </button>
      </div>
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {chats.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full p-8 text-center text-on-surface-variant opacity-50">
            <span className="material-symbols-outlined text-4xl mb-2">forum</span>
            <p className="text-sm">No conversations yet</p>
          </div>
        ) : (
          <div className="divide-y divide-outline-variant/5">
            {chats.map((chat) => (
              <div
                key={chat._id}
                className="group relative p-4 hover:bg-surface-container-high cursor-pointer transition-colors"
                onClick={() => onSelect(chat._id)}
              >
                <div className="flex flex-col gap-1 pr-6">
                  <div className="text-sm font-semibold text-on-surface group-hover:text-primary truncate transition-colors">
                    {chat.title || 'Untitled Chat'}
                  </div>
                  <div className="flex items-center gap-3 text-[11px] font-medium text-on-surface-variant">
                    <span className="flex items-center gap-1">
                      <span className="material-symbols-outlined text-[12px]">calendar_today</span>
                      {formatDate(chat.updated_at)}
                    </span>
                    <span className="flex items-center gap-1 text-primary bg-surface-container-high px-1.5 py-0.5 rounded">
                      <span className="material-symbols-outlined text-[12px]">chat_bubble</span>
                      {chat.message_count}
                    </span>
                  </div>
                </div>
                <button
                  className="absolute right-4 top-1/2 -translate-y-1/2 p-1.5 opacity-0 group-hover:opacity-100 hover:bg-error-container hover:text-error text-on-surface-variant rounded-full transition-all duration-200"
                  title="Delete conversation"
                  onClick={(e) => { e.stopPropagation(); onDelete(chat._id); }}
                >
                  <span className="material-symbols-outlined text-lg">delete</span>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
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
      <button
        className={`fixed bottom-6 right-6 z-[60] flex items-center justify-center w-14 h-14 bg-primary text-on-primary rounded-xl shadow-lg hover:shadow-xl hover:bg-primary-container active:scale-95 transition-all duration-300 group ${state.isOpen ? 'rotate-90' : ''}`}
        onClick={handleToggle}
        title={state.isOpen ? 'Close Chat' : 'Open Chat'}
      >
        <span className="material-symbols-outlined text-2xl group-hover:scale-110 transition-transform">{state.isOpen ? 'close' : 'chat_bubble'}</span>
      </button>

      {state.isOpen && (
        <div className="fixed bottom-24 right-6 z-50 w-[400px] h-[600px] max-h-[calc(100vh-120px)] bg-surface rounded-xl shadow-2xl flex flex-col overflow-hidden border border-outline-variant/10 animate-in slide-in-from-bottom-4 duration-300 font-body">
          <div className="p-4 bg-surface-container-low border-b border-outline-variant/10 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center shadow-sm">
                <span className="material-symbols-outlined text-on-primary text-lg">robot_2</span>
              </div>
              <div>
                <h1 className="text-sm font-headline font-bold text-on-surface leading-none">Global Chat</h1>
                <span className="text-[10px] font-label font-medium text-green-600 flex items-center gap-0.5 mt-1">
                  <span className="w-1.5 h-1.5 bg-green-600 rounded-full"></span>
                  Online
                </span>
              </div>
            </div>
            <button
              className="p-2 hover:bg-surface-container-high rounded-lg text-on-surface-variant hover:text-on-surface transition-colors"
              onClick={handleToggle}
            >
              <span className="material-symbols-outlined">expand_more</span>
            </button>
          </div>

          <div className="flex-1 overflow-hidden">
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
        </div>
      )}
    </>
  );
}
