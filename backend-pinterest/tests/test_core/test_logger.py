import inspect
import logging
from pathlib import Path

from core.logger import LOG_FORMAT, logger


def test_logger_format_uses_call_site_path(caplog):
    caplog.set_level(logging.ERROR, logger=logger.name)

    expected_line = _emit_log()

    record = caplog.records[0]
    formatted = logging.Formatter(LOG_FORMAT).format(record)

    assert Path(record.pathname).resolve() == Path(__file__).resolve()
    assert f"{record.pathname}:{expected_line}" in formatted
    assert "core.logger" not in formatted


def _emit_log():
    expected_line = inspect.currentframe().f_lineno + 1
    logger.error("call-site check")
    return expected_line
