from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from functools import lru_cache
import os
from pathlib import Path
import sys
from typing import ClassVar, Literal, final

from pydantic import BaseModel, Field, field_validator
from tree_sitter import Language, Node, Parser
import tree_sitter_bash as tsbash

from vibe.core.scratchpad import is_scratchpad_path
from vibe.core.tools.arity import build_session_pattern
from vibe.core.tools.base import (
    BaseTool,
    BaseToolConfig,
    BaseToolState,
    InvokeContext,
    ToolError,
    ToolPermission,
)
from vibe.core.tools.permissions import (
    PermissionContext,
    PermissionScope,
    RequiredPermission,
)
from vibe.core.tools.ui import ToolCallDisplay, ToolResultDisplay, ToolUIData
from vibe.core.tools.utils import is_path_within_workdir
from vibe.core.types import ToolResultEvent, ToolStreamEvent
from vibe.core.utils import is_windows, kill_async_subprocess


@lru_cache(maxsize=1)
def _get_parser() -> Parser:
    return Parser(Language(tsbash.language()))


def _extract_commands(command: str) -> list[str]:
    parser = _get_parser()
    tree = parser.parse(command.encode("utf-8"))

    commands: list[str] = []

    def find_commands(node: Node) -> None:
        if node.type == "command":
            parts = []
            for child in node.children:
                if (
                    child.type
                    in {"command_name", "word", "string", "raw_string", "concatenation"}
                    and child.text is not None
                ):
                    parts.append(child.text.decode("utf-8"))
            if parts:
                commands.append(" ".join(parts))

        for child in node.children:
            find_commands(child)

    find_commands(tree.root_node)
    return commands


_OUTPUT_REDIRECT_OPS = {">", ">>", ">&", ">>&", "&>"}


def _has_output_redirection(command: str) -> bool:
    """Check if the command has output redirection that writes to a file.

    Detects: >, >>, >&, >>&, 2>, 2>>, &>, etc.
    Does NOT flag: <, << (input redirection / heredoc).
    """
    parser = _get_parser()
    tree = parser.parse(command.encode("utf-8"))

    def find_output_redirect(node: Node) -> bool:
        if node.type == "file_redirect":
            for child in node.children:
                if child.text is not None:
                    token = child.text.decode("utf-8")
                    if token in _OUTPUT_REDIRECT_OPS:
                        return True
        for child in node.children:
            if find_output_redirect(child):
                return True
        return False

    return find_output_redirect(tree.root_node)


def _get_subprocess_encoding() -> str:
    if sys.platform == "win32":
        # Windows console uses OEM code page (e.g., cp850, cp1252)
        import ctypes

        return f"cp{ctypes.windll.kernel32.GetOEMCP()}"
    return "utf-8"


def _get_shell_executable() -> str | None:
    if is_windows():
        return None
    return os.environ.get("SHELL")


def _get_base_env() -> dict[str, str]:
    base_env = {**os.environ, "CI": "true", "NONINTERACTIVE": "1", "NO_TTY": "1"}

    if is_windows():
        base_env["GIT_PAGER"] = "more"
        base_env["PAGER"] = "more"
    else:
        base_env["TERM"] = "dumb"
        base_env["DEBIAN_FRONTEND"] = "noninteractive"
        base_env["GIT_PAGER"] = "cat"
        base_env["PAGER"] = "cat"
        base_env["LESS"] = "-FX"
        base_env["LC_ALL"] = "en_US.UTF-8"

    return base_env


def _get_default_allowlist() -> list[str]:
    common = ["cd", "echo", "git diff", "git log", "git status", "tree", "whoami"]

    if is_windows():
        return common + ["dir", "findstr", "more", "type", "ver", "where"]
    else:
        return common + [
            "cat",
            "file",
            "find",
            "head",
            "ls",
            "pwd",
            "stat",
            "tail",
            "uname",
            "wc",
            "which",
        ]


def _get_default_denylist() -> list[str]:
    common = ["gdb", "pdb", "passwd"]

    if is_windows():
        return common + ["cmd /k", "powershell -NoExit", "pwsh -NoExit", "notepad"]
    else:
        return common + [
            "nano",
            "vim",
            "vi",
            "emacs",
            "bash -i",
            "sh -i",
            "zsh -i",
            "fish -i",
            "dash -i",
            "screen",
            "tmux",
            "git checkout",
            "git reset --hard",
            "git add -A",
        ]


def _get_default_denylist_standalone() -> list[str]:
    common = ["python", "python3", "ipython"]

    if is_windows():
        return common + ["cmd", "powershell", "pwsh", "notepad"]
    else:
        return common + ["bash", "sh", "nohup", "vi", "vim", "emacs", "nano", "su"]


