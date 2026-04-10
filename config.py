from __future__ import annotations

import json
from dataclasses import asdict

from models import AppConfig


class ConfigStore:
    def __init__(self) -> None:
        self.path = AppConfig.config_path()
        self.config = self.load()

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return AppConfig()

        defaults = asdict(AppConfig())
        defaults.update(
            {
                key: value
                for key, value in raw.items()
                if key in defaults and value is not None
            }
        )
        return AppConfig(**defaults)

    def save(self, config: AppConfig) -> None:
        self.path.write_text(
            json.dumps(asdict(config), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.config = config
