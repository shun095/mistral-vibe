"""Core type definitions that everything else depends on.

This module contains fundamental types that have no dependencies on other
submodules in the types package.
"""

from __future__ import annotations

from abc import ABC
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Iterator, Sequence
from contextlib import contextmanager
import copy
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Annotated, Any, Literal, overload
from uuid import uuid4

if TYPE_CHECKING:
    from vibe.core.tools.base import BaseTool
else:
    BaseTool = Any

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PrivateAttr,
    computed_field,
    model_validator,
)


class Backend(StrEnum):
    MISTRAL = auto()
    GENERIC = auto()


class AgentStats(BaseModel):
    steps: int = 0
    session_prompt_tokens: int = 0
    session_completion_tokens: int = 0
    tool_calls_agreed: int = 0
    tool_calls_rejected: int = 0
    tool_calls_failed: int = 0
    tool_calls_succeeded: int = 0

    context_tokens: int = 0

    last_turn_prompt_tokens: int = 0
    last_turn_completion_tokens: int = 0
    last_turn_duration: float = 0.0
    tokens_per_second: float = 0.0

    input_price_per_million: float = 0.0
    output_price_per_million: float = 0.0

    _listeners: dict[str, Callable[[AgentStats], None]] = PrivateAttr(
        default_factory=dict
    )

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if name in self._listeners:
            self._listeners[name](self)

    def trigger_listeners(self) -> None:
        for listener in self._listeners.values():
            listener(self)

    def add_listener(
        self, attr_name: str, listener: Callable[[AgentStats], None]
    ) -> None:
        self._listeners[attr_name] = listener

    @computed_field
    @property
    def session_total_llm_tokens(self) -> int:
        return self.session_prompt_tokens + self.session_completion_tokens

    @computed_field
    @property
    def last_turn_total_tokens(self) -> int:
        return self.last_turn_prompt_tokens + self.last_turn_completion_tokens

    @computed_field
    @property
    def session_cost(self) -> float:
        """Calculate the total session cost in dollars based on token usage and pricing.

        NOTE: This is a rough estimate and is worst-case scenario.
        The actual cost may be lower due to prompt caching.
        If the model changes mid-session, this uses current pricing for all tokens.
        """
        input_cost = (
            self.session_prompt_tokens / 1_000_000
        ) * self.input_price_per_million
        output_cost = (
            self.session_completion_tokens / 1_000_000
        ) * self.output_price_per_million
        return input_cost + output_cost

    def update_pricing(self, input_price: float, output_price: float) -> None:
        """Update pricing info when model changes.

        NOTE: session_cost will be recalculated using new pricing for all
        accumulated tokens. This is a known approximation when models change.
        This should not be a big issue, pricing is only used for max_price which is in
        programmatic mode, so user should not update models there.
        """
        self.input_price_per_million = input_price
        self.output_price_per_million = output_price

    def reset_context_state(self) -> None:
        """Reset context-related fields while preserving cumulative session stats.

        Used after config reload or similar operations where the context
        changes but we want to preserve session totals.
        """
        self.context_tokens = 0
        self.last_turn_prompt_tokens = 0
        self.last_turn_completion_tokens = 0
        self.last_turn_duration = 0.0
        self.tokens_per_second = 0.0

    @staticmethod
    def create_fresh(previous: AgentStats) -> AgentStats:
        fresh = AgentStats()
        fresh._listeners = previous._listeners.copy()
        return fresh


class SessionInfo(BaseModel):
    session_id: str
    start_time: str
    message_count: int
    stats: AgentStats
    save_dir: str


class SessionMetadata(BaseModel):
    session_id: str
    start_time: str
    end_time: str | None
    git_commit: str | None
    git_branch: str | None
    environment: dict[str, str | None]
    username: str


class ClientMetadata(BaseModel):
    name: str
    version: str


class EntrypointMetadata(BaseModel):
    agent_entrypoint: Literal["cli", "acp", "programmatic"]
    agent_version: str
    client_name: str
    client_version: str


StrToolChoice = Literal["auto", "none", "any", "required"]


class AvailableFunction(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]


