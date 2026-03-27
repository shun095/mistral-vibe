from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from vibe.core.types import Content, LLMMessage, Role


def strip_reasoning(msg: LLMMessage) -> LLMMessage:
    if msg.role != Role.assistant or not msg.reasoning_content:
        return msg
    return msg.model_copy(
        update={"reasoning_content": None, "reasoning_signature": None}
    )


def merge_consecutive_user_messages(messages: Sequence[LLMMessage]) -> list[LLMMessage]:
    """Merge consecutive user messages into a single message.

    This handles cases where middleware injects messages resulting in
    consecutive user messages before sending to the API.
    """
    result: list[LLMMessage] = []
    for msg in messages:  # noqa: PLR1702
        if result and result[-1].role == Role.user and msg.role == Role.user:
            prev_content = result[-1].content
            curr_content = msg.content

            # Handle multi-part content (lists with image_url)
            if isinstance(prev_content, list) or isinstance(curr_content, list):
                # Merge lists properly - use cast since Content can be list[str] but we're working with list[dict]
                merged_list: list[dict[str, Any]] = []

                # Add previous content
                if isinstance(prev_content, list):
                    # prev_content is list[str] per Content type, but in practice it's list[dict] for multi-part
                    for item in prev_content:
                        if isinstance(item, dict):
                            merged_list.append(item)
                        else:
                            merged_list.append({"type": "text", "text": str(item)})
                elif prev_content:
                    merged_list.append({"type": "text", "text": prev_content})

                # Add current content
                if isinstance(curr_content, list):
                    for item in curr_content:
                        if isinstance(item, dict):
                            merged_list.append(item)
                        else:
                            merged_list.append({"type": "text", "text": str(item)})
                elif curr_content:
                    merged_list.append({"type": "text", "text": curr_content})

                # Cast to Content since we're creating multi-part content
                merged_content: Content = cast(Content, merged_list)
            else:
                # Both are strings or empty
                merged_content = f"{prev_content or ''}\n\n{curr_content or ''}".strip()

            result[-1] = LLMMessage(
                role=Role.user, content=merged_content, message_id=result[-1].message_id
            )
        else:
            result.append(msg)

    return result
