from __future__ import annotations

from rich.style import Style
from textual.css.query import NoMatches
from textual.widgets.text_area import TextAreaTheme

from tests.cli.plan_offer.adapters.fake_whoami_gateway import FakeWhoAmIGateway
from tests.conftest import build_test_agent_loop, build_test_vibe_config
from tests.stubs.fake_backend import FakeBackend
from vibe.cli.plan_offer.ports.whoami_gateway import WhoAmIPlanType, WhoAmIResponse
from vibe.cli.textual_ui.app import VibeApp
from vibe.cli.textual_ui.widgets.chat_input import ChatTextArea
from vibe.cli.textual_ui.widgets.mcp_app import MCPApp
from vibe.cli.textual_ui.widgets.tools import ToolCallMessage
from vibe.core.agents.models import BuiltinAgentName
from vibe.core.config import VibeConfig
from vibe.core.tools.mcp import MCPRegistry


def default_config() -> VibeConfig:
    """Default configuration for snapshot testing.
    Remove as much interference as possible from the snapshot comparison, in order to get a clean pixel-to-pixel comparison.
    - Injects a fake backend to prevent (or stub) LLM calls.
    - Disables the banner animation.
    - Forces a value for the displayed workdir
    - Hides the chat input cursor (as the blinking animation is not deterministic).
    """
    return build_test_vibe_config(
        disable_welcome_banner_animation=True, displayed_workdir="/test/workdir"
    )


class BaseSnapshotTestApp(VibeApp):
    CSS_PATH = "../../vibe/cli/textual_ui/app.tcss"
    _current_agent_name: str = BuiltinAgentName.DEFAULT

    def __init__(
        self,
        config: VibeConfig | None = None,
        backend: FakeBackend | None = None,
        mcp_registry: MCPRegistry | None = None,
        **kwargs,
    ):
        agent_loop = build_test_agent_loop(
            config=config or default_config(),
            agent_name=self._current_agent_name,
            enable_streaming=bool(kwargs.get("enable_streaming", False)),
            backend=backend or FakeBackend(),
            mcp_registry=mcp_registry,
        )

        plan_offer_gateway = kwargs.pop(
            "plan_offer_gateway",
            FakeWhoAmIGateway(
                WhoAmIResponse(
                    plan_type=WhoAmIPlanType.CHAT,
                    plan_name="INDIVIDUAL",
                    prompt_switching_to_pro_plan=False,
                )
            ),
        )

        super().__init__(
            agent_loop=agent_loop, plan_offer_gateway=plan_offer_gateway, **kwargs
        )

    async def on_mount(self) -> None:
        await super().on_mount()
        self._hide_chat_input_cursor()

    def _hide_chat_input_cursor(self) -> None:
        text_area = self.query_one(ChatTextArea)
        hidden_cursor_theme = TextAreaTheme(name="hidden_cursor", cursor_style=Style())
        text_area.register_theme(hidden_cursor_theme)
        text_area.theme = "hidden_cursor"

    def freeze_spinners(self) -> None:
        """Freeze all ToolCallMessage spinners to make snapshots deterministic."""
        for widget in self.query(ToolCallMessage):
            widget._is_spinning = False
            if widget._spinner_timer:
                widget._spinner_timer.stop()
                widget._spinner_timer = None
            widget._spinner.reset()
            if widget._indicator_widget:
                widget._indicator_widget.update(widget._spinner.current_frame())
            if widget._text_widget:
                widget._text_widget.update(widget.get_content())

    async def wait_for_mcp_refresh(self, pilot) -> None:
        """Wait for MCP refresh to complete (max 30s)."""
        try:
            mcp_app = self.query_one(MCPApp)
        except NoMatches:
            return
        for _ in range(600):
            if not mcp_app._refreshing:
                return
            await pilot.pause(0.05)
