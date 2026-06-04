from __future__ import annotations

from vibe.core.types import LLMMessage, Role
from vibe.core.utils.tokens import approx_token_count, truncate_middle_to_tokens

COMPACT_USER_MESSAGE_MAX_TOKENS = 20_000


def _find_preceding_assistant(
    messages: list[LLMMessage], user_index: int
) -> LLMMessage | None:
    """Find the nearest non-injected assistant message before the user message at `user_index`.

    Skips tool messages. Returns None if no such message exists (e.g., first
    message in the conversation).
    """
    for i in range(user_index - 1, -1, -1):
        msg = messages[i]
        if (
            msg.role == Role.assistant
            and not msg.injected
            and isinstance(msg.content, str)
            and msg.content
        ):
            return msg
        if msg.role == Role.user:
            break
    return None


def collect_prior_context(
    messages: list[LLMMessage],
    summary_prefix: str,
    max_tokens: int = COMPACT_USER_MESSAGE_MAX_TOKENS,
) -> list[LLMMessage]:
    """Pick user messages and their preceding assistant messages to preserve through compaction.

    Walks newest-first within a token budget, dropping system-internal
    injections and prior compaction summaries, middle-truncating the message
    that spills over. For each preserved user message, also includes the
    immediately preceding assistant response. Returns kept messages in
    chronological order.
    """
    candidates = [
        m
        for m in messages
        if m.role == Role.user
        and not m.injected
        and isinstance(m.content, str)
        and m.content
        and not m.content.startswith(summary_prefix)
    ]

    def _injected_user(text: str) -> LLMMessage:
        return LLMMessage(role=Role.user, content=text, injected=True)

    selected: list[LLMMessage] = []
    remaining = max_tokens
    for m in reversed(candidates):
        if remaining <= 0:
            break
        user_index = messages.index(m)
        assistant = _find_preceding_assistant(messages, user_index)

        content = m.content
        assert isinstance(content, str)
        user_cost = approx_token_count(content)
        assistant_cost = (
            approx_token_count(assistant.content)
            if assistant and isinstance(assistant.content, str)
            else 0
        )

        if user_cost + assistant_cost <= remaining:
            pair = (
                [
                    LLMMessage(
                        role=Role.assistant, content=assistant.content, injected=True
                    )
                ]
                if assistant is not None
                else []
            ) + [_injected_user(content)]
            selected = pair + selected
            remaining -= user_cost + assistant_cost
        elif user_cost <= remaining:
            selected = [_injected_user(content)] + selected
            remaining -= user_cost
        else:
            selected = [
                _injected_user(truncate_middle_to_tokens(content, remaining))
            ] + selected
            remaining = 0

    return selected
