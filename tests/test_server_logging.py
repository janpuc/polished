import logging

from polished.server import HideCallbackQuery


def record(path: str) -> logging.LogRecord:
    return logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("10.0.0.1:1234", "GET", path, "1.1", 302),
        None,
    )


def test_the_callback_query_never_reaches_the_access_log():
    entry = record("/auth/callback?code=pocket_id_ac_secret&state=abc")
    assert HideCallbackQuery().filter(entry)
    assert "secret" not in entry.getMessage() and "/auth/callback?…" in entry.getMessage()


def test_other_paths_keep_their_query():
    entry = record("/shades?q=spirit")
    HideCallbackQuery().filter(entry)
    assert "/shades?q=spirit" in entry.getMessage()
