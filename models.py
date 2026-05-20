from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class ClipboardPayload:
    kind: str
    text: str | None = None
    image_bytes: bytes | None = None
    source_hash: str = ""
    captured_at: datetime = field(default_factory=datetime.now)


@dataclass(slots=True)
class AppConfig:
    provider: str = "custom"
    base_url: str = "https://api.openai.com/v1/chat/completions"
    api_key: str = ""
    model: str = "gpt-4.1-mini"
    show_window_hotkey: str = "ctrl+shift+s"
    system_prompt: str = "请直接回答剪贴板中的问题，简洁清晰。"
    request_timeout: int = 60
    temperature: float = 0.7
    keywords: list[str] = field(default_factory=list)

    @classmethod
    def config_path(cls) -> Path:
        return Path(__file__).resolve().parent / "config.json"
