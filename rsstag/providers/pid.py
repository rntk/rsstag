from uuid import uuid5, NAMESPACE_URL


def generate_post_pid(provider: str, feed_id: str, post_id: str) -> str:
    payload = f"{provider}:{feed_id}:{post_id}"
    return str(uuid5(NAMESPACE_URL, payload))
