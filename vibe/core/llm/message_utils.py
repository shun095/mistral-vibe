from __future__ import annotations

from collections.abc import Sequence

from vibe.core.types import LLMMessage, Role


def merge_consecutive_user_messages(messages: Sequence[LLMMessage]) -> list[LLMMessage]:
    """Merge consecutive user messages into a single message.

    This handles cases where middleware injects messages resulting in
    consecutive user messages before sending to the API.
    """
    result: list[LLMMessage] = []
    for msg in messages:
        if result and result[-1].role == Role.user and msg.role == Role.user:
            prev_content = result[-1].content
            curr_content = msg.content
            
            # Handle multi-part content (lists with image_url)
            if isinstance(prev_content, list) or isinstance(curr_content, list):
                # Merge lists properly
                merged_list: list[dict] = []
                
                # Add previous content
                if isinstance(prev_content, list):
                    merged_list.extend(prev_content)
                elif prev_content:
                    merged_list.append({"type": "text", "text": prev_content})
                
                # Add current content
                if isinstance(curr_content, list):
                    merged_list.extend(curr_content)
                elif curr_content:
                    merged_list.append({"type": "text", "text": curr_content})
                
                merged_content = merged_list
            else:
                # Both are strings or empty
                merged_content = f"{prev_content or ''}\n\n{curr_content or ''}".strip()
            
            result[-1] = LLMMessage(
                role=Role.user, content=merged_content, message_id=result[-1].message_id
            )
        else:
            result.append(msg)

    return result
