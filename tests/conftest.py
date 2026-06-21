"""pytest 公共配置：注册自定义命令行开关。"""

from __future__ import annotations


def pytest_addoption(parser):
    parser.addoption(
        "--run-real-llm",
        action="store_true",
        default=False,
        help="启用会调用真实模型 API 并产生副作用的验收测试。",
    )
