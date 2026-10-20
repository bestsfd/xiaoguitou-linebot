"""把 LINE 群組裡開頭的 @提及 拿掉，再拿去對指令。不讀取、不回傳任何密鑰。"""
import os
import re

REFUSAL = "這個我幫不了，我不會提供任何人的帳號密碼或密鑰。"

_WS = " \t\r\n\u3000\u00a0"
_SECRET = re.compile(
    r"(?i)(密碼|密码|金鑰|密钥|環境變數|环境变量|\.env|"
    r"(?<![A-Za-z0-9])(?:password|passwd|passcode|secret|api[-_ ]?key|"
    r"access[-_ ]?token|channel[-_ ]?secret)(?![A-Za-z0-9]))"
)
_LEADING_AT = re.compile(r"^@\S+")


def u16_len(text):
    return len((text or "").encode("utf-16-le")) // 2


def _u16_width(ch):
    return 2 if ord(ch) > 0xFFFF else 1


def py_index_at_u16(text, u16_pos):
    """LINE 的 index/length 以 UTF-16 code unit 計。"""
    acc = 0
    for i, ch in enumerate(text):
        if acc == u16_pos:
            return i
        acc += _u16_width(ch)
        if acc > u16_pos:
            return i
    return len(text) if acc == u16_pos else None


def _field(obj, name, alias=None):
    if obj is None:
        return None
    if isinstance(obj, dict):
        if alias and alias in obj:
            return obj[alias]
        return obj.get(name)
    return getattr(obj, name, None)


def squash(text):
    text = (text or "").replace("\u3000", " ").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _regex_strip_at(text):
    s = text or ""
    changed = False
    while True:
        m = _LEADING_AT.match(s.lstrip(_WS))
        if not m:
            break
        lead = len(s) - len(s.lstrip(_WS))
        s = s[lead + (m.end() - m.start()):]
        changed = True
    return s, changed


def strip_leading_mentions(text, mentionees):
    """依 mentionees 的 index/length 移除開頭連續提及。回傳 (剩下的文字, 有沒有拿掉)。"""
    text = text or ""
    spans = []
    for m in mentionees or []:
        idx, length = _field(m, "index"), _field(m, "length")
        if idx is None or length is None:
            continue
        spans.append((int(idx), int(length)))
    if not spans:
        return text, False
    spans.sort()
    cursor = 0
    used = False
    while True:
        p = py_index_at_u16(text, cursor)
        if p is None:
            break
        while p < len(text) and text[p] in _WS:
            cursor += _u16_width(text[p])
            p += 1
        hit = next((ln for i, ln in spans if i == cursor), None)
        if hit is None:
            break
        cursor += hit
        used = True
    p = py_index_at_u16(text, cursor)
    if p is None:
        return text, used
    return text[p:], used


def bot_was_mentioned(mentionees, destination):
    for m in mentionees or []:
        if _field(m, "is_self", "isSelf") is True:
            return True
        if (_field(m, "type") or "") == "all":
            return True
        uid = _field(m, "user_id", "userId")
        if destination and uid and uid == destination:
            return True
    return False


def prepare_message(text, mentionees=None, destination=None):
    """回傳 (指令文字, 是否在呼叫這個機器人)。

    有 mentionees 就用 index/length 拿掉開頭提及；否則用正則拿掉開頭的 @名稱。
    全形空白會先當成一般空白。
    """
    raw = text or ""
    mentioned = bot_was_mentioned(mentionees, destination)
    if mentionees:
        rest, _used = strip_leading_mentions(raw, mentionees)
        rest, _ = _regex_strip_at(rest)
    else:
        rest, regex_hit = _regex_strip_at(raw)
        mentioned = mentioned or regex_hit
    return squash(rest), mentioned


def is_secret_request(text):
    return bool(_SECRET.search(text or ""))


def redact(text):
    """日誌用。去掉環境變數裡的密鑰與 Bearer，避免寫進 log。"""
    s = "" if text is None else str(text)
    for key in ("LINE_CHANNEL_SECRET", "LINE_CHANNEL_ACCESS_TOKEN"):
        val = os.environ.get(key) or ""
        if len(val) >= 4:
            s = s.replace(val, "[redacted]")
    s = re.sub(r"(?i)(bearer\s+)\S+", r"\1[redacted]", s)
    s = re.sub(r"(?i)(access_token=)[^&\s]+", r"\1[redacted]", s)
    return s
