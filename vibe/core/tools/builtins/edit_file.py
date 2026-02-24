from __future__ import annotations

from collections.abc import AsyncGenerator
import difflib
from pathlib import Path
from typing import ClassVar, NamedTuple, final

import anyio
from pydantic import BaseModel, Field

from vibe.core.lsp import LSPClientManager, LSPDiagnosticFormatter
from vibe.core.tools.base import (
    BaseTool,
    BaseToolConfig,
    BaseToolState,
    InvokeContext,
    ToolError,
    ToolPermission,
)
from vibe.core.tools.ui import ToolCallDisplay, ToolResultDisplay, ToolUIData
from vibe.core.types import ToolCallEvent, ToolResultEvent, ToolStreamEvent
import shutil


class EditFileArgs(BaseModel):
    file_path: str
    old_string: str = Field(
        description=(
            "The exact literal text to replace, preferably unescaped. For "
            "single replacements (default), include at least 3 lines of context BEFORE "
            "and AFTER the target text, matching whitespace and indentation precisely. "
            "If this string is not the exact literal text (i.e. you escaped it) or does "
            "not match exactly, the tool will fail."
        )
    )
    new_string: str = Field(
        description=(
            "The exact literal text to replace `old_string` with, "
            "preferably unescaped. Provide the EXACT text. Ensure the resulting code is "
            "correct and idiomatic."
        )
    )
    replace_all: bool = Field(
        default=False,
        description="Replace all occurrences of old_string (default false).",
    )


class EditFileResult(BaseModel):
    file: str
    blocks_applied: int
    lines_changed: int
    warnings: list[str] = Field(default_factory=list)
    content: str
    lsp_diagnostics: str | None = Field(
        default=None,
        description="Formatted LSP diagnostics for the modified file, if available"
    )


class EditFileConfig(BaseToolConfig):
    max_content_size: int = 100_000
    create_backup: bool = False
    fuzzy_threshold: float = 0.9


class FuzzyMatch(NamedTuple):
    similarity: float
    start_line: int
    end_line: int
    text: str


class EditFileState(BaseToolState):
    pass