_PATH_COMMANDS = {
    "cat",
    "cd",
    "chmod",
    "chown",
    "cp",
    "head",
    "ls",
    "mkdir",
    "mv",
    "rm",
    "stat",
    "tail",
    "touch",
    "wc",
}

_FIND_EXECUTION_PREDICATES = {"-exec", "-execdir", "-ok", "-okdir"}


def _collect_outside_dirs(command_parts: list[str]) -> set[str]:
    """Collect parent directories referenced outside the workdir.

    Iterates file-manipulating commands (see _PATH_COMMANDS) and inspects
    their arguments as candidate paths. Skips flags (-r, --recursive) and
    chmod mode strings (+x). For any argument that resolves outside the current
    working directory, adds the parent directory (or the path itself when it is
    a directory) to the result set — suitable for building an OUTSIDE_DIRECTORY
    RequiredPermission.
    """
    dirs: set[str] = set()
    for part in command_parts:
        tokens = part.split()
        command = tokens[0] if tokens else None
        if not command or command not in _PATH_COMMANDS:
            continue
        for token in tokens[1:]:
            # Skip CLI flags like -r, --recursive
            if token.startswith("-"):
                continue
            # Skip chmod mode strings like +x, +rwx — they are not file paths
            if command == "chmod" and token.startswith("+"):
                continue
            # Only consider tokens that look like paths
            if not (
                token.startswith(os.sep)
                or token.startswith("~")
                or token.startswith(".")
                or os.sep in token
            ):
                continue
            if is_path_within_workdir(token):
                continue
            if is_scratchpad_path(token):
                continue
            # Resolve relative / home-relative paths, then collect parent dir
            resolved = Path(token).expanduser()
            if not resolved.is_absolute():
                resolved = Path.cwd() / resolved
            resolved = resolved.resolve()
            # For a directory target use the dir itself; for a file use its parent
            parent = str(resolved) if resolved.is_dir() else str(resolved.parent)
            dirs.add(parent)
    return dirs


def _matches_pattern(command: str, pattern: str) -> bool:
    return command == pattern or command.startswith(pattern + " ")


class BashToolConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ASK
    max_output_bytes: int = Field(
        default=16_000, description="Maximum bytes to capture from stdout and stderr."
    )
    default_timeout: int = Field(
        default=300, description="Default timeout for commands in seconds."
    )
    allowlist: list[str] = Field(
        default_factory=_get_default_allowlist,
        description="Command prefixes that are automatically allowed",
    )
    denylist: list[str] = Field(
        default_factory=_get_default_denylist,
        description="Command prefixes that are automatically denied",
    )
    denylist_standalone: list[str] = Field(
        default_factory=_get_default_denylist_standalone,
        description="Commands that are denied only when run without arguments",
    )
    sensitive_patterns: list[str] = Field(
        default=["sudo", "tee"],
        description="Command prefixes that always ASK regardless of arity approval.",
    )


class BashArgs(BaseModel):
    command: str
    timeout: int = Field(description="Command timeout in seconds (max 600).")

    @field_validator("timeout", mode="before")
    @classmethod
    def _clamp_timeout(cls, value: int) -> int:
        return min(value, 600)


class BashResult(BaseModel):
    command: str
    stdout: str
    stderr: str
    returncode: int


