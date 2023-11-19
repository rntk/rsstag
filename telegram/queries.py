import base64
from typing import List, Dict, Any


def set_log_verbosity_level(level: int) -> Dict[str, Any]:
    return {
        "@type": "setLogVerbosityLevel",
        "new_verbosity_level": level,
    }

def get_chat(chat_id: int) -> Dict[str, Any]:
    return {"@type": "getChat", "chat_id": chat_id}

def get_chats_(offset_order: int = 0, offset_chat_id: int = 0, limit: int = 100) -> Dict[str, Any]:
    return {
        "@type": "getChats",
        "offset_order": offset_order,
        "offset_chat_id": offset_chat_id,
        "limit": limit,
    }

def get_chats(limit: int = 100) -> Dict[str, Any]:
    return {
        "@type": "getChats",
        "chat_list": None,
        "limit": limit,
    }

def get_chat_history(
    chat_id: int,
    limit: int = 1000,
    from_message_id: int = 0,
    offset: int = 0,
    only_local: bool = False,
) -> Dict[str, Any]:
    return {
        "@type": "getChatHistory",
        "chat_id": chat_id,
        "limit": limit,
        "from_message_id": from_message_id,
        "offset": offset,
        "only_local": only_local,
    }

def get_message_link(chat_id: int, message_id: int, for_album: bool = False, for_comment: bool = False) -> Dict[str, Any]:
    return {
        "@type": "getMessageLink",
        "chat_id": chat_id,
        "message_id": message_id,
        "for_album": for_album,
        "for_comment": for_comment
    }

def open_chat(chat_id: int):
    return {"@type": "openChat", "chat_id": chat_id}

def close_chat(chat_id: int):
    return {"@type": "closeChat", "chat_id": chat_id}

def search_channel(channel_name: str):
    return {"@type": "searchPublicChat", "username": channel_name}

def view_messages(chat_id: int, ids: List[int], force_read: bool = False) -> Dict[str, Any]:
    return {
        "@type": "viewMessages",
        "chat_id": chat_id,
        "message_ids": ids,
        "force_read": force_read,
        "message_thread_id": 0
    }

def get_authorization_state() -> Dict[str, Any]:
    return {"@type": "getAuthorizationState"}

def check_authentication_code(code: str) -> Dict[str, Any]:
    return {"@type": "checkAuthenticationCode", "code": code}

def check_authentication_password(code: str) -> Dict[str, Any]:
    return {"@type": "checkAuthenticationPassword", "password": code}

def set_tdlib_parameters(app_id: int, app_hash: str, db_path: str) -> Dict[str, Any]:
    return {
        "@type": "setTdlibParameters",
        "database_directory": db_path,
        "use_message_database": True,
        "use_secret_chats": True,
        "api_id": app_id,
        "api_hash": app_hash,
        "system_language_code": "en",
        "device_model": "rsstag",
        "application_version": "0.1",
        "enable_storage_optimizer": True
    }

def check_database_encryption_key(key: str) -> Dict[str, Any]:
    k = base64.b64encode(key.encode("utf-8")).decode()
    return {"@type": "checkDatabaseEncryptionKey", "encryption_key": k}

def set_authentication_phone_number(phone: str) -> Dict[str, Any]:
    return {"@type": "setAuthenticationPhoneNumber", "phone_number": phone}

#login
