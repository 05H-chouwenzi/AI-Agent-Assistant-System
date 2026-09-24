"""Request-scoped context used by tools that need caller identity."""
from contextvars import ContextVar


current_user_id: ContextVar[int | None] = ContextVar("current_user_id", default=None)


def set_current_user_id(user_id: int):
    return current_user_id.set(user_id)


def get_current_user_id() -> int | None:
    return current_user_id.get()


def reset_current_user_id(token) -> None:
    current_user_id.reset(token)