class EditFile(
    BaseTool[EditFileArgs, EditFileResult, EditFileConfig, EditFileState],
    ToolUIData[EditFileArgs, EditFileResult],
):
    description: ClassVar[str] = (
        "Replaces text within a file. By default, replaces a single "
        "occurrence. Set `replace_all` to true when you intend to modify every "
        "instance of `old_string`. This tool requires providing significant "
        "context around the change to ensure precise targeting. Always use the "
        "read_file tool to examine the file's current content before "
        "attempting a text replacement."
    )

    @classmethod
    def get_call_display(cls, event: ToolCallEvent) -> ToolCallDisplay:
        if not isinstance(event.args, EditFileArgs):
            return ToolCallDisplay(summary="Invalid arguments")

        args = event.args
        occurrences = "all" if args.replace_all else "single"
        return ToolCallDisplay(
            summary=f"Patching {args.file_path} ({occurrences} occurrence)",
            content=f"old_string: {args.old_string[:100]}{'...' if len(args.old_string) > 100 else ''}",
        )

    @classmethod
    def get_result_display(cls, event: ToolResultEvent) -> ToolResultDisplay:
        if isinstance(event.result, EditFileResult):
            return ToolResultDisplay(
                success=True,
                message=f"Applied {event.result.blocks_applied} block{'' if event.result.blocks_applied == 1 else 's'}",
                warnings=event.result.warnings,
            )

        return ToolResultDisplay(success=True, message="File edited")

    @classmethod
    def get_status_text(cls) -> str:
        return "Editing files"

    def check_allowlist_denylist(self, args: EditFileArgs) -> ToolPermission | None:
        import fnmatch

        file_path = Path(args.file_path).expanduser()
        if not file_path.is_absolute():
            file_path = Path.cwd() / file_path
        file_str = str(file_path)

        for pattern in self.config.denylist:
            if fnmatch.fnmatch(file_str, pattern):
                return ToolPermission.NEVER

        for pattern in self.config.allowlist:
            if fnmatch.fnmatch(file_str, pattern):
                return ToolPermission.ALWAYS

        return None

    @final
    async def run(
        self, args: EditFileArgs, ctx: InvokeContext | None = None
    ) -> AsyncGenerator[ToolStreamEvent | EditFileResult, None]:
        file_path = self._prepare_and_validate_args(args)

        original_content = await self._read_file(file_path)

        # Count occurrences
        occurrences = original_content.count(args.old_string)

        # Check if old_string exists in content
        if occurrences == 0:
            context = EditFile._find_context(original_content, args.old_string)
            fuzzy_context = EditFile._find_fuzzy_match_context(
                original_content, args.old_string, self.config.fuzzy_threshold
            )
            
            error_msg = (
                f"old_string not found in file: {file_path}\n"
                "Make sure the exact literal text (including all whitespace, indentation, "
                "and newlines) matches exactly what's in the file.\n"
                "Debugging tips:\n"
                "1. Check for exact whitespace/indentation match\n"
                "2. Verify line endings match the file exactly (\\r\\n vs \\n)\n"
                "3. Ensure the old_string hasn't been modified by previous tool calls\n"
                "4. Check for typos or case sensitivity issues"
            )
            
            error_msg += f"\n\nContext analysis:\n{context}"
            
            if fuzzy_context:
                error_msg += f"\n\n{fuzzy_context}"
            
            raise ToolError(error_msg)

        # Warn if multiple occurrences (unless replace_all is True)
        warnings: list[str] = []
        if occurrences > 1 and not args.replace_all:
            context = EditFile._find_context(original_content, args.old_string)
            warning_msg = (
                f"old_string appears {occurrences} times in the file. "
                f"Only the first occurrence will be replaced. Consider making your "
                f"old_string more specific to avoid unintended changes.\n"
                f"\nPotential locations:\n{context}"
            )
            warnings.append(warning_msg)

        # Perform replacement
        if args.replace_all:
            modified_content = original_content.replace(args.old_string, args.new_string)
            occurrences_replaced = occurrences
        else:
            modified_content = original_content.replace(args.old_string, args.new_string, 1)
            occurrences_replaced = 1

        # Calculate line changes
        original_lines = len(original_content.splitlines())
        new_lines = len(modified_content.splitlines())
        lines_changed = new_lines - original_lines

        try:
            if self.config.create_backup:
                await self._backup_file(file_path)
        except Exception:
            # Don't fail the operation if backup fails
            pass

        await self._write_file(file_path, modified_content)

        # Automatically check for LSP diagnostics after modification
        lsp_diagnostics = None
        try:
            client_manager = LSPClientManager()
            diagnostics_list = await client_manager.get_diagnostics_from_all_servers(file_path)

            # Format diagnostics for LLM consumption if available
            if diagnostics_list:
                lsp_diagnostics = LSPDiagnosticFormatter.format_diagnostics_for_llm(
                    diagnostics_list, file_path
                )
        except Exception:
            # Don't fail the edit_file operation if LSP fails
            pass

        # Generate unified diff between old and new content
        diff = EditFile._create_unified_diff(
            original_content, modified_content, "ORIGINAL", "MODIFIED"
        )

        yield EditFileResult(
            file=str(file_path),
            blocks_applied=occurrences_replaced,
            lines_changed=lines_changed,
            warnings=warnings,
            content=diff,
            lsp_diagnostics=lsp_diagnostics,
        )

    @final
    def _prepare_and_validate_args(
        self, args: EditFileArgs
    ) -> Path:
        file_path_str = args.file_path.strip()
        old_string = args.old_string
        new_string = args.new_string

        # Validate file_path is absolute
        if not file_path_str.startswith("/"):
            raise ToolError(
                f"file_path must be an absolute path, got: {file_path_str}"
            )

        content_bytes = len((old_string + new_string).encode("utf-8"))
        if content_bytes > self.config.max_content_size:
            raise ToolError(
                f"Content size ({content_bytes} bytes) exceeds max_content_size "
                f"({self.config.max_content_size} bytes)"
            )

        # Validate old_string and new_string are not empty
        if not old_string:
            raise ToolError("old_string cannot be empty")
        if not new_string:
            raise ToolError("new_string cannot be empty")

        # Expand user home directory and resolve to absolute path
        file_path = Path(file_path_str).expanduser().resolve()

        # Validate file exists
        if not file_path.exists():
            raise ToolError(f"File does not exist: {file_path}")

        # Validate it's a file
        if not file_path.is_file():
            raise ToolError(f"Path is not a file: {file_path}")

        return file_path

    async def _read_file(self, file_path: Path) -> str:
        try:
            async with await anyio.Path(file_path).open(encoding="utf-8") as f:
                return await f.read()
        except UnicodeDecodeError as e:
            raise ToolError(f"Unicode decode error reading {file_path}: {e}") from e
        except PermissionError:
            raise ToolError(f"Permission denied reading file: {file_path}")
        except Exception as e:
            raise ToolError(f"Unexpected error reading {file_path}: {e}") from e

    async def _backup_file(self, file_path: Path) -> None:
        shutil.copy2(file_path, file_path.with_suffix(file_path.suffix + ".bak"))

    async def _write_file(self, file_path: Path, content: str) -> None:
        try:
            async with await anyio.Path(file_path).open(
                mode="w", encoding="utf-8"
            ) as f:
                await f.write(content)
        except PermissionError:
            raise ToolError(f"Permission denied writing to file: {file_path}")
        except OSError as e:
            raise ToolError(f"OS error writing to {file_path}: {e}") from e
        except Exception as e:
            raise ToolError(f"Unexpected error writing to {file_path}: {e}") from e

    @staticmethod
    def _find_context(
        content: str, target_text: str, max_context: int = 5
    ) -> str:
        """Find lines containing target_text and return context around each match."""
        lines = content.split("\n")
        target_lines = target_text.split("\n")

        if not target_lines:
            return "Target text is empty"

        first_target_line = target_lines[0].strip()
        if not first_target_line:
            return "First line of target text is empty or whitespace only"

        matches = []
        for i, line in enumerate(lines):
            if first_target_line in line:
                matches.append(i)

        if not matches:
            return f"First target line '{first_target_line}' not found anywhere in file"

        context_lines = []
        for match_idx in matches[:3]:
            start = max(0, match_idx - max_context)
            end = min(len(lines), match_idx + max_context + 1)

            context_lines.append(f"\nPotential match area around line {match_idx + 1}:")
            for i in range(start, end):
                marker = ">>>" if i == match_idx else "   "
                context_lines.append(f"{marker} {i + 1:3d}: {lines[i]}")

        return "\n".join(context_lines)

    @staticmethod
    def _find_fuzzy_match_context(
        content: str, search_text: str, threshold: float = 0.9
    ) -> str | None:
        """Find closest fuzzy match to search_text in content."""
        best_match = EditFile._find_best_fuzzy_match(content, search_text, threshold)

        if not best_match:
            return None

        diff = EditFile._create_unified_diff(
            search_text, best_match.text, "SEARCH", "CLOSEST MATCH"
        )

        similarity_pct = best_match.similarity * 100

        return (
            f"Closest fuzzy match (similarity {similarity_pct:.1f}%) "
            f"at lines {best_match.start_line}–{best_match.end_line}:\n"
            f"```diff\n{diff}\n```"
        )

    @staticmethod
    def _find_best_fuzzy_match(  # noqa: PLR0914
        content: str, search_text: str, threshold: float = 0.9
    ) -> FuzzyMatch | None:
        """Find the best fuzzy match for search_text in content."""
        content_lines = content.split("\n")
        search_lines = search_text.split("\n")
        window_size = len(search_lines)

        if window_size == 0:
            return None

        non_empty_search = [line for line in search_lines if line.strip()]
        if not non_empty_search:
            return None

        first_anchor = non_empty_search[0]
        last_anchor = (
            non_empty_search[-1] if len(non_empty_search) > 1 else first_anchor
        )

        candidate_starts = set()
        spread = 5

        for i, line in enumerate(content_lines):
            if first_anchor in line or last_anchor in line:
                start_min = max(0, i - spread)
                start_max = min(len(content_lines) - window_size + 1, i + spread + 1)
                for s in range(start_min, start_max):
                    candidate_starts.add(s)

        if not candidate_starts:
            max_positions = min(len(content_lines) - window_size + 1, 100)
            candidate_starts = set(range(0, max_positions))

        best_match = None
        best_similarity = 0.0

        for start in candidate_starts:
            end = start + window_size
            window_text = "\n".join(content_lines[start:end])

            matcher = difflib.SequenceMatcher(None, search_text, window_text)
            similarity = matcher.ratio()

            if similarity >= threshold and similarity > best_similarity:
                best_similarity = similarity
                best_match = FuzzyMatch(
                    similarity=similarity,
                    start_line=start + 1,  # 1-based line numbers
                    end_line=end,
                    text=window_text,
                )

        return best_match

    @staticmethod
    def _create_unified_diff(
        text1: str, text2: str, label1: str = "SEARCH", label2: str = "CLOSEST MATCH"
    ) -> str:
        """Create a unified diff between two texts."""
        lines1 = text1.splitlines(keepends=True)
        lines2 = text2.splitlines(keepends=True)

        lines1 = [line if line.endswith("\n") else line + "\n" for line in lines1]
        lines2 = [line if line.endswith("\n") else line + "\n" for line in lines2]

        diff = difflib.unified_diff(
            lines1, lines2, fromfile=label1, tofile=label2, lineterm="", n=3
        )

        diff_lines = list(diff)

        # Ensure all diff lines end with newline for proper formatting
        diff_lines = [line if line.endswith("\n") else line + "\n" for line in diff_lines]

        result = "".join(diff_lines)

        max_chars = 2000
        if len(result) > max_chars:
            result = result[:max_chars] + "\n...(diff truncated)"

        return result.rstrip()