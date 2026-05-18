"""Generate SVG snapshots for 5 LoadMore scenarios to diagnose Bug #2."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from textual.pilot import Pilot

from tests.cli.plan_offer.adapters.fake_whoami_gateway import FakeWhoAmIGateway
from tests.conftest import build_test_agent_loop
from tests.mock.utils import mock_llm_chunk
from tests.snapshots.base_snapshot_test_app import BaseSnapshotTestApp, default_config
from tests.stubs.fake_backend import FakeBackend
from vibe.cli.plan_offer.ports.whoami_gateway import WhoAmIPlanType, WhoAmIResponse
from vibe.cli.textual_ui.widgets.load_more import HistoryLoadMoreMessage
from vibe.core.types import FunctionCall, LLMChunk, ToolCall

logger = logging.getLogger(__name__)

_SAMPLE_FILE = "sample_config.md"
_SAMPLE_CONTENT = "# Config\n" + "- item: value\n" * 100


class _VibeAppProtocol:
    _agent_running: bool
    agent_loop: Any
    _windowing: Any
    _history_widget_indices: Any


def _make_tool_call_bash_only(idx: int) -> list[ToolCall]:
    return [
        ToolCall(
            id=f"call-bash-{idx}",
            index=idx,
            function=FunctionCall(
                name="bash",
                arguments=json.dumps({"command": f"echo turn-{idx}", "timeout": 30}),
            ),
        )
    ]


def _make_tool_call_mixed(idx: int) -> list[ToolCall]:
    if idx % 2 == 0:
        return [
            ToolCall(
                id=f"call-read-{idx}",
                index=idx,
                function=FunctionCall(
                    name="read_file",
                    arguments=json.dumps({
                        "path": f"sample_turn_{idx}.md",
                        "offset": 0,
                    }),
                ),
            )
        ]
    return [
        ToolCall(
            id=f"call-bash-{idx}",
            index=idx,
            function=FunctionCall(
                name="bash",
                arguments=json.dumps({"command": f"echo turn-{idx}", "timeout": 30}),
            ),
        )
    ]


def _build_backend_streams(num_tool_turns: int, tool_call_fn) -> list[list[LLMChunk]]:
    streams: list[list[LLMChunk]] = []
    for idx in range(num_tool_turns):
        streams.append([mock_llm_chunk(content="", tool_calls=tool_call_fn(idx))])
    streams.append([mock_llm_chunk(content="Task complete.")])
    return streams


class _LoadMoreApp(BaseSnapshotTestApp):
    def __init__(self, tool_call_fn):
        # DEBUG: Monkey-patch Button render methods to trace cache behavior
        # Commented out after Bug #2 fix — preserved for future debugging
        if False:  # DEBUG BLOCK START
            import time as _time

            from textual.widgets._button import Button as _Button

            _orig_render = _Button.render
            _orig_render_line = (
                None  # Button doesn't override render_line, uses Widget's
            )

            def _traced_render(self):
                result = _orig_render(self)
                with open("/tmp/render_debug.txt", "a") as f:
                    f.write(
                        f"{_time.monotonic():.3f} Button.render #{id(self)} label={self.label!r}\n"
                    )
                    f.flush()
                return result

            _Button.render = _traced_render
            # Also trace Widget._render (used by Button)
            from textual.widget import Widget as _Widget

            _orig__render = _Widget._render

            def _traced__render(self):
                cache_hit = self._layout_cache.get("_render.visual") is not None
                result = _orig__render(self)
                if isinstance(self, _Button):
                    with open("/tmp/render_debug.txt", "a") as f:
                        dirty = bool(self._dirty_regions)
                        f.write(
                            f"{_time.monotonic():.3f} Button._render #{id(self)} cache_hit={cache_hit} dirty={dirty}\n"
                        )
                        f.flush()
                return result

            _Widget._render = _traced__render
            # Trace Widget._render_content
            _orig__render_content = _Widget._render_content

            def _traced__render_content(self):
                if isinstance(self, _Button):
                    label_obj = self.label
                    label_text = getattr(
                        label_obj, "_text", getattr(label_obj, "plain", "?")
                    )
                    visual_before = self._layout_cache.get("_render.visual")
                    with open("/tmp/render_debug.txt", "a") as f:
                        f.write(
                            f"{_time.monotonic():.3f} Button._render_content #{id(self)} BEFORE label_id={id(label_obj)} label._text={label_text!r} layout_has_visual={visual_before is not None}\n"
                        )
                        f.flush()
                result = _orig__render_content(self)
                if isinstance(self, _Button):
                    with open("/tmp/render_debug.txt", "a") as f:
                        texts = []
                        if (
                            hasattr(self._render_cache, "lines")
                            and len(self._render_cache.lines) > 0
                        ):
                            for seg in self._render_cache.lines[0]:
                                if seg.text.strip():
                                    texts.append(seg.text)
                        cached_visual = self._layout_cache.get("_render.visual")
                        visual_text = ""
                        if cached_visual:
                            visual_text = getattr(
                                cached_visual,
                                "_text",
                                getattr(
                                    cached_visual, "plain", str(cached_visual)[:30]
                                ),
                            )
                        f.write(
                            f"{_time.monotonic():.3f} Button._render_content #{id(self)} AFTER cache_text={''.join(texts)[:50]} layout_visual_id={id(cached_visual)} layout_visual_text={visual_text!r}\n"
                        )
                        f.flush()
                return result

            _Widget._render_content = _traced__render_content
            # Trace Content.render_strips
            from textual.content import Content as _Content

            _orig_render_strips = _Content.render_strips
            # Trace _FormattedLine.to_strip
            from textual.content import _FormattedLine as _FormattedLine

            _orig_to_strip = _FormattedLine.to_strip
            _orig_expand_tabs = _Content.expand_tabs

            def _traced_expand_tabs(self_c, tab_size=8):
                result = _orig_expand_tabs(self_c, tab_size)
                if "Load more" in getattr(self_c, "_text", ""):
                    with open("/tmp/render_debug.txt", "a") as f:
                        f.write(
                            f"{_time.monotonic():.3f} Content.expand_tabs #{id(self_c)} input_text={self_c._text!r} output_text={result._text!r} same={self_c is result}\\n"
                        )
                        f.flush()
                return result

            _Content.expand_tabs = _traced_expand_tabs
            _orig_fl_init = _FormattedLine.__init__
            _orig_content_pad = _Content.pad
            _orig_content_divide = _Content.divide
            import textual.content as _textual_content_mod

            _orig_divide_line = _textual_content_mod.divide_line

            def _traced_divide_line(text, *args, **kwargs):
                result = _orig_divide_line(text, *args, **kwargs)
                if "Load more" in text:
                    with open("/tmp/render_debug.txt", "a") as f:
                        f.write(
                            f"{_time.monotonic():.3f} divide_line text={text!r} width_arg={args[0] if args else '?'} offsets={result}\\n"
                        )
                        f.flush()
                return result

            _textual_content_mod.divide_line = _traced_divide_line

            def _traced_content_divide(self_c, offsets):
                result = _orig_content_divide(self_c, offsets)
                if "Load more" in getattr(self_c, "_text", ""):
                    parts = [f"#{i}({r._text!r})" for i, r in enumerate(result)]
                    with open("/tmp/render_debug.txt", "a") as f:
                        f.write(
                            f"{_time.monotonic():.3f} Content.divide #{id(self_c)} text={self_c._text!r} offsets={list(offsets)} results=[{', '.join(parts)}]\\n"
                        )
                        f.flush()
                return result

            _Content.divide = _traced_content_divide

            def _traced_content_pad(self_c, left, right, character=" "):
                result = _orig_content_pad(self_c, left, right, character)
                if "Load more" in getattr(self_c, "_text", ""):
                    with open("/tmp/render_debug.txt", "a") as f:
                        f.write(
                            f"{_time.monotonic():.3f} Content.pad #{id(self_c)} left={left} right={right} input_text={self_c._text!r} output_text={result._text!r}\\n"
                        )
                        f.flush()
                return result

            _Content.pad = _traced_content_pad

            def _traced_fl_init(self_fl, get_style, content, width, *args, **kwargs):
                if "Load more" in getattr(content, "_text", ""):
                    with open("/tmp/render_debug.txt", "a") as f:
                        f.write(
                            f"{_time.monotonic():.3f} _FormattedLine.__init__ content_id={id(content)} content._text={content._text!r} width={width}\\n"
                        )
                        f.flush()
                return _orig_fl_init(
                    self_fl, get_style, content, width, *args, **kwargs
                )

            _FormattedLine.__init__ = _traced_fl_init

            def _traced_to_strip(self_fl, style):
                result = _orig_to_strip(self_fl, style)
                content_text = getattr(getattr(self_fl, "content", None), "_text", "?")
                if "Load more" in content_text:
                    segments = result[0] if result else []
                    seg_texts = [s.text for s in segments]
                    with open("/tmp/render_debug.txt", "a") as f:
                        f.write(
                            f"{_time.monotonic():.3f} _FormattedLine.to_strip content._text={content_text!r} width={self_fl.width} align={self_fl.align} segs={seg_texts}\\n"
                        )
                        f.flush()
                return result

            _FormattedLine.to_strip = _traced_to_strip

            def _traced_render_strips(self_c, width, height, style, options):
                result = _orig_render_strips(self_c, width, height, style, options)
                texts = []
                if result and len(result) > 0:
                    for seg in result[0]:
                        if seg.text.strip():
                            texts.append(seg.text)
                result_count = sum(len(r) for r in result)
                with open("/tmp/render_debug.txt", "a") as f:
                    f.write(
                        f"{_time.monotonic():.3f} Content.render_strips #{id(self_c)} _text={getattr(self_c, '_text', '?')!r} width={width} result_lines={len(result)} result_segs={result_count} result_text={''.join(texts)[:50]}\\n"
                    )
                    f.flush()
                return result

            _Content.render_strips = _traced_render_strips
            # Trace Button size at render time
            _orig_btn_render = _Button.render

            def _traced_btn_render(self_b):
                result = _orig_btn_render(self_b)
                with open("/tmp/render_debug.txt", "a") as f:
                    f.write(
                        f"{_time.monotonic():.3f} Button.render #{id(self_b)} size={self_b.size} outer_size={self_b.outer_size} content_size={self_b.content_size} label_text={getattr(self_b.label, '_text', '?')!r}\\n"
                    )
                    f.flush()
                return result

            _Button.render = _traced_btn_render
            # Trace Widget.render_line
            _orig_render_line = _Widget.render_line

            def _traced_render_line(self, y):
                if isinstance(self, _Button):
                    dirty = bool(self._dirty_regions)
                    if dirty:
                        with open("/tmp/render_debug.txt", "a") as f:
                            f.write(
                                f"{_time.monotonic():.3f} Button.render_line #{id(self)} y={y} dirty=True → will call _render_content\n"
                            )
                            f.flush()
                result = _orig_render_line(self, y)
                if isinstance(self, _Button):
                    with open("/tmp/render_debug.txt", "a") as f:
                        dirty = bool(self._dirty_regions)
                        cache_len = (
                            len(self._render_cache.lines)
                            if hasattr(self._render_cache, "lines")
                            else 0
                        )
                        # Extract text from render_cache
                        texts = []
                        if hasattr(self._render_cache, "lines") and cache_len > 0:
                            for seg in self._render_cache.lines[0]:
                                if seg.text.strip():
                                    texts.append(seg.text)
                        f.write(
                            f"{_time.monotonic():.3f} Button.render_line #{id(self)} y={y} dirty_was={dirty} cache_lines={cache_len} text={''.join(texts)[:40]}\n"
                        )
                        f.flush()
                return result

            _Widget.render_line = _traced_render_line
            # Trace _styles_cache.render_widget
            from textual._styles_cache import StylesCache as _StylesCache

            _orig_render_widget = _StylesCache.render_widget

            def _traced_render_widget(self_sc, widget, crop):
                result = _orig_render_widget(self_sc, widget, crop)
                if isinstance(widget, _Button):
                    with open("/tmp/render_debug.txt", "a") as f:
                        cache_keys = (
                            list(self_sc._cache.keys())
                            if hasattr(self_sc, "_cache")
                            else []
                        )
                        dirty_lines = (
                            list(self_sc._dirty_lines)
                            if hasattr(self_sc, "_dirty_lines")
                            else []
                        )
                        text_parts = []
                        for y in [0, 1, 2]:
                            if y in self_sc._cache:
                                segments = self_sc._cache[y]
                                texts = [s.text for s in segments if s.text.strip()]
                                text_parts.append(f"y{y}={''.join(texts)[:40]}")
                        f.write(
                            f"{_time.monotonic():.3f} StylesCache.render_widget #{id(widget)} cache={cache_keys} dirty={dirty_lines} {' '.join(text_parts)}\n"
                        )
                        f.flush()
                return result

            _StylesCache.render_widget = _traced_render_widget
            # Trace _styles_cache.clear and set_dirty
            _orig_clear = _StylesCache.clear

            def _traced_clear(self_sc):
                _orig_clear(self_sc)
                with open("/tmp/render_debug.txt", "a") as f:
                    f.write(
                        f"{_time.monotonic():.3f} StylesCache.clear #{id(self_sc)}\n"
                    )
                    f.flush()

            _StylesCache.clear = _traced_clear
            _orig_set_dirty = _StylesCache.set_dirty

            def _traced_set_dirty(self_sc, *regions):
                _orig_set_dirty(self_sc, *regions)
                with open("/tmp/render_debug.txt", "a") as f:
                    f.write(
                        f"{_time.monotonic():.3f} StylesCache.set_dirty #{id(self_sc)} regions={len(regions)} dirty_lines={list(self_sc._dirty_lines)}\n"
                    )
                    f.flush()

            _StylesCache.set_dirty = _traced_set_dirty
        pass  # DEBUG BLOCK END

        backend = FakeBackend(_build_backend_streams(15, tool_call_fn))
        config = default_config()
        agent_loop = build_test_agent_loop(
            config=config, backend=backend, enable_streaming=False
        )
        plan_offer_gateway = FakeWhoAmIGateway(
            WhoAmIResponse(
                plan_type=WhoAmIPlanType.CHAT,
                plan_name="INDIVIDUAL",
                prompt_switching_to_pro_plan=False,
            )
        )
        from vibe.cli.textual_ui.app import VibeApp

        VibeApp.__init__(
            self, agent_loop=agent_loop, plan_offer_gateway=plan_offer_gateway
        )


async def _wait_for_agent(
    app,
    pilot: Pilot,
    expand_load_more_once: bool = False,
    expand_tool_calls_after: bool = False,
    scroll_to_bottom: bool = False,
) -> None:
    vibe_app = cast(_VibeAppProtocol, app)
    for _ in range(750):
        if not vibe_app._agent_running:
            break
        await pilot.pause(0.02)

    for _ in range(750):
        widgets = list(app.query(HistoryLoadMoreMessage))
        if widgets:
            wm = widgets[0]
            if wm._remaining is not None:
                break
        await pilot.pause(0.02)

    widgets = list(app.query(HistoryLoadMoreMessage))
    if widgets:
        last_remaining = widgets[0]._remaining
        for _ in range(50):
            await pilot.pause(0.02)
            current = widgets[0]._remaining
            if current != last_remaining:
                last_remaining = current

    # Expand load more widget once by single click
    if expand_load_more_once:
        load_more_widgets = list(app.query(HistoryLoadMoreMessage))
        if load_more_widgets:
            load_more_btn = load_more_widgets[0]._label_widget
            if load_more_btn:
                await pilot.click(load_more_btn)
                for _ in range(300):
                    await pilot.pause(0.02)
                    updated_widgets = list(app.query(HistoryLoadMoreMessage))
                    if not updated_widgets or (
                        updated_widgets and updated_widgets[0]._remaining is None
                    ):
                        break

    # Expand tool calls by ctrl+o after load more
    if expand_tool_calls_after:
        await pilot.press("ctrl+o")
        await pilot.pause(0.5)

    cast(_LoadMoreApp, app).freeze_spinners()
    if scroll_to_bottom:
        await pilot.press("end")
    else:
        await pilot.press("home")
    await pilot.pause(1.0)

    # Debug: print message counts and widget tree with history indices
    from vibe.cli.textual_ui.app import non_system_history_messages

    ns_msgs = non_system_history_messages(vibe_app.agent_loop.messages)
    windowing = vibe_app._windowing
    messages_area = app.query_one("#messages")
    children = list(messages_area.children)
    children_count = len(children)
    hwi = vibe_app._history_widget_indices
    logger.debug(
        "history_msgs=%s backfill_cursor=%s messages_area_children=%s",
        len(ns_msgs),
        windowing._backfill_cursor,
        children_count,
    )
    logger.debug("hwi entries=%s", len(hwi))
    for i, child in enumerate(children):
        cls = child.__class__.__name__
        hidx = hwi.get(child)
        tool_info = f" hidx={hidx}"
        if hasattr(child, "tool_name"):
            tool_info += f" tool={child.tool_name}"
        collapsed = ""
        if hasattr(child, "collapsed"):
            collapsed = f" collapsed={child.collapsed}"
        logger.debug("child[%s]=%s%s%s", i, cls, tool_info, collapsed)
    # Also log visible_indices calculation
    visible_indices = [idx for child in children if (idx := hwi.get(child)) is not None]
    logger.debug(
        "visible_indices=%s oldest=%s",
        visible_indices,
        min(visible_indices) if visible_indices else "N/A",
    )


def _export_svg(
    label: str,
    tool_call_fn,
    tool_call_name: str,
    fold_state: str,
    expand_before: bool,
    expand_load_more_once: bool = False,
    expand_tool_calls_after: bool = False,
    scroll_to_bottom: bool = False,
) -> None:
    import time as _time

    from textual._doc import take_svg_screenshot

    async def _run(pilot: Pilot) -> None:
        app = pilot.app
        Path(_SAMPLE_FILE).write_text(_SAMPLE_CONTENT)
        for turn_idx in range(0, 20, 2):
            Path(f"sample_turn_{turn_idx}.md").write_text(
                f"# Config (Turn {turn_idx})\n" + f"- item: value_{turn_idx}\n" * 100
            )
        if expand_before:
            await pilot.press("ctrl+o")
            await pilot.pause(0.1)
        with patch("vibe.cli.textual_ui.app.PRUNE_LOW_MARK", 5):
            with patch("vibe.cli.textual_ui.app.PRUNE_HIGH_MARK", 10):
                await pilot.press(*"run a task")
                await pilot.press("enter")
                await _wait_for_agent(
                    app,
                    pilot,
                    expand_load_more_once,
                    expand_tool_calls_after,
                    scroll_to_bottom,
                )

    # DEBUG: Monkey-patch export_screenshot to log capture timing — preserved for future debugging
    if False:  # DEBUG BLOCK START
        from textual.app import App as _App

        _orig_export = _App.export_screenshot

        def _traced_export(self, *, title=None, simplify=False):
            with open("/tmp/render_debug.txt", "a") as f:
                f.write(f"{_time.monotonic():.3f} *** SVG CAPTURE START ***\n")
                f.flush()
            result = _orig_export(self, title=title, simplify=simplify)
            with open("/tmp/render_debug.txt", "a") as f:
                f.write(f"{_time.monotonic():.3f} *** SVG CAPTURE END ***\n")
                f.flush()
            return result

        _App.export_screenshot = _traced_export
        pass  # DEBUG BLOCK END

    app = _LoadMoreApp(tool_call_fn)
    svg = take_svg_screenshot(app=app, terminal_size=(120, 36), run_before=_run)
    out = Path(f"/tmp/loadmore_{label}.svg")
    out.write_text(svg)
    # Extract LoadMore text from SVG
    import re

    matches = re.findall(r"Load[^<]*", svg)
    loadmore_lines = [m for m in matches if "more" in m.lower()]
    logger.debug("[%s] LoadMore text in SVG: %s", label, loadmore_lines)


def test_export_svg_scenarios() -> None:
    """Generate SVG files for manual inspection."""
    _export_svg(
        "mixed_folded", _make_tool_call_mixed, "mixed", "folded", expand_before=False
    )


def test_export_svg_bash() -> None:
    """Generate bash-only SVG files."""
    _export_svg(
        "bash_folded", _make_tool_call_bash_only, "bash", "folded", expand_before=False
    )


def test_export_svg_load_more_expanded() -> None:
    """Generate SVG with load more widget expanded once by single click."""
    _export_svg(
        "mixed_load_more_expanded",
        _make_tool_call_mixed,
        "mixed",
        "folded",
        expand_before=False,
        expand_load_more_once=True,
    )


def test_export_svg_load_more_and_tool_calls_expanded() -> None:
    """Generate SVG with load more clicked once, then tool calls expanded by ctrl+o."""
    _export_svg(
        "mixed_load_more_and_tool_calls_expanded",
        _make_tool_call_mixed,
        "mixed",
        "folded",
        expand_before=False,
        expand_load_more_once=True,
        expand_tool_calls_after=True,
    )


def test_export_svg_bash_load_more_scrolled() -> None:
    """Bash-only, folded, one load more click, scroll to bottom, no expand tool calls."""
    _export_svg(
        "bash_load_more_scrolled",
        _make_tool_call_bash_only,
        "bash",
        "folded",
        expand_before=False,
        expand_load_more_once=True,
        scroll_to_bottom=True,
    )


def test_export_svg_mixed_load_more_scrolled() -> None:
    """Mixed, folded, one load more click, scroll to bottom, no expand tool calls."""
    _export_svg(
        "mixed_load_more_scrolled",
        _make_tool_call_mixed,
        "mixed",
        "folded",
        expand_before=False,
        expand_load_more_once=True,
        scroll_to_bottom=True,
    )
