from __future__ import annotations

from collections.abc import MutableMapping
from enum import StrEnum, auto
import os
from pathlib import Path
import re
import shlex
import tomllib
from typing import Annotated, Any, Literal, cast
from urllib.parse import urljoin

from dotenv import dotenv_values

# Magic values for type annotation processing
DICT_ARGS_MIN_LENGTH = 2
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
import tomlkit
from tomlkit.exceptions import TOMLKitError

from vibe.core.config.harness_files import get_harness_files_manager
from vibe.core.logger import logger
from vibe.core.lsp.config import LSPServerConfig
from vibe.core.paths import GLOBAL_ENV_FILE, SESSION_LOG_DIR
from vibe.core.prompts import SystemPrompt
from vibe.core.types import Backend
from vibe.core.utils import get_server_url_from_api_base
from vibe.core.utils.io import read_safe


def load_dotenv_values(
    env_path: Path = GLOBAL_ENV_FILE.path,
    environ: MutableMapping[str, str] = os.environ,
) -> None:
    # We allow FIFO path to support some environment management solutions (e.g. https://developer.1password.com/docs/environments/local-env-file/)
    if not env_path.is_file() and not env_path.is_fifo():
        return

    env_vars = dotenv_values(env_path)
    for key, value in env_vars.items():
        if not value:
            continue
        environ.update({key: value})


class MissingAPIKeyError(RuntimeError):
    def __init__(self, env_key: str, provider_name: str) -> None:
        super().__init__(
            f"Missing {env_key} environment variable for {provider_name} provider"
        )
        self.env_key = env_key
        self.provider_name = provider_name


class MissingPromptFileError(RuntimeError):
    def __init__(self, system_prompt_id: str, *prompt_dirs: str) -> None:
        dirs_str = " or ".join(prompt_dirs) if prompt_dirs else "<no prompt dirs>"
        super().__init__(
            f"Invalid system_prompt_id value: '{system_prompt_id}'. "
            f"Must be one of the available prompts ({', '.join(f'{p.name.lower()}' for p in SystemPrompt)}), "
            f"or correspond to a .md file in {dirs_str}"
        )
        self.system_prompt_id = system_prompt_id


class TomlFileSettingsSource(PydanticBaseSettingsSource):
    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls)
        self.toml_data = self._load_toml()

    def _load_toml(self) -> dict[str, Any]:
        file = get_harness_files_manager().config_file
        if file is None:
            return {}
        try:
            with file.open("rb") as f:
                return tomllib.load(f)
        except FileNotFoundError:
            return {}
        except tomllib.TOMLDecodeError as e:
            raise RuntimeError(f"Invalid TOML in {file}: {e}") from e
        except OSError as e:
            raise RuntimeError(f"Cannot read {file}: {e}") from e

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        return self.toml_data.get(field_name), field_name, False

    def __call__(self) -> dict[str, Any]:
        return self.toml_data


class ProjectContextConfig(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    default_commit_count: int = 5
    timeout_seconds: float = 2.0


class SessionLoggingConfig(BaseSettings):
    save_dir: str = ""
    session_prefix: str = "session"
    enabled: bool = True

    @field_validator("save_dir", mode="before")
    @classmethod
    def set_default_save_dir(cls, v: str) -> str:
        if not v:
            return str(SESSION_LOG_DIR.path)
        return v

    @field_validator("save_dir", mode="after")
    @classmethod
    def expand_save_dir(cls, v: str) -> str:
        return str(Path(v).expanduser().resolve())


class ProviderConfig(BaseModel):
    name: str
    api_base: str
    api_key_env_var: str = ""
    api_style: str = "openai"
    backend: Backend = Backend.GENERIC
    reasoning_field_name: str = "reasoning_content"
    project_id: str = ""
    region: str = ""


class TranscribeClient(StrEnum):
    MISTRAL = auto()


class TranscribeProviderConfig(BaseModel):
    name: str
    api_base: str = "wss://api.mistral.ai"
    api_key_env_var: str = ""
    client: TranscribeClient = TranscribeClient.MISTRAL


class _MCPBase(BaseModel):
    name: str = Field(description="Short alias used to prefix tool names")
    prompt: str | None = Field(
        default=None, description="Optional usage hint appended to tool descriptions"
    )
    startup_timeout_sec: float = Field(
        default=10.0,
        gt=0,
        description="Timeout in seconds for the server to start and initialize.",
    )
    tool_timeout_sec: float = Field(
        default=60.0, gt=0, description="Timeout in seconds for tool execution."
    )
    sampling_enabled: bool = Field(
        default=True,
        description="Allow this MCP server to request LLM completions via sampling/createMessage.",
    )

    @field_validator("name", mode="after")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9_-]", "_", v)
        normalized = normalized.strip("_-")
        return normalized[:256]