class AvailableTool(BaseModel):
    type: Literal["function"] = "function"
    function: AvailableFunction


class FunctionCall(BaseModel):
    name: str | None = None
    arguments: str | None = None


class ToolCall(BaseModel):
    id: str | None = None
    index: int | None = None
    function: FunctionCall = Field(default_factory=FunctionCall)
    type: Literal["function"] = "function"


def _content_before(v: Any) -> str | list:
    """Convert content to a format suitable for LLM messages.

    Handles:
    - Strings: returned as-is
    - Lists with text dicts: extracts text and joins with newlines
    - Lists with image_url dicts: preserves the list format for API compatibility
    """
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        # Check if this is a multi-part content with image_url
        has_image_url = any(
            isinstance(p, dict) and p.get("type") == "image_url" for p in v
        )
        if has_image_url:
            # Preserve the list format for multi-part content with images
            return v

        # Handle simple lists of text dicts
        parts: list[str] = []
        for p in v:
            if isinstance(p, dict) and isinstance(p.get("text"), str):
                parts.append(p["text"])
            else:
                parts.append(str(p))
        return "\n".join(parts)
    return str(v)


Content = Annotated[str | list[dict | str], BeforeValidator(_content_before)]


class Role(StrEnum):
    system = auto()
    user = auto()
    assistant = auto()
    tool = auto()


class ApprovalResponse(StrEnum):
    YES = "y"
    NO = "n"


class LLMMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: Role
    content: Content | None = None
    injected: bool = False
    reasoning_content: Content | None = None
    reasoning_signature: str | None = None
    reasoning_message_id: str | None = None
    tool_calls: list[ToolCall] | None = None
    name: str | None = None
    tool_call_id: str | None = None
    message_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _from_any(cls, v: Any) -> dict[str, Any] | Any:
        if isinstance(v, dict):
            v.setdefault("content", "")
            v.setdefault("role", "assistant")
            if v.get("message_id") is None and v.get("role") != "tool":
                v["message_id"] = str(uuid4())
            if v.get("reasoning_message_id") is None and v.get("reasoning_content"):
                v["reasoning_message_id"] = str(uuid4())
            return v
        role = str(getattr(v, "role", "assistant"))
        reasoning_content = getattr(v, "reasoning_content", None)
        return {
            "role": role,
            "content": getattr(v, "content", ""),
            "reasoning_content": reasoning_content,
            "reasoning_signature": getattr(v, "reasoning_signature", None),
            "reasoning_message_id": getattr(v, "reasoning_message_id", None)
            or (str(uuid4()) if reasoning_content else None),
            "tool_calls": getattr(v, "tool_calls", None),
            "name": getattr(v, "name", None),
            "tool_call_id": getattr(v, "tool_call_id", None),
            "message_id": getattr(v, "message_id", None)
            or (str(uuid4()) if role != "tool" else None),
        }

    def __add__(self, other: LLMMessage) -> LLMMessage:
        """Careful: this is not commutative!"""
        if self.role != other.role:
            raise ValueError("Can't accumulate messages with different roles")

        if self.name != other.name:
            raise ValueError("Can't accumulate messages with different names")

        if self.tool_call_id != other.tool_call_id:
            raise ValueError("Can't accumulate messages with different tool_call_ids")

        # Handle content concatenation with type guards
        self_content = self.content if isinstance(self.content, str) else ""
        other_content = other.content if isinstance(other.content, str) else ""
        content = self_content + other_content
        if not content:
            content = None

        # Handle reasoning_content concatenation with type guards
        self_reasoning = (
            self.reasoning_content if isinstance(self.reasoning_content, str) else ""
        )
        other_reasoning = (
            other.reasoning_content if isinstance(other.reasoning_content, str) else ""
        )
        reasoning_content = self_reasoning + other_reasoning
        if not reasoning_content:
            reasoning_content = None

        reasoning_signature = (self.reasoning_signature or "") + (
            other.reasoning_signature or ""
        )
        if not reasoning_signature:
            reasoning_signature = None

        tool_calls_map = OrderedDict[int, ToolCall]()
        for tool_calls in [self.tool_calls or [], other.tool_calls or []]:
            for tc in tool_calls:
                if tc.index is None:
                    raise ValueError("Tool call chunk missing index")
                if tc.index not in tool_calls_map:
                    tool_calls_map[tc.index] = copy.deepcopy(tc)
                else:
                    existing_name = tool_calls_map[tc.index].function.name
                    new_name = tc.function.name
                    if existing_name and new_name and existing_name != new_name:
                        raise ValueError(
                            "Can't accumulate messages with different tool call names"
                        )
                    if new_name and not existing_name:
                        tool_calls_map[tc.index].function.name = new_name
                    new_args = (tool_calls_map[tc.index].function.arguments or "") + (
                        tc.function.arguments or ""
                    )
                    tool_calls_map[tc.index].function.arguments = new_args

        return LLMMessage(
            role=self.role,
            content=content,
            reasoning_content=reasoning_content,
            reasoning_signature=reasoning_signature,
            reasoning_message_id=self.reasoning_message_id
            or other.reasoning_message_id,
            tool_calls=list(tool_calls_map.values()) or None,
            name=self.name,
            tool_call_id=self.tool_call_id,
            message_id=self.message_id,
        )


