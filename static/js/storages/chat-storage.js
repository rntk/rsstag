'use strict';

export default class ChatStorage {
  constructor(event_system) {
    this.ES = event_system;
    this._state = {
      chats: [],
      activeChat: null,
      isOpen: false,
      isLoading: false,
    };
    this.urls = {
      list: '/api/chats',
      create: '/api/chats',
      detail: (id) => `/api/chats/${id}`,
      messages: (id) => `/api/chats/${id}/messages`,
      rename: (id) => `/api/chats/${id}/rename`,
      delete: (id) => `/api/chats/${id}/delete`,
      fork: (id) => `/api/chats/${id}/fork`,
      context: (id) => `/api/chats/${id}/context`,
    };
  }

  getState() {
    return { ...this._state };
  }

  _setState(patch) {
    this._state = { ...this._state, ...patch };
  }

  async fetchChats() {
    this._setState({ isLoading: true });
    try {
      const response = await fetch(this.urls.list, { credentials: 'include' });
      const data = await response.json();
      const chats = data.data || [];
      this._setState({ chats, isLoading: false });
      this.ES.trigger(this.ES.CHAT_LIST_UPDATED, this.getState());
    } catch (err) {
      console.error('Failed to fetch chats:', err);
      this._setState({ isLoading: false });
    }
  }

  async createChat(context) {
    this._setState({ isLoading: true });
    try {
      const body = { title: 'New Chat', context: context || null };
      const response = await fetch(this.urls.create, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await response.json();
      if (data.error) {
        console.error('Failed to create chat:', data.error);
        this._setState({ isLoading: false });
        return null;
      }
      const chatId = data.data.chat_id;
      await this.loadChat(chatId);
      await this.fetchChats();
      this._setState({ isOpen: true });
      this.ES.trigger(this.ES.CHAT_UPDATED, this.getState());
      return chatId;
    } catch (err) {
      console.error('Failed to create chat:', err);
      this._setState({ isLoading: false });
      return null;
    }
  }

  async loadChat(chatId) {
    this._setState({ isLoading: true });
    try {
      const response = await fetch(this.urls.detail(chatId), { credentials: 'include' });
      const data = await response.json();
      if (data.error) {
        console.error('Failed to load chat:', data.error);
        this._setState({ isLoading: false });
        return;
      }
      this._setState({ activeChat: data.data, isLoading: false });
      this.ES.trigger(this.ES.CHAT_UPDATED, this.getState());
    } catch (err) {
      console.error('Failed to load chat:', err);
      this._setState({ isLoading: false });
    }
  }

  async sendMessage(chatId, content) {
    this._setState({ isLoading: true });
    try {
      const response = await fetch(this.urls.messages(chatId), {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      });
      const data = await response.json();
      if (data.error) {
        console.error('Failed to send message:', data.error);
        this._setState({ isLoading: false });
        return null;
      }
      // Reload chat to get updated messages
      await this.loadChat(chatId);
      await this.fetchChats();
      return data.data;
    } catch (err) {
      console.error('Failed to send message:', err);
      this._setState({ isLoading: false });
      return null;
    }
  }

  async renameChat(chatId, title) {
    try {
      const response = await fetch(this.urls.rename(chatId), {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title }),
      });
      const data = await response.json();
      if (data.error) {
        console.error('Failed to rename chat:', data.error);
        return false;
      }
      if (this._state.activeChat && this._state.activeChat._id === chatId) {
        this._setState({ activeChat: { ...this._state.activeChat, title } });
      }
      await this.fetchChats();
      this.ES.trigger(this.ES.CHAT_UPDATED, this.getState());
      return true;
    } catch (err) {
      console.error('Failed to rename chat:', err);
      return false;
    }
  }

  async deleteChat(chatId) {
    try {
      const response = await fetch(this.urls.delete(chatId), {
        method: 'POST',
        credentials: 'include',
      });
      const data = await response.json();
      if (data.error) {
        console.error('Failed to delete chat:', data.error);
        return false;
      }
      if (this._state.activeChat && this._state.activeChat._id === chatId) {
        this._setState({ activeChat: null });
      }
      await this.fetchChats();
      this.ES.trigger(this.ES.CHAT_UPDATED, this.getState());
      return true;
    } catch (err) {
      console.error('Failed to delete chat:', err);
      return false;
    }
  }

  async forkChat(chatId, messageIndex) {
    try {
      const response = await fetch(this.urls.fork(chatId), {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_index: messageIndex }),
      });
      const data = await response.json();
      if (data.error) {
        console.error('Failed to fork chat:', data.error);
        return null;
      }
      const newId = data.data.chat_id;
      await this.loadChat(newId);
      await this.fetchChats();
      this.ES.trigger(this.ES.CHAT_UPDATED, this.getState());
      return newId;
    } catch (err) {
      console.error('Failed to fork chat:', err);
      return null;
    }
  }

  async updateContext(chatId, context) {
    try {
      const response = await fetch(this.urls.context(chatId), {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ context }),
      });
      const data = await response.json();
      if (data.error) {
        console.error('Failed to update context:', data.error);
        return false;
      }
      if (this._state.activeChat && this._state.activeChat._id === chatId) {
        this._setState({ activeChat: { ...this._state.activeChat, context } });
        this.ES.trigger(this.ES.CHAT_UPDATED, this.getState());
      }
      return true;
    } catch (err) {
      console.error('Failed to update context:', err);
      return false;
    }
  }

  bindEvents() {
    this.ES.bind(this.ES.CHAT_TOGGLE_PANEL, () => {
      this._setState({ isOpen: !this._state.isOpen });
      this.ES.trigger(this.ES.CHAT_UPDATED, this.getState());
    });

    this.ES.bind(this.ES.CHAT_START_WITH_CONTEXT, async (context) => {
      this._setState({ isOpen: true });
      this.ES.trigger(this.ES.CHAT_UPDATED, this.getState());
      await this.createChat(context);
    });
  }

  start() {
    this.bindEvents();
    this.fetchChats();
  }
}
