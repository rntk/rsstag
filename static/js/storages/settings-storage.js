'use strict';
export default class SettingsStorage {
    constructor(event_system) {
        this.ES = event_system;
        this._state = {
            settings: {},
            offset: {},
            showed: false
        };
        this.urls = {
            save_settings: '/settings',
            save_telegram_code: '/telegram-code'
        };
    }

    fetchSettings() {
        let state = this.getState();

        state.settings = window.rss_settings;
        this.setState(state);
    }

    getState() {
        return(Object.assign({}, this._state));
    }

    setState(state) {
        if (state.showed === undefined) {
            state.showed = false;
        }
        this._state = state;
        this.ES.trigger(this.ES.SETTINGS_UPDATED, this.getState());
    }

    bindEvents() {
        this.ES.bind(this.ES.UPDATE_SETTINGS, this.saveSettings.bind(this));
        this.ES.bind(this.ES.CHANGE_SETTINGS_WINDOW_STATE, this.changeSettingsWindowState.bind(this));
        this.ES.bind(this.ES.SAVE_TELEGRAM_CODE, this.saveTelegramCode.bind(this));
    }

    changeSettingsWindowState(offset) {
        let state = this.getState();

        state.showed = !state.showed;
        if (offset) {
            state.offset = offset;
        }
        this.setState(state);
    }

    saveSettings(settings) {
        fetch(
            this.urls.save_settings,
            {
                method: 'POST',
                credentials: 'include',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(this._state.settings)
            }
        ).then(response => {
            response.json().then(data => {
                if (data.data) {
                    let state = this.getState();

                    state.settings = settings;
                    this.setState(state);
                } else {
                    this.ES.trigger(this.ES.SETTINGS_UPDATED, this.getState());
                    this.errorMessage('Error. Try later');
                }
            });
            this.changeSettingsWindowState();
        }).catch(err => {
            this.errorMessage('Error. Try later');
        });
    }

    saveTelegramCode(code) {
        fetch(
            this.urls.save_telegram_code,
            {
                method: 'POST',
                credentials: 'include',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({code: code})
            }
        ).then(response => {
            return;
        }).catch(err => {
            this.errorMessage('Error. Try later');
        });
    }

    errorMessage(msg) {
        console.log(msg);
        this.ES.trigger(this.SETTINGS_ERROR_MESSAGE, msg);
    }

    start() {
        this.bindEvents();
        this.fetchSettings();
    }
}