from __future__ import annotations

from vibe.core.types import LLMMessage, Role
from vibe.core.utils.tokens import approx_token_count, truncate_middle_to_tokens

COMPACT_USER_MESSAGE_MAX_TOKENS = 50_000


def _find_preceding_assistants(
    messages: list[LLMMessage], user_index: int, summary_prefix: str
) -> list[LLMMessage]:
    """Find all consecutive non-injected assistant messages before the user message at `user_index`.

    Skips tool messages and injected user messages. Returns messages in
    reverse chronological order (nearest first).
    """
    assistants: list[LLMMessage] = []
    for i in range(user_index - 1, -1, -1):
        msg = messages[i]
        if (
            msg.role == Role.assistant
            and not msg.injected
            and isinstance(msg.content, str)
            and msg.content
        ):
            assistants.append(msg)
            continue
        if msg.role == Role.user and not _would_be_filtered(msg, summary_prefix):
            break
    return assistants


def _would_be_filtered(msg: LLMMessage, summary_prefix: str) -> bool:
    """Return True if a user message would be excluded from prior context."""
    if msg.injected:
        return True
    if (
        msg.content
        and isinstance(msg.content, str)
        and msg.content.startswith(summary_prefix)
    ):
        return True
    return False


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
        assistants = _find_preceding_assistants(messages, user_index, summary_prefix)

        content = m.content
        assert isinstance(content, str)
        user_cost = approx_token_count(content)
        assistant_cost = sum(
            approx_token_count(a.content)
            for a in assistants
            if isinstance(a.content, str)
        )

        if user_cost + assistant_cost <= remaining:
            pair = [
                LLMMessage(role=Role.assistant, content=a.content, injected=True)
                for a in reversed(assistants)
            ] + [_injected_user(content)]
            selected = pair + selected
            remaining -= user_cost + assistant_cost
        elif user_cost <= remaining:
            assistant_space = remaining - user_cost
            if assistant_space > 0 and assistants:
                assistant_contents = []
                for a in reversed(assistants):
                    if isinstance(a.content, str) and assistant_space > 0:
                        assistant_contents.append(
                            LLMMessage(
                                role=Role.assistant,
                                content=truncate_middle_to_tokens(
                                    a.content, assistant_space
                                ),
                                injected=True,
                            )
                        )
                        assistant_space -= approx_token_count(a.content)
                if assistant_contents:
                    selected = assistant_contents + [_injected_user(content)] + selected
                else:
                    selected = [_injected_user(content)] + selected
                remaining = 0
            else:
                selected = [_injected_user(content)] + selected
                remaining = 0
        else:
            selected = [
                _injected_user(truncate_middle_to_tokens(content, remaining))
            ] + selected
            remaining = 0

    return selected
