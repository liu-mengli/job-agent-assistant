import sys

from loguru import logger as _logger

from config import settings

# 移除默认 handler
_logger.remove()

# 开发环境：彩色终端输出
_logger.add(
    sys.stdout,
    colorize=True,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>[{extra[request_id]:>3}]</cyan> | <level>{message}</level>",
    level="DEBUG" if settings.DEBUG else "INFO",
)

# 生产环境：JSON 日志文件（按大小轮转）
_logger.add(
    "logs/app.json.log",
    format="{message}",
    serialize=True,
    rotation="10 MB",
    retention="7 days",
    level="INFO",
)

# 业务模块统一入口（request_id 默认 "-"，由中间件通过 contextualize 覆盖）
_logger.configure(extra={"request_id": "-"})
logger = _logger

__all__ = ["logger"]
