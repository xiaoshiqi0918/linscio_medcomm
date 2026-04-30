"""SaaS 用户 LLM provider 偏好 — contextvar 传播。

在请求入口设置，所有下游 LLM 调用自动读取，无需逐层透传。
值可以是：
  - str: 全局覆盖（如请求头 X-Preferred-Provider）
  - dict[str, str]: 按工作流组覆盖（如用户 DB 偏好 {"writing": "openai", ...}）
"""
import contextvars

current_preferred_provider: contextvars.ContextVar[str | dict | None] = (
    contextvars.ContextVar("current_preferred_provider", default=None)
)