class _MCPHttpFields(BaseModel):
    url: str = Field(description="Base URL of the MCP HTTP server")
    headers: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Additional HTTP headers when using 'http' transport (e.g., Authorization or X-API-Key)."
        ),
    )
    api_key_env: str = Field(
        default="",
        description=(
            "Environment variable name containing an API token to send for HTTP transport."
        ),
    )
    api_key_header: str = Field(
        default="Authorization",
        description=(
            "HTTP header name to carry the token when 'api_key_env' is set (e.g., 'Authorization' or 'X-API-Key')."
        ),
    )
    api_key_format: str = Field(
        default="Bearer {token}",
        description=(
            "Format string for the header value when 'api_key_env' is set. Use '{token}' placeholder."
        ),
    )

    def http_headers(self) -> dict[str, str]:
        hdrs = dict(self.headers or {})
        env_var = (self.api_key_env or "").strip()
        if env_var and (token := os.getenv(env_var)):
            target = (self.api_key_header or "").strip() or "Authorization"
            if not any(h.lower() == target.lower() for h in hdrs):
                try:
                    value = (self.api_key_format or "{token}").format(token=token)
                except Exception:
                    value = token
                hdrs[target] = value
        return hdrs


class MCPHttp(_MCPBase, _MCPHttpFields):
    transport: Literal["http"]


class MCPStreamableHttp(_MCPBase, _MCPHttpFields):
    transport: Literal["streamable-http"]


class MCPStdio(_MCPBase):
    transport: Literal["stdio"]
    command: str | list[str]
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables to set for the MCP server process.",
    )

    def argv(self) -> list[str]:
        base = (
            shlex.split(self.command)
            if isinstance(self.command, str)
            else list(self.command or [])
        )
        return [*base, *self.args] if self.args else base


MCPServer = Annotated[
    MCPHttp | MCPStreamableHttp | MCPStdio, Field(discriminator="transport")
]


def _default_alias_to_name(data: Any) -> Any:
    if isinstance(data, dict):
        if "alias" not in data or data["alias"] is None:
            data["alias"] = data.get("name")
    return data


class ModelConfig(BaseModel):
    name: str
    provider: str
    alias: str
    temperature: float | None = None
    input_price: float = 0.0  # Price per million input tokens
    output_price: float = 0.0  # Price per million output tokens
    thinking: Literal["off", "low", "medium", "high"] = "off"
    auto_compact_threshold: int = 200_000

    _default_alias_to_name = model_validator(mode="before")(_default_alias_to_name)


class TranscribeModelConfig(BaseModel):
    name: str
    provider: str
    alias: str
    sample_rate: int = 16000
    encoding: Literal["pcm_s16le"] = "pcm_s16le"
    language: str = "en"
    target_streaming_delay_ms: int = 500

    _default_alias_to_name = model_validator(mode="before")(_default_alias_to_name)


class TTSClient(StrEnum):
    MISTRAL = auto()


class TTSProviderConfig(BaseModel):
    name: str
    api_base: str = "https://api.mistral.ai"
    api_key_env_var: str = ""
    client: TTSClient = TTSClient.MISTRAL


class TTSModelConfig(BaseModel):
    name: str
    provider: str
    alias: str
    voice: str = "gb_jane_neutral"
    response_format: str = "wav"

    _default_alias_to_name = model_validator(mode="before")(_default_alias_to_name)


class OtelExporterConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    endpoint: str
    headers: dict[str, str] | None = None


DEFAULT_MISTRAL_API_ENV_KEY = "MISTRAL_API_KEY"
MISTRAL_OTEL_TRACES_PATH = "/telemetry/v1/traces"
_DEFAULT_MISTRAL_SERVER_URL = "https://api.mistral.ai"

DEFAULT_PROVIDERS = [
    ProviderConfig(
        name="mistral",
        api_base=f"{_DEFAULT_MISTRAL_SERVER_URL}/v1",
        api_key_env_var=DEFAULT_MISTRAL_API_ENV_KEY,
        backend=Backend.MISTRAL,
    ),
    ProviderConfig(
        name="llamacpp",
        api_base="http://127.0.0.1:8080/v1",
        api_key_env_var="",  # NOTE: if you wish to use --api-key in llama-server, change this value
    ),
]

DEFAULT_MODELS = [
    ModelConfig(
        name="mistral-vibe-cli-latest",
        provider="mistral",
        alias="devstral-2",
        input_price=0.4,
        output_price=2.0,
    ),
    ModelConfig(
        name="devstral-small-latest",
        provider="mistral",
        alias="devstral-small",
        input_price=0.1,
        output_price=0.3,
    ),
    ModelConfig(
        name="devstral",
        provider="llamacpp",
        alias="local",
        input_price=0.0,
        output_price=0.0,
    ),
]

DEFAULT_TRANSCRIBE_PROVIDERS = [
    TranscribeProviderConfig(
        name="mistral",
        api_base="wss://api.mistral.ai",
        api_key_env_var=DEFAULT_MISTRAL_API_ENV_KEY,
    )
]

DEFAULT_TRANSCRIBE_MODELS = [
    TranscribeModelConfig(
        name="voxtral-mini-transcribe-realtime-2602",
        provider="mistral",
        alias="voxtral-realtime",
    )
]

