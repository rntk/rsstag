import os
import json
import queue
import time
import datetime
import logging
from ctypes import *
from typing import Callable, Dict, Any, Optional
from queue import Queue
from threading import Thread, Event
from random import randint

from .queries import (
    set_log_verbosity_level,
    set_tdlib_parameters,
    get_authorization_state,
    check_authentication_code,
    check_authentication_password,
    set_authentication_phone_number,
    check_database_encryption_key,
)


class Result:
    def __init__(self, data: Optional[dict], error: Optional[dict]):
        self.update = data
        self.error = error

    def __str__(self) -> str:
        return "Data: {}\nError: {}".format(self.update, self.error)


class ResponseEvent(Event):
    def __init__(self, req_id: str):
        super().__init__()
        self.__ev_data: Optional[Result] = None
        self.__req_id = req_id

    def set_data(self, data: Result):
        if self.is_set():
            raise Exception("Event already is set")

        self.__ev_data = data
        self.set()

    def get_data(self) -> Optional[Result]:
        return self.__ev_data

    @property
    def request_id(self) -> str:
        return self.__req_id


# TODO: refactor
# WARNING: absolutely silly and naive implementation
class Telegram:
    def __init__(
        self,
        app_id: int,
        app_hash: str,
        phone: str,
        db_path: str,
        db_key: str,
        tdjson_path: str = "",
    ):
        self._app_id = app_id
        self._app_hash = app_hash
        self._phone = phone
        self._db_path = db_path
        if tdjson_path == "":
            tdjson_path = os.path.join(os.path.dirname(__file__), "lib", "libtdjson.so")
        self._tdjson_path = tdjson_path
        self._get_code_fn = None
        self._db_key = db_key
        self._auth = False
        self._responser = None
        self._queue = Queue()
        self._stopped = False
        self._auth = False

        self._log: logging.Logger = logging.getLogger("telegram")
        self._tdjson = CDLL(tdjson_path)

        self._td_create_client_id = self._tdjson.td_create_client_id
        self._td_create_client_id.restype = c_int
        self._td_create_client_id.argtypes = []

        self._td_execute = self._tdjson.td_execute
        self._td_execute.restype = c_char_p
        self._td_execute.argtypes = [c_char_p]

        self._td_receive = self._tdjson.td_receive
        self._td_receive.restype = c_char_p
        self._td_receive.argtypes = [c_double]

        self._td_send = self._tdjson.td_send
        self._td_send.restype = None
        self._td_send.argtypes = [c_int, c_char_p]

        log_message_callback_type = CFUNCTYPE(None, c_int, c_char_p)

        self._td_set_log_message_callback = self._tdjson.td_set_log_message_callback
        self._td_set_log_message_callback.restype = None
        self._td_set_log_message_callback.argtypes = [c_int, log_message_callback_type]
        self._c_on_log_message_callback = log_message_callback_type(
            self._on_log_message_callback
        )
        self._td_set_log_message_callback(2, self._c_on_log_message_callback)

        self._client_id = None

    def _listen_responses(self):
        events: Dict[str, ResponseEvent] = {}
        while self._auth and not self._stopped:
            r = self._receive()
            if not r:
                time.sleep(1)
                continue

            extra = r.get("@extra", None)
            if extra is None:
                continue

            r_id = extra.get("req_id", None)
            if r_id is None:
                continue
            try:
                while not self._queue.empty():
                    ev: Optional[ResponseEvent] = self._queue.get_nowait()
                    self._queue.task_done()
                    events[ev.request_id] = ev
            except queue.Empty:
                pass

            ev = events.pop(r_id, None)
            if ev is None:
                continue

            ev.set_data(Result(r, None))

    def _on_log_message_callback(self, verbosity_level: int, message: str):
        if verbosity_level == 0:
            self._log.critical("TDLib message: %s", message)
        elif verbosity_level == 1:
            self._log.error("TDLib message: %s", message)
        elif verbosity_level == 2:
            self._log.warning("TDLib message: %s", message)
        elif verbosity_level == 3:
            self._log.info(("TDLib message: %s", message))
        elif verbosity_level == 4:
            self._log.debug(("TDLib message: %s", message))
        else:
            self._log.info(
                ("TDLib message level %d. Message %s", verbosity_level, message)
            )

    def request(self, query: dict) -> Result:
        if not self._client_id:
            return Result(data=None, error={"error": "not logged in"})
        if self._stopped:
            return Result(None, error={"error": "client is stopped"})

        r_id = "{}_{}".format(datetime.datetime.utcnow().timestamp(), randint(0, 99999))
        query["@extra"] = {"req_id": r_id}
        ev = ResponseEvent(r_id)
        self._queue.put_nowait(ev)
        self._send(query)
        ev.wait()
        r = ev.get_data()
        if r.error:
            return r

        if "@type" not in r.update:
            return Result(None, r.update)

        if r.update["@type"] == "error":
            return Result(None, r.update)

        return r

    def _send(self, query: Dict[str, Any]):
        q = json.dumps(query).encode("utf-8")
        self._td_send(self._client_id, q)

    def close(self):
        if not self._client_id:
            return
        if self._stopped:
            return
        self._auth = False
        self._stopped = True
        self._responser.join()
        self._responser = None
        self._send({"@type": "close"})
        self._send(get_authorization_state())
        while True:
            event = self._receive()
            if not event:
                continue
            if "@type" in event:
                if event["@type"] == "error":
                    self._log.error("Got error from TDlib: %s", event)
                    break
            if "authorization_state" not in event:
                continue
            state = event["authorization_state"]["@type"]
            if state == "authorizationStateClosed":
                break
            time.sleep(1)

        self._client_id = None

    def login(
        self, get_code: Callable[[str], str], get_password: Callable[[str], str]
    ) -> bool:
        self._client_id = self._td_create_client_id()
        self._td_execute(json.dumps(set_log_verbosity_level(2)).encode("utf-8"))
        self._get_code_fn = get_code
        self._get_password_fn = get_password
        self._send(get_authorization_state())
        while True:
            event = self._receive()
            if not event:
                continue

            if "@type" in event:
                if event["@type"] == "error":
                    self._log.error("Got error from TDlib: %s", event)
                    return False

            if "authorization_state" not in event:
                continue

            state = event["authorization_state"]["@type"]

            if state == "authorizationStateClosed":
                return False
            if state == "authorizationStateClosing":
                return False

            if state == "authorizationStateWaitTdlibParameters":
                self._send(
                    set_tdlib_parameters(self._app_id, self._app_hash, self._db_path)
                )
                continue

            if state == "authorizationStateWaitCode":
                self._send(check_authentication_code(self._get_code_fn(self._phone)))
                continue

            if state == "authorizationStateWaitPhoneNumber":
                self._send(set_authentication_phone_number(self._phone))
                continue

            if state == "authorizationStateWaitEncryptionKey":
                self._send(check_database_encryption_key(self._db_key))
                continue

            if state == "authorizationStateWaitRegistration":
                return False

            if state == "authorizationStateWaitPassword":
                self._send(
                    check_authentication_password(self._get_password_fn(self._phone))
                )
                continue

            if state == "authorizationStateReady":
                self._auth = True
                return True

            self._log.critical("Unknown auth state: %s. %s", state, event)

            break

        return False

    def _receive(self) -> Optional[Dict]:
        resp = self._td_receive(1.0)
        if not resp:
            return resp

        return json.loads(resp.decode("utf-8"))

    def run(self):
        self._stopped = False
        self._responser = Thread(target=self._listen_responses)
        self._responser.start()
