'use strict';

class RssTagUtils {
  fetchJSON(url, opts) {
    let ES = window.EVSYS;
    ES.trigger(window.EVSYS.START_TASK, 'ajax');
    let req_promise = fetch(url, opts),
      prom = new Promise((resolve, reject) => {
        req_promise
          .then((response) => {
            response
              .json()
              .then((data) => {
                ES.trigger(ES.END_TASK, 'ajax');
                resolve(data);
              })
              .catch((err) => {
                ES.trigger(ES.END_TASK, 'ajax');
                reject(err);
              });
          })
          .catch((err) => {
            ES.trigger(ES.END_TASK, 'ajax');
            reject(err);
          });
      });

    return prom;
  }

  randInt(min, max) {
    return Math.random() * (max - min) + min;
  }

  waitFor(test_func, timeout, check_interval) {
    let start_time = new Date().getTime(),
      interval_handler = 0,
      prom = new Promise((resolve, reject) => {
        interval_handler = setInterval(
          () => {
            if (test_func()) {
              clearInterval(interval_handler);
              resolve();
            }
            if (timeout) {
              let dt = new Date().getTime();

              if (dt - start_time >= timeout) {
                clearInterval(interval_handler);
                reject();
              }
            }
          },
          check_interval ? check_interval : 1000
        );
      });

    return prom;
  }
}

const rsstag_utils = new RssTagUtils();

export default rsstag_utils;
