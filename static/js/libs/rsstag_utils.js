'use strict';

class RssTagUtils {

    fetchJSON(url, opts) {
        let ES = window.EVSYS;
        ES.trigger(window.EVSYS.START_TASK, 'ajax');
        let req_promise = fetch(url, opts),
            prom = new Promise((resolve, reject) => {
                req_promise.then(response => {
                    response.json().then(data => {
                        ES.trigger(ES.END_TASK, 'ajax');
                        resolve(data);
                    }).catch(err => {
                        ES.trigger(ES.END_TASK, 'ajax');
                        reject(err);
                    });
                }).catch(err => {
                    ES.trigger(ES.END_TASK, 'ajax');
                    reject(err);
                });
            })

        return prom;
    };

    randInt(min, max) {
        return (Math.random() * (max - min)) + min;
    };
};

const rsstag_utils = new RssTagUtils();

export default rsstag_utils;