class Bash(
    BaseTool[BashArgs, BashResult, BashToolConfig, BaseToolState],
    ToolUIData[BashArgs, BashResult],
):
    description: ClassVar[str] = "Run a one-off bash command and capture its output."

    @classmethod
    def format_call_display(cls, args: BashArgs) -> ToolCallDisplay:
        timeout = args.timeout
        if timeout is not None:
            return ToolCallDisplay(
                summary=f"bash: {args.command} (timeout: {timeout}s)"
            )
        return ToolCallDisplay(summary=f"bash: {args.command}")

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if not isinstance(event.result, BashResult):
            return ToolResultDisplay(
                success=False, message=event.error or event.skip_reason or "No result"
            )

        return ToolResultDisplay(success=True, message=f"Ran {event.result.command}")

    @classmethod
    def get_status_text(cls) -> str:
        return "Running command"

    @staticmethod
    def _has_find_execution_predicate(command: str) -> bool:
        """Defensive check for find -exec, -execdir, -ok, -okdir predicates."""
        if not _matches_pattern(command, "find"):
            return False
        return any(predicate in command for predicate in _FIND_EXECUTION_PREDICATES)

    @staticmethod
    def _build_command_required_permission(
        invocation_pattern: str, session_pattern: str, label: str
    ) -> RequiredPermission:
        return RequiredPermission(
            scope=PermissionScope.COMMAND_PATTERN,
            invocation_pattern=invocation_pattern,
            session_pattern=session_pattern,
            label=label,
        )

    @staticmethod
    def _build_outside_directory_permission(glob: str) -> RequiredPermission:
        return RequiredPermission(
            scope=PermissionScope.OUTSIDE_DIRECTORY,
            invocation_pattern=glob,
            session_pattern=glob,
            label=f"outside workdir ({glob})",
        )

    def _find_denylist_match(self, command: str) -> str | None:
        return next(
            (p for p in self.config.denylist if _matches_pattern(command, p)), None
        )

    def _is_standalone_denylisted(self, command: str) -> bool:
        parts = command.split()
        if not parts:
            return False
        base_command = parts[0]
        if len(parts) == 1:
            command_name = os.path.basename(base_command)
            if command_name in self.config.denylist_standalone:
                return True
            if base_command in self.config.denylist_standalone:
                return True
        return False

    def _is_allowlisted(self, command: str) -> bool:
        return any(
            _matches_pattern(command, pattern) for pattern in self.config.allowlist
        )

    def _is_sensitive(self, command: str) -> bool:
        tokens = command.split()
        if not tokens:
            return False
        return tokens[0] in self.config.sensitive_patterns

    def _resolve_guardrail_permission(
        self, command_parts: list[str]
    ) -> PermissionContext | None:
        find_execution_required: list[RequiredPermission] = []
        seen_find_execution: set[str] = set()

        for part in command_parts:
            if matched := self._find_denylist_match(part):
                return PermissionContext(
                    permission=ToolPermission.NEVER,
                    reason=(
                        f"Command denied: '{part}' matches denylist pattern '{matched}'. "
                        f"Blocked for safety and efficiency: this command is an interactive tool "
                        f"that cannot be used through the bash tool, or is dangerously destructive. "
                        f"Reconsider your approach if you are not attempting something hazardous."
                    ),
                )
            if self._is_standalone_denylisted(part):
                return PermissionContext(
                    permission=ToolPermission.NEVER,
                    reason=(
                        f"Command denied: '{part}' is not allowed as a standalone command. "
                        f"Interactive interpreters, shells, and editors cannot be used through "
                        f"the bash tool — they require a TTY and will hang. "
                        f"Use the appropriate tool instead (e.g., write_file for editing, "
                        f"or pass arguments to run a script)."
                    ),
                )
            if not self._has_find_execution_predicate(part):
                continue
            if part in seen_find_execution:
                continue
            seen_find_execution.add(part)
            find_execution_required.append(
                self._build_command_required_permission(
                    invocation_pattern=part, session_pattern=part, label=part
                )
            )

        if not find_execution_required:
            return None
        return PermissionContext(
            permission=ToolPermission.ASK, required_permissions=find_execution_required
        )

    def _is_unconditionally_allowed(
        self, command_parts: list[str], outside_dirs: set[str]
    ) -> bool:
        if any(self._is_sensitive(part) for part in command_parts):
            return False

        if self.config.permission == ToolPermission.ALWAYS:
            return True

        return all(self._is_allowlisted(part) for part in command_parts) and (
            not outside_dirs
        )

    def _build_required_permissions(
        self, command_parts: list[str], outside_dirs: set[str]
    ) -> list[RequiredPermission]:
        required: list[RequiredPermission] = []
        seen_session: set[str] = set()

        for part in command_parts:
            if not part:
                continue
            tokens = part.split()
            if not tokens:
                continue

            is_sensitive = self._is_sensitive(part)
            if not is_sensitive and self._is_allowlisted(part):
                continue

            if is_sensitive:
                required.append(
                    self._build_command_required_permission(
                        invocation_pattern=part, session_pattern=part, label=part
                    )
                )
                continue

            session_pat = build_session_pattern(tokens)
            if session_pat in seen_session:
                continue
            seen_session.add(session_pat)
            required.append(
                self._build_command_required_permission(
                    invocation_pattern=part,
                    session_pattern=session_pat,
                    label=session_pat,
                )
            )

        for glob in sorted(str(Path(d) / "*") for d in outside_dirs):
            required.append(self._build_outside_directory_permission(glob))

        return required

    def resolve_permission(self, args: BashArgs) -> PermissionContext | None:
        if is_windows():
            return None

        command_parts = _extract_commands(args.command)
        if not command_parts:
            return None

        guardrail_permission = self._resolve_guardrail_permission(command_parts)
        if (
            guardrail_permission
            and guardrail_permission.permission == ToolPermission.NEVER
        ):
            return guardrail_permission
        outside_dirs = _collect_outside_dirs(command_parts)
        has_redirect = _has_output_redirection(args.command)
        if (
            self._is_unconditionally_allowed(command_parts, outside_dirs)
            and not guardrail_permission
            and not has_redirect
        ):
            return PermissionContext(permission=ToolPermission.ALWAYS)

        required = self._build_required_permissions(command_parts, outside_dirs)
        if guardrail_permission:
            required.extend(guardrail_permission.required_permissions)

        if not required:
            if has_redirect:
                required = []
            else:
                return None

        if has_redirect and not guardrail_permission:
            if self.config.permission == ToolPermission.NEVER:
                perm = ToolPermission.NEVER
                reason = (
                    "Output redirection blocked: writing to files is not allowed for safety. "
                    "Complete all read-only work first. If you genuinely need to write files, "
                    "ask the user for write permissions instead of attempting workarounds."
                )
            else:
                perm = ToolPermission.ASK
                reason = None
        elif self.config.permission == ToolPermission.NEVER:
            perm = ToolPermission.NEVER
            reason = (
                f"Command not allowlisted: {'; '.join(rp.label for rp in required)}. "
                f"Writing to files is not allowed for safety. "
                f"Complete all read-only work first. If you genuinely need to write files, "
                f"ask the user for write permissions instead of attempting workarounds."
            )
        else:
            perm = ToolPermission.ASK
            reason = None
        return PermissionContext(
            permission=perm, required_permissions=required, reason=reason
        )

    @final
    def _build_timeout_error(
        self, command: str, timeout: int, stdout: str, stderr: str
    ) -> ToolError:
        error_msg = f"Command timed out after {timeout}s: {command!r}"
        if stdout:
            error_msg += f"\nPartial stdout:\n{stdout}"
        if stderr:
            error_msg += f"\nPartial stderr:\n{stderr}"
        return ToolError(error_msg)

    @final
    def _build_result(
        self, *, command: str, stdout: str, stderr: str, returncode: int
    ) -> BashResult:
        if returncode != 0:
            error_msg = f"Command failed: {command!r}\n"
            error_msg += f"Return code: {returncode}"
            if stderr:
                error_msg += f"\nStderr: {stderr}"
            if stdout:
                error_msg += f"\nStdout: {stdout}"
            raise ToolError(error_msg.strip())

        return BashResult(
            command=command, stdout=stdout, stderr=stderr, returncode=returncode
        )

    async def _execute_with_timeout(
        self,
        proc: asyncio.subprocess.Process,
        timeout: int,
        max_bytes: int,
        command: str,
    ) -> tuple[str, str]:
        """Execute process with timeout, capturing partial output on timeout.

        Returns (stdout, stderr). Raises ToolError on timeout with partial output.
        """
        stdout_buffer = bytearray()
        stderr_buffer = bytearray()
        encoding = _get_subprocess_encoding()

        def decode_output(buffer: bytearray) -> str:
            return (
                buffer.decode(encoding, errors="replace")[:max_bytes] if buffer else ""
            )

        async def read_stream(stream: asyncio.StreamReader, buffer: bytearray) -> None:
            """Read from stream and append to buffer."""
            while True:
                data = await stream.read(4096)
                if not data:
                    break
                buffer.extend(data)

        assert proc.stdout is not None
        assert proc.stderr is not None

        stdout_task = asyncio.create_task(read_stream(proc.stdout, stdout_buffer))
        stderr_task = asyncio.create_task(read_stream(proc.stderr, stderr_buffer))

        await asyncio.wait({stdout_task, stderr_task}, timeout=timeout)

        if not stdout_task.done() or not stderr_task.done():
            for task in [stdout_task, stderr_task]:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

            await kill_async_subprocess(proc)
            await proc.wait()

            stdout = decode_output(stdout_buffer)
            stderr = decode_output(stderr_buffer)

            raise self._build_timeout_error(command, timeout, stdout, stderr)

        stdout_task.result()
        stderr_task.result()

        return decode_output(stdout_buffer), decode_output(stderr_buffer)

    async def run(
        self, args: BashArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | BashResult, None]:
        timeout = args.timeout
        max_bytes = self.config.max_output_bytes

        from vibe.core.logger import logger

        logger.debug("Config: %s", self.config)

        proc = None
        try:
            # start_new_session is Unix-only, on Windows it's ignored
            kwargs: dict[Literal["start_new_session"], bool] = (
                {} if is_windows() else {"start_new_session": True}
            )

            proc = await asyncio.create_subprocess_shell(
                args.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
                env=_get_base_env(),
                executable=_get_shell_executable(),
                **kwargs,
            )

            stdout, stderr = await self._execute_with_timeout(
                proc, timeout, max_bytes, args.command
            )

            returncode = proc.returncode or 0

            yield self._build_result(
                command=args.command,
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            )

        except (ToolError, asyncio.CancelledError):
            raise
        except Exception as exc:
            raise ToolError(f"Error running command {args.command!r}: {exc}") from exc
        finally:
            if proc is not None:
                await kill_async_subprocess(proc)
