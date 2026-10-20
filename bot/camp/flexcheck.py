"""檢查要送給 LINE 的訊息是否符合公開的長度與結構限制。"""
import re

from ..inbound import u16_len

MAX_MESSAGES = 5
MAX_QUICK_REPLY = 13
MAX_LABEL = 20
MAX_DATA = 300
MAX_DISPLAY = 300
MAX_ALT = 400
MAX_TEXT = 5000
MAX_BOX = 10

BUBBLE_SIZES = {"nano", "micro", "deca", "hecto", "kilo", "mega", "giga"}
BUTTON_STYLES = {"primary", "secondary", "link"}
BUTTON_HEIGHTS = {"sm", "md"}
BOX_LAYOUTS = {"horizontal", "vertical", "baseline"}
DT_MODES = {"date", "time", "datetime"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def clip(text, n):
    text = "" if text is None else str(text)
    if u16_len(text) <= n:
        return text
    out = []
    acc = 0
    for ch in text:
        w = 2 if ord(ch) > 0xFFFF else 1
        if acc + w > n - 1:
            break
        out.append(ch)
        acc += w
    return "".join(out) + "…"


def validate_reply(messages):
    errors = []
    if not messages:
        return ["沒有訊息"]
    if len(messages) > MAX_MESSAGES:
        errors.append(f"訊息超過 {MAX_MESSAGES} 則（{len(messages)}）")
    for i, msg in enumerate(messages):
        for err in validate_message(msg):
            errors.append(f"messages[{i}]: {err}")
    return errors


def validate_message(msg):
    if hasattr(msg, "to_dict"):
        msg = msg.to_dict()
    if not isinstance(msg, dict):
        return ["訊息不是物件"]
    kind = msg.get("type")
    errors = []
    if kind == "text":
        text = msg.get("text") or ""
        if not text:
            errors.append("文字是空的")
        if u16_len(text) > MAX_TEXT:
            errors.append(f"文字超過 {MAX_TEXT}")
    elif kind == "flex":
        alt = msg.get("altText") or ""
        if not alt:
            errors.append("altText 是空的")
        elif u16_len(alt) > MAX_ALT:
            errors.append(f"altText 超過 {MAX_ALT}")
        errors.extend(_container(msg.get("contents"), "contents"))
    else:
        errors.append(f"不支援的 type={kind}")
    if msg.get("quickReply"):
        errors.extend(_quick(msg["quickReply"]))
    return errors


def _container(node, path):
    if not isinstance(node, dict):
        return [f"{path} 不是物件"]
    kind = node.get("type")
    if kind == "bubble":
        return _bubble(node, path)
    if kind == "carousel":
        bubbles = node.get("contents") or []
        errors = []
        if not bubbles or len(bubbles) > 12:
            errors.append(f"{path} carousel 氣泡數須為 1～12")
        for i, b in enumerate(bubbles):
            errors.extend(_bubble(b, f"{path}[{i}]"))
        return errors
    return [f"{path} type={kind} 不是 bubble/carousel"]


def _bubble(node, path):
    errors = []
    if node.get("type") not in (None, "bubble"):
        errors.append(f"{path} 不是 bubble")
    if node.get("size") and node["size"] not in BUBBLE_SIZES:
        errors.append(f"{path} size={node.get('size')}")
    for part in ("header", "body", "footer"):
        if node.get(part):
            errors.extend(_component(node[part], f"{path}.{part}"))
    return errors


def _component(node, path):
    if not isinstance(node, dict):
        return [f"{path} 不是元件"]
    kind = node.get("type")
    errors = []
    if kind == "box":
        if node.get("layout") not in BOX_LAYOUTS:
            errors.append(f"{path} layout={node.get('layout')}")
        contents = node.get("contents")
        if not isinstance(contents, list) or not contents:
            errors.append(f"{path} 內容是空的")
        else:
            if len(contents) > MAX_BOX:
                errors.append(f"{path} 內容超過 {MAX_BOX} 個（{len(contents)}）")
            for i, child in enumerate(contents):
                errors.extend(_component(child, f"{path}[{i}]"))
    elif kind == "text":
        if not node.get("text"):
            errors.append(f"{path} 文字是空的")
    elif kind == "button":
        if node.get("style") and node["style"] not in BUTTON_STYLES:
            errors.append(f"{path} style={node.get('style')}")
        if node.get("height") and node["height"] not in BUTTON_HEIGHTS:
            errors.append(f"{path} height={node.get('height')}")
        errors.extend(_action(node.get("action"), path))
    elif kind == "separator":
        pass
    elif kind:
        errors.append(f"{path} 未檢查的元件 type={kind}")
    if kind != "button" and node.get("action"):
        errors.extend(_action(node["action"], path + ".action"))
    return errors


def _quick(qr):
    items = qr.get("items") if isinstance(qr, dict) else None
    if not items:
        return ["quickReply 是空的"]
    errors = []
    if len(items) > MAX_QUICK_REPLY:
        errors.append(f"quickReply 超過 {MAX_QUICK_REPLY} 個（{len(items)}）")
    for i, item in enumerate(items):
        action = item.get("action") if isinstance(item, dict) else None
        errors.extend(_action(action, f"quickReply[{i}]"))
    return errors


def _action(action, path):
    if not isinstance(action, dict):
        return [f"{path} 缺少 action"]
    errors = []
    kind = action.get("type")
    label = action.get("label")
    if not label:
        errors.append(f"{path} label 是空的")
    elif u16_len(label) > MAX_LABEL:
        errors.append(f"{path} label 長度 {u16_len(label)} 超過 {MAX_LABEL}")
    data = action.get("data")
    if kind in ("postback", "datetimepicker"):
        if not data:
            errors.append(f"{path} data 是空的")
        elif u16_len(data) > MAX_DATA:
            errors.append(f"{path} data 超過 {MAX_DATA}")
    if kind == "uri":
        uri = action.get("uri") or ""
        if not uri.startswith("https://"):
            errors.append(f"{path} uri 須為 https")
    display = action.get("displayText")
    if display is not None and u16_len(display) > MAX_DISPLAY:
        errors.append(f"{path} displayText 超過 {MAX_DISPLAY}")
    if kind == "datetimepicker":
        if action.get("mode") not in DT_MODES:
            errors.append(f"{path} mode={action.get('mode')}")
        if action.get("mode") == "date":
            for key in ("initial", "min", "max"):
                val = action.get(key)
                if val and not DATE_RE.match(val):
                    errors.append(f"{path} {key}={val}")
    return errors