DEFAULT_TTS_PROVIDERS = [
    TTSProviderConfig(
        name="mistral",
        api_base="https://api.mistral.ai",
        api_key_env_var=DEFAULT_MISTRAL_API_ENV_KEY,
    )
]

DEFAULT_TTS_MODELS = [
    TTSModelConfig(
        name="voxtral-mini-tts-latest", provider="mistral", alias="voxtral-tts"
    )
]


class VibeConfig(BaseSettings):
    active_model: str = "devstral-2"
    vim_keybindings: bool = False
    disable_welcome_banner_animation: bool = False
    autocopy_to_clipboard: bool = True
    file_watcher_for_autocomplete: bool = False
    displayed_workdir: str = ""
    context_warnings: bool = False
    voice_mode_enabled: bool = False
    narrator_enabled: bool = False
    active_transcribe_model: str = "voxtral-realtime"
    active_tts_model: str = "voxtral-tts"
    auto_approve: bool = False
    enable_telemetry: bool = False
    loop_detection_enabled: bool = True
    loop_detection_threshold: int = 3
    system_prompt_id: str = "cli"
    include_commit_signature: bool = True
    include_model_info: bool = True
    include_project_context: bool = True
    include_prompt_detail: bool = True
    enable_update_checks: bool = True
    enable_auto_update: bool = True
    enable_notifications: bool = True
    enable_web_notifications: bool = True
    api_timeout: float = 720.0
    auto_compact_threshold: int = 200_000

    # TODO(vibe-nuage): remove exclude=True once the feature is publicly available
    nuage_enabled: bool = Field(default=False, exclude=True)
    nuage_base_url: str = Field(default="https://api.globalaegis.net", exclude=True)
    nuage_workflow_id: str = Field(default="__shared-nuage-workflow", exclude=True)
    nuage_task_queue: str | None = Field(default="shared-vibe-nuage", exclude=True)
    # TODO(vibe-nuage): change default value to MISTRAL_API_KEY once prod has shared vibe-nuage workers
    nuage_api_key_env_var: str = Field(default="STAGING_MISTRAL_API_KEY", exclude=True)

    # TODO(otel): remove exclude=True once the feature is publicly available
    enable_otel: bool = Field(default=False, exclude=True)
    otel_endpoint: str = Field(default="", exclude=True)

    providers: list[ProviderConfig] = Field(
        default_factory=lambda: list(DEFAULT_PROVIDERS)
    )
    models: list[ModelConfig] = Field(default_factory=lambda: list(DEFAULT_MODELS))
    compaction_model: ModelConfig | None = None

    transcribe_providers: list[TranscribeProviderConfig] = Field(
        default_factory=lambda: list(DEFAULT_TRANSCRIBE_PROVIDERS)
    )
    transcribe_models: list[TranscribeModelConfig] = Field(
        default_factory=lambda: list(DEFAULT_TRANSCRIBE_MODELS)
    )

    tts_providers: list[TTSProviderConfig] = Field(
        default_factory=lambda: list(DEFAULT_TTS_PROVIDERS)
    )
    tts_models: list[TTSModelConfig] = Field(
        default_factory=lambda: list(DEFAULT_TTS_MODELS)
    )

    project_context: ProjectContextConfig = Field(default_factory=ProjectContextConfig)
    session_logging: SessionLoggingConfig = Field(default_factory=SessionLoggingConfig)
    tools: dict[str, dict[str, Any]] = Field(default_factory=dict)
    tool_paths: list[Path] = Field(
        default_factory=list,
        description=(
            "Additional directories or files to explore for custom tools. "
            "Paths may be absolute or relative to the current working directory. "
            "Directories are shallow-searched for tool definition files, "
            "while files are loaded directly if valid."
        ),
    )

    mcp_servers: list[MCPServer] = Field(
        default_factory=list, description="Preferred MCP server configuration entries."
    )

    lsp_servers: list[LSPServerConfig] = Field(
        default_factory=list,
        description=(
            "List of LSP (Language Server Protocol) server configurations. "
            "Each server can be enabled/disabled and configured with specific options."
        ),
    )

    enabled_tools: list[str] = Field(
        default_factory=list,
        description=(
            "An explicit list of tool names/patterns to enable. If set, only these"
            " tools will be active. Supports glob patterns (e.g., 'serena_*') and"
            " regex with 're:' prefix (e.g., 're:^serena_.*')."
        ),
    )
    disabled_tools: list[str] = Field(
        default_factory=list,
        description=(
            "A list of tool names/patterns to disable. Ignored if 'enabled_tools'"
            " is set. Supports glob patterns and regex with 're:' prefix."
        ),
    )
    agent_paths: list[Path] = Field(
        default_factory=list,
        description=(
            "Additional directories to search for custom agent profiles. "
            "Each path may be absolute or relative to the current working directory."
        ),
    )
    enabled_agents: list[str] = Field(
        default_factory=list,
        description=(
            "An explicit list of agent names/patterns to enable. If set, only these"
            " agents will be available. Supports glob patterns (e.g., 'custom-*')"
            " and regex with 're:' prefix."
        ),
    )
    disabled_agents: list[str] = Field(
        default_factory=list,
        description=(
            "A list of agent names/patterns to disable. Ignored if 'enabled_agents'"
            " is set. Supports glob patterns and regex with 're:' prefix."
        ),
    )
    installed_agents: list[str] = Field(
        default_factory=list,
        description=(
            "A list of opt-in builtin agent names that have been explicitly installed."
        ),
    )
    skill_paths: list[Path] = Field(
        default_factory=list,
        description=(
            "Additional directories to search for skills. "
            "Each path may be absolute or relative to the current working directory."
        ),
    )
    enabled_skills: list[str] = Field(
        default_factory=list,
        description=(
            "An explicit list of skill names/patterns to enable. If set, only these"
            " skills will be active. Supports glob patterns (e.g., 'search-*') and"
            " regex with 're:' prefix."
        ),
    )
    disabled_skills: list[str] = Field(
        default_factory=list,
        description=(
            "A list of skill names/patterns to disable. Ignored if 'enabled_skills'"
            " is set. Supports glob patterns and regex with 're:' prefix."
        ),
    )

    model_config = SettingsConfigDict(
        env_prefix="VIBE_", case_sensitive=False, extra="ignore"
    )

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(**kwargs)

    @property
    def nuage_api_key(self) -> str:
        return os.getenv(self.nuage_api_key_env_var, "")

    @property
    def otel_exporter_config(self) -> OtelExporterConfig | None:
        # When otel_endpoint is set explicitly, authentication is the user's responsibility
        # (via OTEL_EXPORTER_OTLP_* env vars), so headers are left empty.
        # Otherwise endpoint and API key are derived from the first MISTRAL provider.
        if self.otel_endpoint:
            return OtelExporterConfig(endpoint=self.otel_endpoint)

        provider = next(
            (p for p in self.providers if p.backend == Backend.MISTRAL), None
        )

        if provider is not None:
            server_url = get_server_url_from_api_base(provider.api_base)
            api_key_env = provider.api_key_env_var or DEFAULT_MISTRAL_API_ENV_KEY
        else:
            server_url = None
            api_key_env = DEFAULT_MISTRAL_API_ENV_KEY

        endpoint = urljoin(
            server_url or _DEFAULT_MISTRAL_SERVER_URL, MISTRAL_OTEL_TRACES_PATH
        )

        if not (api_key := os.getenv(api_key_env)):
            logger.warning(
                "OTEL tracing enabled but %s is not set; skipping.", api_key_env
            )
            return None

        return OtelExporterConfig(
            endpoint=endpoint, headers={"Authorization": f"Bearer {api_key}"}
        )

    @property
    def system_prompt(self) -> str:
        try:
            return SystemPrompt[self.system_prompt_id.upper()].read()
        except KeyError:
            pass

        mgr = get_harness_files_manager()
        prompt_dirs = mgr.project_prompts_dirs + mgr.user_prompts_dirs
        for current_prompt_dir in prompt_dirs:
            custom_sp_path = (current_prompt_dir / self.system_prompt_id).with_suffix(
                ".md"
            )
            if custom_sp_path.is_file():
                return read_safe(custom_sp_path)

        raise MissingPromptFileError(
            self.system_prompt_id, *(str(d) for d in prompt_dirs)
        )

    def get_active_model(self) -> ModelConfig:
        for model in self.models:
            if model.alias == self.active_model:
                return model
        raise ValueError(
            f"Active model '{self.active_model}' not found in configuration."
        )

    def get_compaction_model(self) -> ModelConfig:
        if self.compaction_model is not None:
            return self.compaction_model
        return self.get_active_model()

    def get_provider_for_model(self, model: ModelConfig) -> ProviderConfig:
        for provider in self.providers:
            if provider.name == model.provider:
                return provider
        raise ValueError(
            f"Provider '{model.provider}' for model '{model.name}' not found in configuration."
        )

    def get_active_transcribe_model(self) -> TranscribeModelConfig:
        for model in self.transcribe_models:
            if model.alias == self.active_transcribe_model:
                return model
        raise ValueError(
            f"Active transcribe model '{self.active_transcribe_model}' not found in configuration."
        )

    def get_transcribe_provider_for_model(
        self, model: TranscribeModelConfig
    ) -> TranscribeProviderConfig:
        for provider in self.transcribe_providers:
            if provider.name == model.provider:
                return provider
        raise ValueError(
            f"Transcribe provider '{model.provider}' for transcribe model '{model.name}' not found in configuration."
        )

    def get_active_tts_model(self) -> TTSModelConfig:
        for model in self.tts_models:
            if model.alias == self.active_tts_model:
                return model
        raise ValueError(
            f"Active TTS model '{self.active_tts_model}' not found in configuration."
        )

    def get_tts_provider_for_model(self, model: TTSModelConfig) -> TTSProviderConfig:
        for provider in self.tts_providers:
            if provider.name == model.provider:
                return provider
        raise ValueError(
            f"TTS provider '{model.provider}' for TTS model '{model.name}' not found in configuration."
        )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Define the priority of settings sources.

        Note: dotenv_settings is intentionally excluded. API keys and other
        non-config environment variables are stored in .env but loaded manually
        into os.environ for use by providers. Only VIBE_* prefixed environment
        variables (via env_settings) and TOML config are used for Pydantic settings.
        """
        return (
            init_settings,
            env_settings,
            TomlFileSettingsSource(settings_cls),
            file_secret_settings,
        )

    @model_validator(mode="after")
    def _apply_global_auto_compact_threshold(self) -> VibeConfig:
        self.models = [
            model
            if "auto_compact_threshold" in model.model_fields_set
            else model.model_copy(
                update={"auto_compact_threshold": self.auto_compact_threshold}
            )
            for model in self.models
        ]
        return self

    @model_validator(mode="after")
    def _check_compaction_model_provider(self) -> VibeConfig:
        if self.compaction_model is None:
            return self

        compaction_provider = self.get_provider_for_model(self.compaction_model)
        try:
            active_provider = self.get_provider_for_model(self.get_active_model())
        except ValueError:
            return self
        if active_provider.name != compaction_provider.name:
            raise ValueError(
                f"Compaction model '{self.compaction_model.alias}' uses provider "
                f"'{compaction_provider.name}' but active model uses provider "
                f"'{active_provider.name}'. They must share the same provider."
            )
        return self

    @model_validator(mode="after")
    def _check_api_key(self) -> VibeConfig:
        try:
            active_model = self.get_active_model()
            provider = self.get_provider_for_model(active_model)
            api_key_env = provider.api_key_env_var
            if api_key_env and not os.getenv(api_key_env):
                raise MissingAPIKeyError(api_key_env, provider.name)
        except ValueError:
            pass
        return self

    @field_validator("tool_paths", mode="before")
    @classmethod
    def _expand_tool_paths(cls, v: Any) -> list[Path]:
        if not v:
            return []
        return [Path(p).expanduser().resolve() for p in v]

    @field_validator("skill_paths", mode="before")
    @classmethod
    def _expand_skill_paths(cls, v: Any) -> list[Path]:
        if not v:
            return []
        return [Path(p).expanduser().resolve() for p in v]

    @field_validator("tools", mode="before")
    @classmethod
    def _normalize_tool_configs(cls, v: Any) -> dict[str, dict[str, Any]]:
        if not isinstance(v, dict):
            return {}

        normalized: dict[str, dict[str, Any]] = {}
        for tool_name, tool_config in v.items():
            if isinstance(tool_config, dict):
                normalized[tool_name] = tool_config
            else:
                normalized[tool_name] = {}

        return normalized

    @model_validator(mode="after")
    def _validate_model_uniqueness(self) -> VibeConfig:
        seen_aliases: set[str] = set()
        for model in self.models:
            if model.alias in seen_aliases:
                raise ValueError(
                    f"Duplicate model alias found: '{model.alias}'. Aliases must be unique."
                )
            seen_aliases.add(model.alias)
        return self

    @model_validator(mode="after")
    def _validate_transcribe_model_uniqueness(self) -> VibeConfig:
        seen_aliases: set[str] = set()
        for model in self.transcribe_models:
            if model.alias in seen_aliases:
                raise ValueError(
                    f"Duplicate transcribe model alias found: '{model.alias}'. Aliases must be unique."
                )
            seen_aliases.add(model.alias)
        return self

    @model_validator(mode="after")
    def _validate_tts_model_uniqueness(self) -> VibeConfig:
        seen_aliases: set[str] = set()
        for model in self.tts_models:
            if model.alias in seen_aliases:
                raise ValueError(
                    f"Duplicate TTS model alias found: '{model.alias}'. Aliases must be unique."
                )
            seen_aliases.add(model.alias)
        return self

    @model_validator(mode="after")
    def _check_system_prompt(self) -> VibeConfig:
        _ = self.system_prompt
        return self

    @classmethod
    def save_updates(cls, updates: dict[str, Any]) -> None:
        if not get_harness_files_manager().persist_allowed:
            return
        current_config = TomlFileSettingsSource(cls).toml_data

        def deep_merge(target: dict, source: dict) -> None:
            for key, value in source.items():
                if (
                    key in target
                    and isinstance(target.get(key), dict)
                    and isinstance(value, dict)
                ):
                    deep_merge(target[key], value)
                elif (
                    key in target
                    and isinstance(target.get(key), list)
                    and isinstance(value, list)
                ):
                    if key in {
                        "providers",
                        "models",
                        "transcribe_providers",
                        "transcribe_models",
                        "tts_providers",
                        "tts_models",
                        "installed_agents",
                    }:
                        target[key] = value
                    else:
                        target[key] = list(set(value + target[key]))
                else:
                    target[key] = value

        deep_merge(current_config, updates)
        # Re-validate through Pydantic model and dump to dict
        validated = cls.model_validate(current_config)
        dumped = validated.model_dump(mode="json", exclude_none=True)
        cls.dump_config(dumped)

    @classmethod
    def _get_nested_model_class(
        cls, field_info: FieldInfo | None
    ) -> type[BaseModel] | None:
        """Get the nested model class for a field if it's a known Pydantic model."""
        if field_info is None:
            return None

        # Check the annotation for nested models
        annotation = field_info.annotation
        # Handle bare types (e.g., ProjectContextConfig)
        if hasattr(annotation, "__origin__"):
            # It's a generic type like list[T] or dict[K, V]
            return None
        # Check if it's a BaseModel subclass
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return annotation
        return None

    @classmethod
    def _exclude_defaults(cls, config_dict: dict[str, Any]) -> dict[str, Any]:
        """Recursively remove fields that have default values."""
        result: dict[str, Any] = {}

        for key, value in config_dict.items():
            field_info = cls.model_fields.get(key)
            if field_info is None:
                if value is not None:
                    result[key] = value
                continue

            # Check if value equals default
            if cls._value_is_default(value, field_info):
                continue

            # Skip None values (can't be serialized to TOML)
            if value is None:
                continue

            if isinstance(value, dict):
                # Get the nested model class if this is a known nested field
                nested_model = cls._get_nested_model_class(field_info)
                nested_result = cls._exclude_nested_defaults(value, nested_model)
                if nested_result:
                    result[key] = nested_result
                continue

            if isinstance(value, list):
                processed_list = cls._process_list_excluding_defaults(value)
                if processed_list:
                    result[key] = processed_list
                continue

            result[key] = value

        return result

    @classmethod
    def _value_is_default(cls, value: Any, field_info: FieldInfo) -> bool:
        """Check if a value is equal to the field's default."""
        if field_info.is_required():
            return False

        if field_info.default_factory is not None:
            try:
                default_value = field_info.default_factory()  # type: ignore[call-arg]
                # Normalize BaseModel instances to dicts for comparison
                if isinstance(default_value, BaseModel):
                    default_value = default_value.model_dump(mode="json")
                elif isinstance(default_value, list):
                    default_value = [
                        item.model_dump(mode="json")
                        if isinstance(item, BaseModel)
                        else item
                        for item in default_value
                    ]
                elif isinstance(default_value, dict):
                    default_value = {
                        k: v.model_dump(mode="json") if isinstance(v, BaseModel) else v
                        for k, v in default_value.items()
                    }
                return value == default_value
            except Exception:
                return False

        return value == field_info.default

    @classmethod
    def _exclude_nested_defaults(
        cls, value: dict[str, Any], model_class: type[BaseModel] | None = None
    ) -> dict[str, Any]:
        """Recursively exclude default values from nested dicts."""
        result: dict[str, Any] = {}

        for key, val in value.items():
            if val is None:
                continue

            field_info = None
            if model_class is not None:
                field_info = model_class.model_fields.get(key)

            if field_info is not None and cls._value_is_default(val, field_info):
                continue

            if isinstance(val, dict):
                nested_result = cls._exclude_nested_defaults(val)
                if nested_result:
                    result[key] = nested_result
                continue

            if isinstance(val, list):
                processed_list = cls._process_list_excluding_defaults(val)
                if processed_list:
                    result[key] = processed_list
                continue

            result[key] = val

        return result

    @classmethod
    def _process_list_excluding_defaults(cls, value: list[Any]) -> list[Any]:
        """Process a list, excluding None values and default values from nested dicts."""
        processed_list: list[Any] = []

        for item in value:
            if item is None:
                continue
            if isinstance(item, dict):
                nested_result = cls._exclude_nested_defaults(item)
                if nested_result:
                    processed_list.append(nested_result)
            else:
                processed_list.append(item)
        return processed_list

    @classmethod
    def dump_config(cls, config: dict[str, Any]) -> None:
        """Write config to file, preserving existing comments.

        Args:
            config: Dictionary of non-default values (already filtered by caller).
        """
        mgr = get_harness_files_manager()
        if not mgr.persist_allowed:
            return
        target = mgr.config_file or mgr.user_config_file
        target.parent.mkdir(parents=True, exist_ok=True)

        # Read existing file to preserve comments
        if target.exists():
            with target.open("rb") as f:
                doc = tomlkit.load(f)
        else:
            doc = tomlkit.document()

        # Update document with provided values (already excludes defaults)
        # Skip providers and models - they're managed separately
        for key, value in config.items():
            if key in {"providers", "models"}:
                continue

            if isinstance(value, dict):
                # Update nested dict values
                if key not in doc:
                    doc.add(tomlkit.key(key), tomlkit.table())
                table = doc[key]
                if isinstance(table, dict):
                    for subkey, subvalue in value.items():
                        table[subkey] = subvalue
            else:
                doc[key] = value

        # Remove any fields that have default values
        cls._remove_defaults_from_doc(doc)

        # Write back with preserved comments using tomlkit
        with target.open("wb") as f:
            f.write(tomlkit.dumps(doc).encode("utf-8"))

    @classmethod
    def _get_models_for_array_field(
        cls, field_name: str, field_type: Any
    ) -> list[type[BaseModel]]:
        """Get model classes for an array field, handling discriminated unions.

        For discriminated unions (e.g., MCPServer = MCPHttp | MCPStreamableHttp | MCPStdio),
        returns ALL union members so we can process items with all possible fields.

        Args:
            field_name: Name of the field (for debugging)
            field_type: The type extracted from list[SomeType]

        Returns:
            List of BaseModel classes to use for processing
        """
        # Check if this is a Union type (discriminated union)
        # Union types have __args__ with multiple types (e.g., A | B | C)
        if hasattr(field_type, "__args__") and len(field_type.__args__) > 1:
            # This is a Union - collect all BaseModel members
            models: list[type[BaseModel]] = []
            for arg in field_type.__args__:
                if isinstance(arg, type) and issubclass(arg, BaseModel):
                    models.append(arg)
            return models

        # Default: return the type if it's a BaseModel
        if isinstance(field_type, type) and issubclass(field_type, BaseModel):
            return [field_type]
        return []

    @classmethod
    def _remove_defaults_from_doc(  # noqa: PLR0912, PLR0915
        cls, doc: tomlkit.TOMLDocument
    ) -> None:
        """Remove all fields with default values from the document."""
        # Dynamically detect field types from model_fields
        # Arrays of models: list[SomeModel] -> extract SomeModel
        # Simple arrays: list[str] or list[Path] -> no nested processing needed
        # Nested dicts: SomeModel (not in a list) -> process as nested section
        # Dicts: dict[str, SomeModel] -> process values as models

        nested_section_keys: set[str] = set()
        array_model_map: dict[str, list[type[BaseModel]]] = {}
        dict_model_keys: dict[str, type[BaseModel]] = {}

        for field_name, field_info in cls.model_fields.items():  # noqa: PLR1702
            annotation = field_info.annotation
            origin = getattr(annotation, "__origin__", None)

            if origin is list:
                # It's a list[field_type]
                args = getattr(annotation, "__args__", ())
                if args:
                    field_type = args[0]
                    # Check if it's a BaseModel subclass (possibly wrapped in Annotated)
                    if hasattr(field_type, "__origin__"):
                        # It's Annotated[SomeModel, ...] - extract the actual type
                        actual_args = getattr(field_type, "__args__", ())
                        if actual_args:
                            field_type = actual_args[0]

                    # Use helper to handle discriminated unions
                    model_classes = cls._get_models_for_array_field(
                        field_name, field_type
                    )
                    if model_classes:
                        array_model_map[field_name] = model_classes

            elif origin is dict:
                # It's a dict[str, SomeModel]
                args = getattr(annotation, "__args__", ())
                if len(args) >= DICT_ARGS_MIN_LENGTH:
                    args_typed = cast(tuple[type, type], args)
                    value_type = args_typed[1]
                    # Handle Annotated wrapper
                    if hasattr(value_type, "__origin__"):
                        actual_args = getattr(value_type, "__args__", ())
                        if actual_args:
                            value_type = actual_args[0]

                    if isinstance(value_type, type) and issubclass(
                        value_type, BaseModel
                    ):
                        dict_model_keys[field_name] = value_type

            elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
                # It's a direct BaseModel (nested section)
                nested_section_keys.add(field_name)

        # Remove top-level defaults (excluding nested sections, arrays, and dicts)
        keys_to_remove: list[str] = []
        for key in doc.keys():
            if (
                key in nested_section_keys
                or key in array_model_map
                or key in dict_model_keys
            ):
                # Skip nested structures - handle separately
                continue

            field_info = cls.model_fields.get(key)
            if field_info and key in doc:
                value = doc[key]
                if cls._value_is_default(value, field_info):
                    keys_to_remove.append(key)

        for key in keys_to_remove:
            del doc[key]

        # Check and remove ALL array fields that are default (empty lists)
        for key in list(doc.keys()):  # noqa: PLR1702
            if key in nested_section_keys or key in dict_model_keys:
                # Skip nested sections and dicts - handle separately
                continue

            field_info = cls.model_fields.get(key)
            value = doc[key]

            # Check if this is an array field with a default empty list
            if field_info and isinstance(value, list):
                if cls._value_is_default(value, field_info):
                    del doc[key]
                    continue

                # If it's a model array, process items within
                if key in array_model_map:
                    model_classes = array_model_map[key]
                    for item in value:
                        if isinstance(item, dict):
                            # Process with ALL model classes to handle all possible fields from discriminated unions
                            for model_class in model_classes:
                                cls._remove_defaults_from_dict(item, model_class)

        # Process nested dict sections (e.g., project_context, session_logging)
        for key in nested_section_keys:
            if key not in doc:
                continue
            field_info = cls.model_fields.get(key)
            value = doc[key]
            nested_model = cls._get_nested_model_class(field_info)
            if nested_model is not None and isinstance(value, dict):
                cls._remove_defaults_from_dict(
                    value, nested_model, remove_empty=True, parent=doc, parent_key=key
                )

        # Process dict fields with model values (e.g., tools: dict[str, BaseToolConfig])
        for key, model_class in dict_model_keys.items():
            if key not in doc:
                continue
            value = doc[key]
            if isinstance(value, dict):
                for item in value.values():
                    if isinstance(item, dict):
                        cls._remove_defaults_from_dict(item, model_class)

    @classmethod
    def _remove_defaults_from_dict(
        cls,
        data: dict[str, Any],
        model_class: type[BaseModel],
        remove_empty: bool = False,
        parent: Any = None,
        parent_key: str | None = None,
    ) -> None:
        """Remove default values from a dict using the given model class.

        Args:
            data: Dict to process
            model_class: Pydantic model class for field info
            remove_empty: If True, remove parent key if dict becomes empty
            parent: Parent container (for removal when empty)
            parent_key: Key in parent to remove
        """
        keys_to_remove: list[str] = []
        for key in list(data.keys()):
            field_info = model_class.model_fields.get(key)
            if field_info and key in data:
                value = data[key]
                if cls._value_is_default(value, field_info):
                    keys_to_remove.append(key)
                    continue

                # Remove empty nested dicts (e.g., [mcp_servers.env] when env is {})
                if isinstance(value, dict) and not value:
                    keys_to_remove.append(key)

        for key in keys_to_remove:
            del data[key]

        # Remove the section if it's now empty
        if remove_empty and not data and parent is not None and parent_key is not None:
            del parent[parent_key]

    @classmethod
    def _update_dict_value(
        cls,
        doc: tomlkit.TOMLDocument,
        key: str,
        value: dict[str, Any],
        field_info: FieldInfo | None,
    ) -> None:
        """Update a dict value in the document."""
        # For nested config sections (project_context, session_logging)
        if field_info and hasattr(field_info.annotation, "__origin__"):
            # Skip dict types
            return

        if (
            field_info
            and isinstance(field_info.annotation, type)
            and issubclass(field_info.annotation, BaseModel)
        ):
            # Handle nested Pydantic model sections
            cls._update_nested_table(doc, key, value, field_info.annotation)
            return

        # Generic dict handling
        if key not in doc:
            doc.add(tomlkit.key(key), tomlkit.table())
        table = doc[key]  # type: ignore[assignment]
        if isinstance(table, dict):
            for subkey, subvalue in value.items():
                table[subkey] = subvalue

    @classmethod
    def _update_nested_table(
        cls,
        doc: tomlkit.TOMLDocument,
        section_key: str,
        values: dict[str, Any],
        model_class: type[BaseModel],
    ) -> None:
        """Update a nested table section, removing default values while preserving comments."""
        # Ensure the section exists
        if section_key not in doc:
            doc.add(tomlkit.key(section_key), tomlkit.table())

        table = doc[section_key]  # type: ignore[assignment]
        if not isinstance(table, dict):
            return

        # Track which keys we've updated
        updated_keys: set[str] = set()

        for subkey, subvalue in values.items():
            field_info = model_class.model_fields.get(subkey)
            updated_keys.add(subkey)

            if field_info is None:
                # Unknown field, just set it
                table[subkey] = subvalue
                continue

            # Check if value equals default
            if cls._value_is_default(subvalue, field_info):
                # Remove from table if it exists (it's a default value)
                if subkey in table:
                    del table[subkey]
            else:
                # Set the value
                table[subkey] = subvalue

        # Remove any keys in the table that are now defaults but weren't in the update
        # (This handles the case where a value was changed back to default)
        for key in list(table.keys()):
            if key not in updated_keys:
                continue
            field_info = model_class.model_fields.get(key)
            if field_info and key in values:
                if cls._value_is_default(values[key], field_info):
                    if key in table:
                        del table[key]

    @classmethod
    def _migrate(cls) -> None:
        mgr = get_harness_files_manager()
        if not mgr.persist_allowed:
            return
        file = mgr.config_file
        if file is None:
            return
        try:
            with file.open("rb") as f:
                doc = tomlkit.load(f)
        except (FileNotFoundError, tomllib.TOMLDecodeError, OSError, TOMLKitError):
            return

        bash_tools = doc.get("tools", {})
        if isinstance(bash_tools, dict):
            bash_config = bash_tools.get("bash", {})
            if isinstance(bash_config, dict):
                allowlist = bash_config.get("allowlist")
                if allowlist is not None and "find" in allowlist:
                    allowlist.remove("find")
                    # Write back directly using tomlkit to preserve document structure
                    with file.open("wb") as f:
                        f.write(tomlkit.dumps(doc).encode("utf-8"))
                    return

    @classmethod
    def load(cls, **overrides: Any) -> VibeConfig:
        cls._migrate()
        return cls(**(overrides or {}))

    @classmethod
    def create_default(cls) -> dict[str, Any]:
        config = cls.model_construct()
        config_dict = config.model_dump(mode="json")

        from vibe.core.tools.manager import ToolManager

        tool_defaults = ToolManager.discover_tool_defaults()
        if tool_defaults:
            config_dict["tools"] = tool_defaults

        return config_dict
