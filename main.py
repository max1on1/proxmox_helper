import logging
import structlog
from fastapi import FastAPI
from api.gpu import router as gpu_router

def setup_logging():
    logging.basicConfig(
        format="%(message)s",
        stream=True,
        level=logging.DEBUG,
    )

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

setup_logging()

app = FastAPI()

app.include_router(gpu_router)
