import os
import json
import time
import datetime
import logging
from ctypes import *
from typing import Callable, Dict, Any, Optional

from .queries import (
    set_log_verbosity_level,
    set_tdlib_parameters,
    get_authorization_state,
    check_authentication_code,
    set_authentication_phone_number,
    check_database_encryption_key
)

class Result:
    def __init__(self, data: Optional[dict], error: Optional[dict]):
        self.update = data
        self.error = error

class Telegram:
    def __init__(self, app_id: int, app_hash: str, phone: str, db_path: str, db_key: str, tdjson_path: str = ""):
        self._app_id = app_id
        self._app_hash = app_hash
        self._phone = phone
        self._db_path = db_path
        if tdjson_path == "":
            tdjson_path = os.path.join(os.path.dirname(__file__), "lib", "libtdjson.so")
        self._tdjson_path = tdjson_path
        self._get_code_fn = None
        self._db_key = db_key

        self._log: logging.Logger = logging.getLogger("telegram")
        self._tdjson = CDLL(tdjson_path)

        self._td_create_client_id = self._tdjson.td_create_client_id
        self._td_create_client_id.restype = c_int
        self._td_create_client_id.argtypes = []

        self._td_json_client_destroy = self._tdjson.td_json_client_destroy
        self._td_json_client_destroy.restype = None
        self._td_json_client_destroy.argtypes = [c_int]

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
        self._c_on_log_message_callback = log_message_callback_type(self._on_log_message_callback)
        self._td_set_log_message_callback(2, self._c_on_log_message_callback)

        self._client_id = self._td_create_client_id()

        self._execute(set_log_verbosity_level(1))

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
            self._log.info(("TDLib message level %d. Message %s", verbosity_level, message))

    def request(self, query: dict) -> Result:
        r_id = datetime.datetime.utcnow().timestamp()
        query["@extra"] = {"req_id": r_id}
        self._send(query)
        while True:
            resp = self._td_receive(1.0)
            if not resp:
                time.sleep(1)
                continue

            r = json.loads(resp.decode("utf-8"))
            if "@type" not in r:
                return Result(None, r)

            if r["@type"] == "error":
                return Result(None, r)

            if "@extra" not in r:
                continue

            if r["@extra"].get("req_id") == r_id:
                return Result(r, None)

    def _execute(self, query: dict) -> Optional[dict]:
        q = json.dumps(query).encode("utf-8")
        result = self._td_execute(q)
        if result:
            result = json.loads(result.decode("utf-8"))

        return result

    def _send(self, query: Dict[str, Any]):
        q = json.dumps(query).encode("utf-8")
        self._td_send(self._client_id, q)

    def close(self):
        self._execute({"@type": "close"})
        time.sleep(2)

    def login(self, get_code: Callable[[str], str]) -> bool:
        self._get_code_fn = get_code
        self._send(get_authorization_state())
        while True:
            raw_event = self._td_receive(1.0)
            if not raw_event:
                continue
            event = json.loads(raw_event.decode("utf-8"))
            if "@type" in event:
                if event["@type"] == "error":
                    self._log.error("Got error from TDlib: %s", raw_event)
                    return False

            if "authorization_state" not in event:
                continue

            state = event["authorization_state"]["@type"]

            if state == "authorizationStateClosed":
                return False

            if state == "authorizationStateWaitTdlibParameters":
                self._send(
                    set_tdlib_parameters(
                        self._app_id,
                        self._app_hash,
                        self._db_path
                    )
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
                return False

            if state == "authorizationStateReady":
                return True

            self._log.critical("Unknown auth state: %s. %s", state, event)

            break

        return False
