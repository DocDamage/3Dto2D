import json
import logging
import sys
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_json_log_formatter_emits_structured_record():
    from services.logging_service import JsonLogFormatter

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    logger = logging.getLogger("spriteforge.test.logging")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    logger.info("hello", extra={"job_id": "job-1"})

    data = json.loads(stream.getvalue())
    assert data["level"] == "INFO"
    assert data["logger"] == "spriteforge.test.logging"
    assert data["message"] == "hello"
    assert data["job_id"] == "job-1"


def test_configure_logging_sets_named_spriteforge_logger_level():
    from services.logging_service import configure_logging, get_logger

    configure_logging({"logging": {"level": "DEBUG", "json": False}})
    logger = get_logger("project_service")

    assert logger.name == "spriteforge.project_service"
    assert logger.getEffectiveLevel() == logging.DEBUG


def test_project_service_uses_named_logger():
    import services.project_service as project_service

    assert project_service.logger.name == "spriteforge.project_service"
