'use strict';
import React from 'react';
import SettingsMenuButton from './menu-button.js';

export default class SettingsMenu extends React.Component {
  constructor(props) {
    super(props);
    this.saveSettings = this.saveSettings.bind(this);
    this.updateSettings = this.updateSettings.bind(this);
    this.changeIntSettings = this.changeIntSettings.bind(this);
    this.changeBoolSettings = this.changeBoolSettings.bind(this);
    this.changeStringSettings = this.changeStringSettings.bind(this);
    this.hideMenu = this.hideMenu.bind(this);
    this.handleKeyDown = this.handleKeyDown.bind(this);
    this.handleClickOutside = this.handleClickOutside.bind(this);
    this.menuRef = React.createRef();
  }

  saveSettings() {
    this.props.ES.trigger(this.props.ES.UPDATE_SETTINGS, Object.assign({}, this.state.settings));
  }

  hideMenu() {
    this.props.ES.trigger(this.props.ES.CHANGE_SETTINGS_WINDOW_STATE);
  }

  handleKeyDown(e) {
    if (e.key === 'Escape') {
      this.hideMenu();
    }
  }

  handleClickOutside(e) {
    if (this.menuRef.current && !this.menuRef.current.contains(e.target)) {
      this.hideMenu();
    }
  }

  updateSettings(state) {
    this.setState(state);
  }

  componentDidMount() {
    this.props.ES.bind(this.props.ES.SETTINGS_UPDATED, this.updateSettings);
    //subscribe
  }

  componentDidUpdate(prevProps, prevState) {
    if (this.state && this.state.showed && (!prevState || !prevState.showed)) {
      // Menu is now shown, add listeners
      document.addEventListener('keydown', this.handleKeyDown);
      document.addEventListener('mousedown', this.handleClickOutside);
    } else if (prevState && prevState.showed && (!this.state || !this.state.showed)) {
      // Menu is now hidden, remove listeners
      document.removeEventListener('keydown', this.handleKeyDown);
      document.removeEventListener('mousedown', this.handleClickOutside);
    }
  }

  changeIntSettings(e) {
    let value = parseInt(e.target.value),
      name = e.target.id;

    if (!isNaN(value)) {
      this.state.settings[name] = value;
      this.setState(this.state);
      return true;
    } else {
      return false;
    }
  }

  changeStringSettings(e) {
    let value = e.target.value,
      name = e.target.id;
    this.state.settings[name] = value;
    this.setState(this.state);
    return true;
  }

  changeBoolSettings(e) {
    let name = e.target.id;

    this.state.settings[name] = e.target.checked;
    this.setState(this.state);

    return true;
  }

  componentWillUnmount() {
    this.props.ES.unbind(this.props.ES.SETTINGS_UPDATED, this.updateSettings);
    //unsubscribe
    document.removeEventListener('keydown', this.handleKeyDown);
    document.removeEventListener('mousedown', this.handleClickOutside);
  }

  render() {
    let button = <SettingsMenuButton ES={this.props.ES} src="/static/img/menu.png" />;
    if (this.state && this.state.showed === true) {
      let style = {
        top: this.state.offset.top,
        right: this.state.offset.right,
      };

      const llmOptions = [
        <option key="llamacpp" value="llamacpp">LlamaCPP</option>,
        <option key="openai" value="openai">OpenAI</option>,
        <option key="anthropic" value="anthropic">Anthropic</option>,
        <option key="cerebras" value="cerebras">Cerebras</option>,
        <option key="groqcom" value="groqcom">GroqCom</option>
      ];

      return (
        <div>
          {button}
          <div className="main_menu_window" style={style} ref={this.menuRef}>
            <div>
              <label htmlFor="posts_on_page">posts per page</label>
              <br />
              <input
                id="posts_on_page"
                name="posts_on_page"
                type="text"
                value={this.state.settings.posts_on_page}
                onChange={this.changeIntSettings}
              />
            </div>
            <div id="tags_per_page">
              <label htmlFor="tags_on_page">tags per page</label>
              <br />
              <input
                id="tags_on_page"
                name="tags_on_page"
                type="text"
                value={this.state.settings.tags_on_page}
                onChange={this.changeIntSettings}
              />
            </div>
            <div id="context_n_">
              <label htmlFor="context_n">context size</label>
              <br />
              <input
                id="context_n"
                name="context_n"
                type="text"
                value={this.state.settings.context_n}
                onChange={this.changeIntSettings}
              />
            </div>
            <div id="telegram_limit_">
              <label htmlFor="telegram_limit">telegram limit (0 for only unread)</label>
              <br />
              <input
                id="telegram_limit"
                name="telegram_limit"
                type="text"
                value={this.state.settings.telegram_limit}
                onChange={this.changeIntSettings}
              />
            </div>
            <div id="batch_llm_">
              <label htmlFor="batch_llm">Batch LLM</label>
              <br />
              <select
                id="batch_llm"
                name="batch_llm"
                value={this.state.settings.batch_llm || "openai"}
                onChange={this.changeStringSettings}
              >
                {llmOptions}
              </select>
            </div>
            <div id="worker_llm_">
              <label htmlFor="worker_llm">Worker LLM</label>
              <br />
              <select
                id="worker_llm"
                name="worker_llm"
                value={this.state.settings.worker_llm || "llamacpp"}
                onChange={this.changeStringSettings}
              >
                {llmOptions}
              </select>
            </div>
            <div id="realtime_llm_">
              <label htmlFor="realtime_llm">Realtime LLM</label>
              <br />
              <select
                id="realtime_llm"
                name="realtime_llm"
                value={this.state.settings.realtime_llm || "llamacpp"}
                onChange={this.changeStringSettings}
              >
                {llmOptions}
              </select>
            </div>
            <div>
              <label htmlFor="only_unread">
                <input
                  id="only_unread"
                  name="only_unread"
                  type="checkbox"
                  checked={this.state.settings.only_unread}
                  onChange={this.changeBoolSettings}
                />
                only unread
              </label>
            </div>
            <div>
              <label htmlFor="hot_tags">
                <input
                  id="hot_tags"
                  name="hot_tags"
                  type="checkbox"
                  checked={this.state.settings.hot_tags}
                  onChange={this.changeBoolSettings}
                />
                hot tags
              </label>
            </div>
            <div>
              <label htmlFor="similar_posts">
                <input
                  id="similar_posts"
                  name="similar_posts"
                  type="checkbox"
                  checked={this.state.settings.similar_posts}
                  onChange={this.changeBoolSettings}
                />
                similar posts
              </label>
            </div>
            <button id="save_settings" onClick={this.saveSettings}>
              Save
            </button>
          </div>
        </div>
      );
    } else {
      return button;
    }
  }
}
