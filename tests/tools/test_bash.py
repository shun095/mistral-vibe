from __future__ import annotations

import pytest

from tests.mock.utils import collect_result
from vibe.core.scratchpad import init_scratchpad
from vibe.core.tools.base import BaseToolState, ToolError, ToolPermission
from vibe.core.tools.builtins.bash import Bash, BashArgs, BashToolConfig
from vibe.core.tools.permissions import PermissionContext


@pytest.fixture
def bash(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = BashToolConfig()
    return Bash(config_getter=lambda: config, state=BaseToolState())


@pytest.mark.asyncio
async def test_runs_echo_successfully(bash):
    result = await collect_result(bash.run(BashArgs(command="echo hello", timeout=10)))

    assert result.returncode == 0
    assert result.stdout == "hello\n"
    assert result.stderr == ""


@pytest.mark.asyncio
async def test_fails_cat_command_with_missing_file(bash):
    with pytest.raises(ToolError) as err:
        await collect_result(
            bash.run(BashArgs(command="cat missing_file.txt", timeout=10))
        )

    message = str(err.value)
    assert "Command failed" in message
    assert "Return code: 1" in message
    assert "No such file or directory" in message


@pytest.mark.asyncio
async def test_uses_effective_workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = BashToolConfig()
    bash_tool = Bash(config_getter=lambda: config, state=BaseToolState())

    result = await collect_result(bash_tool.run(BashArgs(command="pwd", timeout=10)))

    assert result.stdout.strip() == str(tmp_path)


@pytest.mark.asyncio
async def test_handles_timeout(bash):
    with pytest.raises(ToolError) as err:
        await collect_result(bash.run(BashArgs(command="sleep 2", timeout=1)))

    assert "Command timed out after 1s" in str(err.value)


@pytest.mark.asyncio
async def test_timeout_includes_partial_output(bash):
    """Test that partial stdout/stderr is captured when command times out."""
    with pytest.raises(ToolError) as err:
        await collect_result(
            bash.run(
                BashArgs(
                    command="echo 'line 1' && echo 'line 2' && sleep 2 && echo 'line 3'",
                    timeout=1,
                )
            )
        )

    error_msg = str(err.value)
    assert "Command timed out after 1s" in error_msg
    assert "Partial stdout:" in error_msg
    assert "line 1" in error_msg
    assert "line 2" in error_msg
    # Verify the partial output section contains only line 1 and line 2
    partial_stdout_start = error_msg.find("Partial stdout:\n")
    assert partial_stdout_start != -1
    partial_stdout = error_msg[partial_stdout_start + len("Partial stdout:\n") :]
    assert "line 1" in partial_stdout
    assert "line 2" in partial_stdout
    assert (
        "line 3" not in partial_stdout
    )  # This should not appear (printed after timeout)


@pytest.mark.asyncio
async def test_truncates_output_to_max_bytes(bash):
    config = BashToolConfig(max_output_bytes=5)
    bash_tool = Bash(config_getter=lambda: config, state=BaseToolState())

    result = await collect_result(
        bash_tool.run(BashArgs(command="printf 'abcdefghij'", timeout=10))
    )

    assert result.stdout == "abcde"
    assert result.stderr == ""
    assert result.returncode == 0


@pytest.mark.asyncio
async def test_decodes_non_utf8_bytes(bash):
    result = await collect_result(
        bash.run(BashArgs(command="printf '\\xff\\xfe'", timeout=10))
    )

    # accept both possible encodings, as some shells emit escaped bytes as literal strings
    assert result.stdout in {"��", "\xff\xfe", r"\xff\xfe"}
    assert result.stderr == ""


def test_find_not_in_default_allowlist():
    bash_tool = Bash(config_getter=lambda: BashToolConfig(), state=BaseToolState())
    # find -exec runs arbitrary commands; must not be allowlisted by default
    permission = bash_tool.resolve_permission(
        BashArgs(command="find . -exec id \\;", timeout=10)
    )
    assert (
        not isinstance(permission, PermissionContext)
        or permission.permission is not ToolPermission.ALWAYS
    )


@pytest.mark.parametrize("predicate", ["-exec", "-execdir", "-ok", "-okdir"])
def test_find_execution_predicates_force_ask(predicate: str):
    config = BashToolConfig(permission=ToolPermission.ALWAYS)
    bash_tool = Bash(config_getter=lambda: config, state=BaseToolState())

    permission = bash_tool.resolve_permission(
        BashArgs(command=f"find . {predicate} id \\;", timeout=10)
    )

    assert isinstance(permission, PermissionContext)
    assert permission.permission is ToolPermission.ASK
    assert [required.label for required in permission.required_permissions] == [
        f"find . {predicate} id \\;"
    ]


def test_find_exec_compound_includes_companion_required_permission():
    config = BashToolConfig(permission=ToolPermission.ALWAYS)
    bash_tool = Bash(config_getter=lambda: config, state=BaseToolState())

    permission = bash_tool.resolve_permission(
        BashArgs(command='find . -exec id \\; && python3 -c "import os"', timeout=10)
    )

    assert isinstance(permission, PermissionContext)
    assert permission.permission is ToolPermission.ASK
    labels = {rp.label for rp in permission.required_permissions}
    assert any("find" in label for label in labels), (
        f"Expected a find-exec RequiredPermission, got {labels}"
    )
    assert any("python3" in label for label in labels), (
        f"Companion command should also require permission, got {labels}"
    )


def test_find_execution_predicate_does_not_override_denylist():
    config = BashToolConfig(denylist=["passwd"])
    bash_tool = Bash(config_getter=lambda: config, state=BaseToolState())

    permission = bash_tool.resolve_permission(
        BashArgs(command="find . -exec id \\; && passwd root", timeout=10)
    )

    assert isinstance(permission, PermissionContext)
    assert permission.permission is ToolPermission.NEVER
    assert "matches denylist pattern 'passwd'" in (permission.reason or "")


def test_resolve_permission():
    config = BashToolConfig(allowlist=["echo", "pwd"], denylist=["rm"])
    bash_tool = Bash(config_getter=lambda: config, state=BaseToolState())

    allowlisted = bash_tool.resolve_permission(BashArgs(command="echo hi", timeout=10))
    denylisted = bash_tool.resolve_permission(
        BashArgs(command="rm -rf /tmp", timeout=10)
    )
    mixed = bash_tool.resolve_permission(BashArgs(command="pwd && whoami", timeout=10))
    empty = bash_tool.resolve_permission(BashArgs(command="", timeout=10))

    assert isinstance(allowlisted, PermissionContext)
    assert allowlisted.permission is ToolPermission.ALWAYS
    assert isinstance(denylisted, PermissionContext)
    assert denylisted.permission is ToolPermission.NEVER
    assert isinstance(mixed, PermissionContext)
    assert mixed.permission is ToolPermission.ASK
    assert any(rp.label == "whoami *" for rp in mixed.required_permissions)
    assert empty is None


class TestResolvePermissionWindowsSyntax:
    """Verify allowlist/denylist works with Windows-style commands."""

    def _make_bash(self, **kwargs) -> Bash:
        config = BashToolConfig(**kwargs)
        return Bash(config_getter=lambda: config, state=BaseToolState())

    def test_dir_with_windows_flags_allowlisted(self):
        bash_tool = self._make_bash(allowlist=["dir"])
        result = bash_tool.resolve_permission(BashArgs(command="dir /s /b", timeout=10))
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ALWAYS

    def test_type_command_allowlisted(self):
        bash_tool = self._make_bash(allowlist=["type"])
        result = bash_tool.resolve_permission(
            BashArgs(command="type file.txt", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ALWAYS

    def test_findstr_allowlisted(self):
        bash_tool = self._make_bash(allowlist=["findstr"])
        result = bash_tool.resolve_permission(
            BashArgs(command="findstr /s pattern *.txt", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ALWAYS

    def test_ver_allowlisted(self):
        bash_tool = self._make_bash(allowlist=["ver"])
        result = bash_tool.resolve_permission(BashArgs(command="ver", timeout=10))
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ALWAYS

    def test_where_allowlisted(self):
        bash_tool = self._make_bash(allowlist=["where"])
        result = bash_tool.resolve_permission(
            BashArgs(command="where python", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ALWAYS

    def test_cmd_k_denylisted(self):
        bash_tool = self._make_bash(denylist=["cmd /k"])
        result = bash_tool.resolve_permission(
            BashArgs(command="cmd /k something", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.NEVER

    def test_powershell_noexit_denylisted(self):
        bash_tool = self._make_bash(denylist=["powershell -NoExit"])
        result = bash_tool.resolve_permission(
            BashArgs(command="powershell -NoExit", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.NEVER

    def test_notepad_denylisted(self):
        bash_tool = self._make_bash(denylist=["notepad"])
        result = bash_tool.resolve_permission(
            BashArgs(command="notepad file.txt", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.NEVER

    def test_cmd_standalone_denylisted(self):
        bash_tool = self._make_bash(denylist_standalone=["cmd"])
        result = bash_tool.resolve_permission(BashArgs(command="cmd", timeout=10))
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.NEVER

    def test_powershell_standalone_denylisted(self):
        bash_tool = self._make_bash(denylist_standalone=["powershell"])
        result = bash_tool.resolve_permission(
            BashArgs(command="powershell", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.NEVER

    def test_powershell_cmdlet_asks(self):
        bash_tool = self._make_bash(allowlist=["dir", "echo"])
        result = bash_tool.resolve_permission(
            BashArgs(command="Get-ChildItem -Path .", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission == ToolPermission.ASK

    def test_mixed_allowed_and_unknown_asks(self):
        bash_tool = self._make_bash(allowlist=["git status"])
        result = bash_tool.resolve_permission(
            BashArgs(command="git status && npm install", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission == ToolPermission.ASK

    def test_chained_windows_commands_all_allowed(self):
        bash_tool = self._make_bash(allowlist=["dir", "echo"])
        result = bash_tool.resolve_permission(
            BashArgs(command="dir /s && echo done", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ALWAYS

    def test_chained_commands_one_denied(self):
        bash_tool = self._make_bash(allowlist=["dir"], denylist=["rm"])
        result = bash_tool.resolve_permission(
            BashArgs(command="dir /s && rm -rf /", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.NEVER

    def test_piped_windows_commands(self):
        bash_tool = self._make_bash(allowlist=["findstr", "type"])
        result = bash_tool.resolve_permission(
            BashArgs(command="type file.txt | findstr pattern", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ALWAYS


class TestDenylistWordBoundary:
    """Verify denylist matches whole command names, not prefixes."""

    def _make_bash(self, **kwargs) -> Bash:
        config = BashToolConfig(**kwargs)
        return Bash(config_getter=lambda: config, state=BaseToolState())

    def test_vi_blocks_vi_exact(self):
        bash_tool = self._make_bash(denylist=["vi"])
        result = bash_tool.resolve_permission(BashArgs(command="vi", timeout=10))
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.NEVER

    def test_vi_blocks_vi_with_args(self):
        bash_tool = self._make_bash(denylist=["vi"])
        result = bash_tool.resolve_permission(
            BashArgs(command="vi file.txt", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.NEVER

    def test_vi_does_not_block_vibe(self):
        bash_tool = self._make_bash(denylist=["vi"])
        result = bash_tool.resolve_permission(
            BashArgs(command="vibe -p hello", timeout=10)
        )
        assert result is None or result.permission is not ToolPermission.NEVER

    def test_multiword_pattern_still_works(self):
        bash_tool = self._make_bash(denylist=["bash -i"])
        result = bash_tool.resolve_permission(BashArgs(command="bash -i", timeout=10))
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.NEVER

    def test_multiword_pattern_with_trailing_args(self):
        bash_tool = self._make_bash(denylist=["bash -i"])
        result = bash_tool.resolve_permission(
            BashArgs(command="bash -i extra", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.NEVER

    def test_multiword_pattern_does_not_match_partial(self):
        bash_tool = self._make_bash(denylist=["bash -i"])
        result = bash_tool.resolve_permission(
            BashArgs(command="bash -init", timeout=10)
        )
        assert result is None or result.permission is not ToolPermission.NEVER

    def test_deny_reason_is_set(self):
        bash_tool = self._make_bash(denylist=["vim"])
        result = bash_tool.resolve_permission(
            BashArgs(command="vim file.txt", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.reason is not None
        assert "vim" in result.reason

    def test_standalone_deny_reason_is_set(self):
        bash_tool = self._make_bash(denylist_standalone=["python"])
        result = bash_tool.resolve_permission(BashArgs(command="python", timeout=10))
        assert isinstance(result, PermissionContext)
        assert result.reason is not None
        assert result.permission is ToolPermission.NEVER
        assert "python" in result.reason
        assert "standalone" in result.reason

    def test_allowlist_does_not_match_prefix(self):
        bash_tool = self._make_bash(allowlist=["cat"])
        result = bash_tool.resolve_permission(BashArgs(command="catalog", timeout=10))
        assert result is not None and result.permission is not ToolPermission.ALWAYS


class TestBashNeverPermission:
    """Test that bash with NEVER permission blocks non-allowlisted commands."""

    @staticmethod
    def _make_bash(**kwargs):
        config = BashToolConfig(**kwargs)
        return Bash(config_getter=lambda: config, state=BaseToolState())

    def test_never_permission_blocks_non_allowlisted(self):
        bash_tool = self._make_bash(
            permission=ToolPermission.NEVER, allowlist=["ls", "cat"]
        )
        result = bash_tool.resolve_permission(BashArgs(command="rm -rf /", timeout=10))
        assert isinstance(result, PermissionContext)
        assert result.permission == ToolPermission.NEVER
        assert result.reason is not None
        assert "not allowlisted" in result.reason

    def test_never_permission_allows_allowlisted(self):
        bash_tool = self._make_bash(
            permission=ToolPermission.NEVER, allowlist=["ls", "cat"]
        )
        result = bash_tool.resolve_permission(BashArgs(command="ls -la", timeout=10))
        assert isinstance(result, PermissionContext)
        assert result.permission == ToolPermission.ALWAYS

    def test_never_permission_still_blocks_denylist(self):
        bash_tool = self._make_bash(
            permission=ToolPermission.NEVER, allowlist=["ls"], denylist=["vim"]
        )
        result = bash_tool.resolve_permission(BashArgs(command="vim file", timeout=10))
        assert isinstance(result, PermissionContext)
        assert result.permission == ToolPermission.NEVER

    def test_ask_permission_still_prompts_for_non_allowlisted(self):
        bash_tool = self._make_bash(
            permission=ToolPermission.ASK, allowlist=["ls", "cat"]
        )
        result = bash_tool.resolve_permission(
            BashArgs(command="pip install x", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission == ToolPermission.ASK


class TestOutputRedirectionBlocking:
    """Test that allowlisted commands with output redirection are not auto-allowed."""

    @staticmethod
    def _make_bash(**kwargs):
        config = BashToolConfig(**kwargs)
        return Bash(config_getter=lambda: config, state=BaseToolState())

    def test_allowlisted_with_output_redirect_not_always(self):
        bash_tool = self._make_bash()
        result = bash_tool.resolve_permission(
            BashArgs(command="cat > file.txt <<'EOF'\nhello\nEOF", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ASK

    def test_allowlisted_with_append_redirect_not_always(self):
        bash_tool = self._make_bash()
        result = bash_tool.resolve_permission(
            BashArgs(command='echo "data" >> file.txt', timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ASK

    def test_allowlisted_with_simple_redirect_not_always(self):
        bash_tool = self._make_bash()
        result = bash_tool.resolve_permission(
            BashArgs(command="ls > listing.txt", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ASK

    def test_allowlisted_without_redirect_still_always(self):
        bash_tool = self._make_bash()
        result = bash_tool.resolve_permission(BashArgs(command="ls -la", timeout=10))
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ALWAYS

    def test_never_permission_blocks_redirect_even_allowlisted(self):
        bash_tool = self._make_bash(
            permission=ToolPermission.NEVER, allowlist=["ls", "cat", "echo"]
        )
        result = bash_tool.resolve_permission(
            BashArgs(command='echo "data" > file.txt', timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.NEVER

    def test_never_permission_blocks_heredoc_redirect(self):
        bash_tool = self._make_bash(
            permission=ToolPermission.NEVER, allowlist=["ls", "cat", "echo"]
        )
        result = bash_tool.resolve_permission(
            BashArgs(command="cat > file.txt <<'EOF'\nhello\nEOF", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.NEVER

    def test_error_redirect_also_blocked(self):
        bash_tool = self._make_bash()
        result = bash_tool.resolve_permission(
            BashArgs(command="ls 2> errors.txt", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ASK

    def test_tee_sensitive_in_default(self):
        bash_tool = self._make_bash()
        assert "tee" in bash_tool.config.sensitive_patterns
        result = bash_tool.resolve_permission(
            BashArgs(command='echo "data" | tee file.txt', timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ASK

    def test_ampersand_gt_redirect_blocked(self):
        """&> redirects both stdout+stderr — should be blocked."""
        bash_tool = self._make_bash()
        result = bash_tool.resolve_permission(
            BashArgs(command='echo "data" &> file.txt', timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ASK

    def test_append_both_redirect_blocked(self):
        """>>& appends both stdout+stderr — should be blocked."""
        bash_tool = self._make_bash()
        result = bash_tool.resolve_permission(
            BashArgs(command='echo "data" >>& file.txt', timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ASK

    def test_process_substitution_output_blocked(self):
        """Process substitution >(cmd) with output redirect — should be blocked."""
        bash_tool = self._make_bash()
        result = bash_tool.resolve_permission(
            BashArgs(command="cat > >(grep foo)", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ASK

    def test_gt_in_string_not_redirect(self):
        """> inside a quoted string is data, not a redirect operator."""
        bash_tool = self._make_bash()
        result = bash_tool.resolve_permission(
            BashArgs(command='echo "a > b"', timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ALWAYS

    def test_gt_in_grep_pattern_not_redirect(self):
        """> as a grep search pattern is data, not a redirect."""
        bash_tool = self._make_bash()
        result = bash_tool.resolve_permission(
            BashArgs(command='grep ">" file.txt', timeout=10)
        )
        # grep is not in default allowlist, so it returns ASK — not ALWAYS
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ASK

    def test_heredoc_input_only_not_redirect(self):
        """Heredoc input (<<) without output redirect is read-only."""
        bash_tool = self._make_bash()
        result = bash_tool.resolve_permission(
            BashArgs(command="cat << 'EOF'\nhello\nEOF", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ALWAYS

    def test_input_redirect_not_output(self):
        """< is input redirection, not output — should be allowed."""
        bash_tool = self._make_bash()
        result = bash_tool.resolve_permission(
            BashArgs(command="cat < input.txt", timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ALWAYS

    def test_pipe_without_redirect_allowed(self):
        """Pipe (|) without output redirect is read-only when both sides are allowlisted."""
        bash_tool = self._make_bash()
        result = bash_tool.resolve_permission(BashArgs(command="ls | head", timeout=10))
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ALWAYS

    def test_heredoc_to_denylisted_interpreter_blocked(self):
        """python heredoc is blocked by standalone denylist, not output redirect check.

        tree-sitter parses `python << 'EOF'` as a `command` node (python) plus a
        separate `heredoc_redirect` node — _has_output_redirection returns False
        because it only inspects `file_redirect` nodes. The block comes from the
        standalone denylist catching bare `python`.
        """
        bash_tool = self._make_bash()
        result = bash_tool.resolve_permission(
            BashArgs(command='python << "EOF"\nopen("x","w")\nEOF', timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.NEVER
        assert "standalone" in (result.reason or "").lower()

    def test_heredoc_to_interpreter_no_output_redirect_flagged(self):
        """Heredoc feeding code to an interpreter is NOT flagged as output redirection.

        The file write happens inside the interpreter, invisible to the shell-level
        _has_output_redirection check. Only the standalone denylist or NEVER permission
        catches it.
        """
        from vibe.core.tools.builtins.bash import _has_output_redirection

        assert not _has_output_redirection('python << "EOF"\nopen("x","w")\nEOF')

    def test_heredoc_to_non_denylisted_interpreter_asks(self):
        """Non-denylisted interpreter via heredoc returns ASK, not NEVER.

        ruby is not on the standalone denylist. The heredoc file-write bypasses the
        output redirection check (heredoc_redirect != file_redirect). In ASK mode
        the command is permitted pending approval — the redirect check never fires.
        """
        bash_tool = self._make_bash()
        result = bash_tool.resolve_permission(
            BashArgs(command='ruby << "EOF"\nFile.open("x","w")\nEOF', timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ASK

    def test_heredoc_to_non_denylisted_interpreter_blocked_in_plan_mode(self):
        """Non-denylisted interpreter via heredoc is blocked in plan mode (NEVER).

        Plan mode sets bash permission to NEVER, catching any non-allowlisted command
        regardless of whether it uses heredoc file writes.
        """
        bash_tool = self._make_bash(
            permission=ToolPermission.NEVER, allowlist=["ls", "cat"]
        )
        result = bash_tool.resolve_permission(
            BashArgs(command='ruby << "EOF"\nFile.open("x","w")\nEOF', timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.NEVER


class TestScratchpadRedirect:
    """Test that redirects to scratchpad are always allowed, even in Plan mode."""

    @staticmethod
    def _make_bash(**kwargs):
        config = BashToolConfig(**kwargs)
        return Bash(config_getter=lambda: config, state=BaseToolState())

    @pytest.fixture(autouse=True)
    def _init_scratchpad(self):
        self.scratchpad = init_scratchpad("test-scratchpad-redirect")

    def test_redirect_to_scratchpad_always_allowed(self):
        """Allowlisted command redirecting to scratchpad should be ALWAYS."""
        bash_tool = self._make_bash()
        result = bash_tool.resolve_permission(
            BashArgs(command=f'echo "data" > {self.scratchpad}/test.txt', timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ALWAYS

    def test_redirect_to_scratchpad_in_plan_mode(self):
        """Scratchpad redirect should be ALWAYS even with NEVER config (Plan mode)."""
        bash_tool = self._make_bash(
            permission=ToolPermission.NEVER, allowlist=["ls", "cat", "echo"]
        )
        result = bash_tool.resolve_permission(
            BashArgs(command=f'echo "data" > {self.scratchpad}/test.txt', timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ALWAYS

    def test_heredoc_redirect_to_scratchpad_in_plan_mode(self):
        """Heredoc redirect to scratchpad should be ALWAYS in Plan mode."""
        bash_tool = self._make_bash(
            permission=ToolPermission.NEVER, allowlist=["ls", "cat", "echo"]
        )
        result = bash_tool.resolve_permission(
            BashArgs(
                command=f"cat > {self.scratchpad}/file.txt <<'EOF'\nhello\nEOF",
                timeout=10,
            )
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ALWAYS

    def test_redirect_to_repo_still_blocked_in_plan_mode(self):
        """Redirect to repo (not scratchpad) should still be blocked in Plan mode."""
        bash_tool = self._make_bash(
            permission=ToolPermission.NEVER, allowlist=["ls", "cat", "echo"]
        )
        result = bash_tool.resolve_permission(
            BashArgs(command='echo "data" > src/test.txt', timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.NEVER

    def test_mixed_redirect_scratchpad_and_repo_asked(self):
        """Redirect to both scratchpad and repo should ASK (not all scratchpad)."""
        bash_tool = self._make_bash()
        result = bash_tool.resolve_permission(
            BashArgs(
                command=f'echo "x" > {self.scratchpad}/a.txt 2> src/b.txt', timeout=10
            )
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ASK

    def test_append_redirect_to_scratchpad_allowed(self):
        """Append redirect (>>) to scratchpad should be ALWAYS."""
        bash_tool = self._make_bash(
            permission=ToolPermission.NEVER, allowlist=["ls", "cat", "echo"]
        )
        result = bash_tool.resolve_permission(
            BashArgs(command=f'echo "more" >> {self.scratchpad}/test.txt', timeout=10)
        )
        assert isinstance(result, PermissionContext)
        assert result.permission is ToolPermission.ALWAYS
