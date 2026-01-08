'use strict';
import React from 'react';
import rsstag_utils from '../libs/rsstag_utils.js';

export default class GlobalStatus extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      msgs: [],
      is_ok: true,
      promptType: null,
      promptValue: '',
    };
    this.ES = props.ES;
    this.timeout_handler = 0;
    this.immediatlyCheck = this.checkStatusAfter.bind(this, 50);
    this.promptInputRef = React.createRef();
  }

  checkStatusAfter(timeout) {
    if (this.timeout_handler) {
      clearTimeout(this.timeout_handler);
    }
    this.timeout_handler = setTimeout(() => {
      this.fetchStatus();
    }, timeout);
    //console.log('Next status fetching after: ', timeout);
  }

  fetchStatus() {
    rsstag_utils
      .fetchJSON('/status', {
        method: 'GET',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      })
      .then((data) => {
        if (data.data) {
          if (data.data) {
            this.setState({
              is_ok: data.data.is_ok,
              msgs: data.data.msgs,
            });
            if (data.data.telegram_password) {
              this.openTelegramPrompt('telegram_password');
              return;
            }
            if (data.data.telegram_code) {
              this.openTelegramPrompt('telegram_code');
              return;
            }
          }
        }
      })
      .catch((err) => {
        console.log('Can`t fetch status.', err);
      });
    this.checkStatusAfter(60000);
  }

  openTelegramPrompt(promptType) {
    if (this.state.promptType === promptType) {
      return;
    }
    this.setState({
      promptType,
      promptValue: '',
    });
  }

  componentDidMount() {
    this.checkStatusAfter(1000);
  }

  componentDidUpdate(prevProps, prevState) {
    if (this.state.promptType && this.state.promptType !== prevState.promptType) {
      if (this.promptInputRef.current) {
        this.promptInputRef.current.focus();
      }
    }
  }

  handlePromptChange = (event) => {
    this.setState({ promptValue: event.target.value });
  };

  handlePromptSubmit = (event) => {
    event.preventDefault();
    const value = this.state.promptValue.trim();
    if (!value || !this.state.promptType) {
      return;
    }
    if (this.state.promptType === 'telegram_password') {
      this.ES.trigger(this.ES.SAVE_TELEGRAM_PASSWORD, value);
    } else {
      this.ES.trigger(this.ES.SAVE_TELEGRAM_CODE, value);
    }
    this.setState({
      promptType: null,
      promptValue: '',
    });
  };

  render() {
    if (!this.state) {
      return null;
    }

    let statusNode = null;
    if (!this.state.is_ok) {
      const msgTitles = this.state.msgs.map((m) => (typeof m === 'string' ? m : m.title));
      statusNode = (
        <a href="/provider" className="error" title={'ERROR: ' + msgTitles.join(', ')}>
          E
        </a>
      );
    } else if (this.state.msgs && this.state.msgs.length) {
      const titles = [];
      let totalCount = 0;
      this.state.msgs.forEach((msg) => {
        let title = msg.title;
        if (msg.count > -1) {
          title += ` (${msg.count})`;
          totalCount += msg.count;
        }
        titles.push(title);
      });

      const displayText = totalCount > 0 ? totalCount : 'W';
      statusNode = (
        <abbr title={'Working: ' + titles.join(', ')} onClick={this.immediatlyCheck}>
          {displayText}
        </abbr>
      );
    } else {
      //&#x21bb; or &#x27F3; refresh symbols
      statusNode = (
        <abbr title="No active tasks. Click to refresh" onClick={this.immediatlyCheck}>
          &#x27F3;
        </abbr>
      );
    }

    const promptLabel =
      this.state.promptType === 'telegram_password' ? 'Telegram password' : 'Telegram code';
    const promptType = this.state.promptType === 'telegram_password' ? 'password' : 'text';
    const promptAutocomplete =
      this.state.promptType === 'telegram_password' ? 'current-password' : 'one-time-code';

    return (
      <React.Fragment>
        {statusNode}
        {this.state.promptType && (
          <div className="telegram-auth-overlay">
            <form className="telegram-auth-modal" onSubmit={this.handlePromptSubmit}>
              <label className="telegram-auth-label" htmlFor="telegram-auth-input">
                {promptLabel}
              </label>
              <input
                className="telegram-auth-input"
                id="telegram-auth-input"
                type={promptType}
                autoComplete={promptAutocomplete}
                value={this.state.promptValue}
                onChange={this.handlePromptChange}
                ref={this.promptInputRef}
                required
              />
              <button className="telegram-auth-submit" type="submit">
                Submit
              </button>
            </form>
          </div>
        )}
      </React.Fragment>
    );
  }
}
