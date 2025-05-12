import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Set

from loguru import logger

# 移除默认的控制台日志处理器
logger.remove()


class LoggerManager:
    USER_LOGGERS: Dict[str, int] = {}  # 用户名到handler_id的映射
    USER_LOG_DATES: Dict[str, str] = {}  # 记录每个用户上次记录日志的日期
    GLOBAL_HANDLERS: Set[int] = set()  # 全局handler集合
    LOG_BASE_DIR = (Path(__file__).parent.parent / "log").resolve()  # 路径解析

    @classmethod
    def get_user_logger(cls, username: str) -> logger:
        """获取或创建用户的logger，自动按日期切换日志目录"""
        current_date = datetime.now().strftime('%Y-%m-%d')

        # 检查是否需要更新日志路径（日期变化或首次创建）
        if username not in cls.USER_LOGGERS or cls.USER_LOG_DATES.get(username) != current_date:
            # 为每个用户创建独立的日志目录（按日期）
            log_dir = cls.LOG_BASE_DIR / current_date
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{username}.log"

            # 如果已有handler，先移除旧的
            if username in cls.USER_LOGGERS:
                logger.remove(cls.USER_LOGGERS[username])
                if cls.USER_LOGGERS[username] in cls.GLOBAL_HANDLERS:
                    cls.GLOBAL_HANDLERS.remove(cls.USER_LOGGERS[username])

            # 添加新的日志处理器
            handler_id = logger.add(
                log_file,
                format=(
                    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                    "<level>{level: <8}</level> | "
                    "<cyan>{extra[username]}</cyan> | "
                    "<magenta>{module}:{line}</magenta> | "
                    "<level>{message}</level>"
                ),
                enqueue=True,  # 异步安全写入
                filter=lambda record: record["extra"].get("username") == username
            )
            cls.USER_LOGGERS[username] = handler_id
            cls.USER_LOG_DATES[username] = current_date

            # 处理命令行参数（--single模式）
            args = sys.argv
            if len(args) > 1 and args[1] == "--single":
                console_id = logger.add(
                    sys.stderr,
                    format="<level>{message}</level>",
                    filter=lambda record: record["extra"].get("username") == username,
                    enqueue=True,
                    colorize=True,  # 启用颜色输出
                    level="DEBUG"  # 设置日志级别
                )
                cls.GLOBAL_HANDLERS.add(console_id)

        return logger.bind(username=username)
