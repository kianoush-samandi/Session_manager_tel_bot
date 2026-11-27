import pytest

from command_input import InputError, command_argument, parse_new_session, parse_session_edits
from config import ConfigError, load_bot_token


def test_token_is_read_and_trimmed(tmp_path):
    token_file = tmp_path / "token-file.txt"
    token_file.write_text("\n  123:abc  \n", encoding="utf-8")
    assert load_bot_token(token_file) == "123:abc"


@pytest.mark.parametrize("content", [None, "", "   \n\n"])
def test_missing_or_empty_token_file_fails_clearly(tmp_path, content):
    token_file = tmp_path / "token-file.txt"
    if content is not None:
        token_file.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_bot_token(token_file)


def test_command_argument_accepts_newline_after_command():
    assert command_argument("/setalias\nکاپیتان") == "کاپیتان"
    assert command_argument("/setalias") == ""


def test_parse_new_session():
    parsed = parse_new_session("/newsession جمعه 20:00 | زمین | ۱۰ | 3")
    assert (parsed.place, parsed.max_main, parsed.max_reserve) == ("زمین", 10, 3)


@pytest.mark.parametrize(
    "text",
    ["/newsession", "/newsession جمعه 20:00 | زمین | 10", "/newsession جمعه 20:00 | زمین | ده | 3", "/newsession فردا | زمین | 10 | 3"],
)
def test_parse_new_session_rejects_bad_input(text):
    with pytest.raises(InputError):
        parse_new_session(text)


def test_parse_session_edits():
    assert parse_session_edits("/editsession مکان=زمین ۲ | حداکثر نفر=12") == {"place": "زمین ۲", "max_main": 12}
    with pytest.raises(InputError):
        parse_session_edits("/editsession رنگ=قرمز")
