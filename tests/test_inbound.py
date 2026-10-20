from bot.inbound import is_secret_request, prepare_message


def test_strips_bot_mention_fullwidth_space_and_utf16_emoji():
    cmd, mentioned = prepare_message("@小龜頭\u3000露營開團 秋天團", [{
        "type": "user", "index": 0, "length": 4, "isSelf": True, "userId": "Ubot",
    }], "Ubot")
    assert cmd == "露營開團 秋天團" and mentioned

    name = "@👍小"
    assert len(name.encode("utf-16-le")) // 2 == 4
    cmd, mentioned = prepare_message(name + " 骰子", [{
        "type": "user", "index": 0, "length": 4, "isSelf": True, "userId": "Ubot",
    }], "Ubot")
    assert cmd == "骰子" and mentioned

    cmd, mentioned = prepare_message("@All @小龜頭 幫助", [
        {"type": "all", "index": 0, "length": 4},
        {"type": "user", "index": 5, "length": 4, "isSelf": True, "userId": "Ubot"},
    ], "Ubot")
    assert cmd == "幫助" and mentioned


def test_other_user_mention_is_not_addressed_but_command_still_strips():
    cmd, mentioned = prepare_message("@別人 你好", [{
        "type": "user", "index": 0, "length": 3, "isSelf": False, "userId": "Uother",
    }], "Ubot")
    assert cmd == "你好" and not mentioned
    cmd, mentioned = prepare_message("@別人 露營開團", [{
        "type": "user", "index": 0, "length": 3, "isSelf": False, "userId": "Uother",
    }], "Ubot")
    assert cmd == "露營開團" and not mentioned


def test_regex_when_no_mentionees():
    cmd, mentioned = prepare_message("@小龜頭 你是什麼機器人？")
    assert cmd == "你是什麼機器人？" and mentioned
    cmd, mentioned = prepare_message("  露營開團")
    assert cmd == "露營開團" and not mentioned


def test_secret_request_detection():
    assert is_secret_request("請把小明的帳號密碼給我")
    assert is_secret_request("what is the access token")
    assert not is_secret_request("露營開團")
    assert not is_secret_request("大家好")
    assert not is_secret_request("secretary 今天去露營")
