import os

from linebot.v3.messaging import (ApiClient, Configuration, MessagingApi,
                                  PushMessageRequest, ReplyMessageRequest, TextMessage)


def _api(client):
    return MessagingApi(client)


def _conf():
    return Configuration(access_token=os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", ""))


def reply(token, text):
    with ApiClient(_conf()) as c:
        _api(c).reply_message(ReplyMessageRequest(reply_token=token, messages=[TextMessage(text=text)]))


def push(to, text):
    with ApiClient(_conf()) as c:
        _api(c).push_message(PushMessageRequest(to=to, messages=[TextMessage(text=text[:5000])]))


_cache = {}


def display_name(source, user_id):
    """取得顯示名稱；失敗時用 ID 末 4 碼。"""
    key = (getattr(source, "group_id", None) or getattr(source, "room_id", None), user_id)
    if key in _cache:
        return _cache[key]
    name = None
    try:
        with ApiClient(_conf()) as c:
            api = _api(c)
            if source.type == "group":
                name = api.get_group_member_profile(source.group_id, user_id).display_name
            elif source.type == "room":
                name = api.get_room_member_profile(source.room_id, user_id).display_name
            else:
                name = api.get_profile(user_id).display_name
    except Exception:
        pass
    name = name or (user_id[-4:] if user_id else "某人")
    _cache[key] = name
    return name