class LLMUsage(BaseModel):
    model_config = ConfigDict(frozen=True)
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def __add__(self, other: LLMUsage) -> LLMUsage:
        return LLMUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
        )


class BaseEvent(BaseModel, ABC):
    model_config = ConfigDict(arbitrary_types_allowed=True)


class MessageList(Sequence[LLMMessage]):
    def __init__(
        self,
        initial: list[LLMMessage] | None = None,
        observer: Callable[[LLMMessage], None] | None = None,
    ) -> None:
        self._data: list[LLMMessage] = list(initial) if initial else []
        self._observer = observer
        self._reset_hooks: list[Callable[[], None]] = []
        self._silent = False
        if self._observer:
            for msg in self._data:
                self._observer(msg)

    def _notify(self, msg: LLMMessage) -> None:
        if not self._silent and self._observer is not None:
            self._observer(msg)

    def append(self, msg: LLMMessage) -> None:
        self._data.append(msg)
        self._notify(msg)

    def insert(self, i: int, msg: LLMMessage) -> None:
        self._data.insert(i, msg)

    def extend(self, msgs: list[LLMMessage]) -> None:
        for msg in msgs:
            self.append(msg)

    def on_reset(self, hook: Callable[[], None]) -> None:
        """Register a callback that fires whenever the list is reset."""
        self._reset_hooks.append(hook)

    def reset(self, new: list[LLMMessage]) -> None:
        """Replace contents silently (never notifies)."""
        self._data = list(new)
        for hook in self._reset_hooks:
            hook()

    def update_system_prompt(self, new: str) -> None:
        """Update the system prompt in place."""
        self._data[0] = LLMMessage(role=Role.system, content=new)

    @contextmanager
    def silent(self) -> Iterator[None]:
        """Context manager that suppresses notifications."""
        prev = self._silent
        self._silent = True
        try:
            yield
        finally:
            self._silent = prev

    def __len__(self) -> int:
        return len(self._data)

    @overload
    def __getitem__(self, index: int) -> LLMMessage: ...
    @overload
    def __getitem__(self, index: slice) -> list[LLMMessage]: ...
    def __getitem__(self, index: int | slice) -> LLMMessage | list[LLMMessage]:
        return self._data[index]

    def __iter__(self) -> Iterator[LLMMessage]:
        return iter(self._data)

    def __contains__(self, item: object) -> bool:
        return item in self._data

    def __bool__(self) -> bool:
        return bool(self._data)


class RateLimitError(Exception):
    def __init__(self, provider: str, model: str) -> None:
        self.provider = provider
        self.model = model
        super().__init__(
            "Rate limits exceeded. Please wait a moment before trying again."
        )


# Type aliases for callbacks
type ApprovalCallback = Callable[
    [str, BaseModel, str, list | None], Awaitable[tuple[ApprovalResponse, str | None]]
]

type UserInputCallback = Callable[[BaseModel], Awaitable[BaseModel]]

type SwitchAgentCallback = Callable[[str], Awaitable[None]]
