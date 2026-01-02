'use strict';
import React from 'react';
import rsstag_utils from '../libs/rsstag_utils.js';

export default class GlobalStatus extends React.Component{
    constructor(props) {
        super(props);
        this.state = {
            msgs: [],
            is_ok: true
        };
        this.ES = props.ES;
        this.timeout_handler = 0;
        this.immediatlyCheck = this.checkStatusAfter.bind(this, 50);
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
        rsstag_utils.fetchJSON(
            '/status',
            {
                method: 'GET',
                credentials: 'include',
                headers: {'Content-Type': 'application/json'},
            }
        ).then(data => {
            if (data.data) {
                if (data.data) {
                    this.setState({
                        is_ok: data.data.is_ok,
                        msgs: data.data.msgs
                    });
                    if (data.data.telegram_password) {
                        this.getTelegramPassword();
                        return;
                    }
                    if (data.data.telegram_code) {
                        this.getTelegramCode();
                        return;
                    }
                }
            }
        }).catch(err => {
            console.log('Can`t fetch status.', err);
        });
        this.checkStatusAfter(60000);
    }

    getTelegramCode() {
        let code = "";
        while (true) {
            code = prompt("Telegram code:");
            if (code) {
                break;
            }
        }
        this.ES.trigger(this.ES.SAVE_TELEGRAM_CODE, code);
    }

    getTelegramPassword() {
        let pswd = "";
        while (true) {
            pswd = prompt("Telegram password:");
            if (pswd) {
                break;
            }
        }
        this.ES.trigger(this.ES.SAVE_TELEGRAM_PASSWORD, pswd);
    }

    componentDidMount() {
        this.checkStatusAfter(1000);
    }

    render() {
        if (this.state) {
            if (!this.state.is_ok) {
                const msgTitles = this.state.msgs.map(m => (typeof m === 'string' ? m : m.title));
                return <a href="/provider" className="error" title={'ERROR: ' + msgTitles.join(', ')}>E</a>;
            } else if (this.state.msgs && this.state.msgs.length) {
                const titles = [];
                let totalCount = 0;
                this.state.msgs.forEach(msg => {
                    let title = msg.title;
                    if (msg.count > -1) {
                        title += ` (${msg.count})`;
                        totalCount += msg.count;
                    }
                    titles.push(title);
                });

                const displayText = totalCount > 0 ? totalCount : 'W';
                return <abbr title={'Working: ' + titles.join(', ')} onClick={this.immediatlyCheck}>{displayText}</abbr>;
            } else {//&#x21bb; or &#x27F3; refresh symbols
                return <abbr title="No active tasks. Click to refresh" onClick={this.immediatlyCheck}>&#x27F3;</abbr>;
            }
        }

        return null;
    }
};