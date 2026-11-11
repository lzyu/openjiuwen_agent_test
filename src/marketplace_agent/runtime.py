"""Configure SDK logging before importing the harness."""
import os


def configure_runtime():
    os.environ.setdefault("IS_SENSITIVE", "true")
    from openjiuwen.core.common.logging.log_config import configure_log_config
    configure_log_config({
        "backend": "default", "level": "WARNING", "output": ["console"],
        "interface_output": ["console"], "performance_output": ["console"],
        "loggers": {"llm": {"level": "WARNING"}},
    })
