"""策略注册表 - 内置策略 + 用户自定义策略

用户策略以 .py 文件保存在 user_strategies 目录, 启动时或创建后通过 importlib 动态加载。
"""
import importlib.util
import os
from loguru import logger

from .examples import BUILTIN_STRATEGIES

# 用户策略目录 (docker: /app/user_strategies 挂载 ./strategies; 本地开发兜底)
USER_STRATEGIES_DIR = os.getenv(
    "USER_STRATEGIES_DIR",
    "/app/user_strategies" if os.path.isdir("/app/user_strategies") else "strategies",
)

USER_STRATEGIES: dict = {}


def load_user_strategies() -> dict:
    """从目录加载用户策略文件, 返回 {name: class}

    注意: 原地清空再填充, 保证外部 `from .registry import USER_STRATEGIES`
    拿到的引用仍然指向最新内容 (不能重新赋值, 否则外部引用会变旧)。
    """
    loaded: dict = {}
    if os.path.isdir(USER_STRATEGIES_DIR):
        for fname in sorted(os.listdir(USER_STRATEGIES_DIR)):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            path = os.path.join(USER_STRATEGIES_DIR, fname)
            try:
                mod_name = f"user_strategy_{fname[:-3]}"
                spec = importlib.util.spec_from_file_location(mod_name, path)
                if not spec or not spec.loader:
                    continue
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                for attr in dir(mod):
                    cls = getattr(mod, attr)
                    if (isinstance(cls, type) and cls.__name__ != "BaseStrategy"
                            and getattr(cls, "name", None) and hasattr(cls, "on_bar")):
                        loaded[cls.name] = cls
            except Exception as e:
                logger.error(f"加载用户策略失败 {fname}: {e}")

    USER_STRATEGIES.clear()
    USER_STRATEGIES.update(loaded)
    if USER_STRATEGIES:
        logger.info(f"用户策略已加载: {list(USER_STRATEGIES.keys())}")
    return USER_STRATEGIES


def get_all_strategies() -> dict:
    """内置 + 用户策略合并"""
    result = dict(BUILTIN_STRATEGIES)
    result.update(USER_STRATEGIES)
    return result


def build_strategy_module(name: str, description: str, code: str) -> str:
    """把用户提供的 on_bar 函数体包装成一个完整策略模块源码

    Args:
        name: 策略名 (已校验合法标识符)
        description: 策略描述
        code: on_bar 函数体 (用户输入, 无缩进)
    """
    body = "\n".join("        " + line if line.strip() else line for line in code.splitlines())
    return f'''"""用户自定义策略: {name}"""
from src.strategies.base import BaseStrategy, BarData, Action, SignalData
from typing import Optional


class UserStrategy(BaseStrategy):
    name = "{name}"
    author = "user"
    description = "{description}"
    requires_ai = True
    requires_confirmation = True
    max_position_pct = 0.1
    stop_loss_pct = 5.0
    take_profit_pct = 10.0

    def on_bar(self, bar: BarData) -> Optional[SignalData]:
{body}
'''


def save_user_strategy(name: str, description: str, code: str) -> str:
    """编译校验并保存用户策略, 返回文件路径"""
    source = build_strategy_module(name, description, code)
    try:
        compile(source, f"<strategy_{name}>", "exec")
    except SyntaxError as e:
        raise ValueError(f"策略代码语法错误: {e}")

    os.makedirs(USER_STRATEGIES_DIR, exist_ok=True)
    path = os.path.join(USER_STRATEGIES_DIR, f"{name}.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(source)

    # 重新加载注册表, 让新策略立即生效
    load_user_strategies()
    if name not in USER_STRATEGIES:
        raise ValueError("策略创建失败: 代码未能编译为可用的策略类")
    return path
