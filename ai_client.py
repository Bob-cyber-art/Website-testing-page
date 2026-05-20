from __future__ import annotations

import base64
from typing import Any

import requests

from models import AppConfig, ClipboardPayload


class AIClientError(RuntimeError):
    pass


class AIClient:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def ask_text(self, payload: ClipboardPayload) -> str:
        if not payload.text:
            raise AIClientError("当前剪贴板没有可发送的文本。")
        return self._send_request(
            [
                {"role": "system", "content": self._build_system_prompt()},
                {"role": "user", "content": payload.text},
            ]
        )

    def ask_image(self, payload: ClipboardPayload) -> str:
        if not payload.image_bytes:
            raise AIClientError("当前剪贴板没有可发送的图片。")

        data_url = self._build_data_url(payload.image_bytes)
        return self._send_request(
            [
                {"role": "system", "content": self._build_system_prompt()},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请识别并回答这张图片中的内容。"},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ]
        )

    def test_connection(self) -> str:
        return self._send_request(
            [
                {"role": "system", "content": "你是一个连接测试助手。"},
                {"role": "user", "content": "请回复：API connection ok"},
            ],
            extra_body={"max_tokens": 16},
        )

    def _send_request(
        self,
        messages: list[dict[str, Any]],
        extra_body: dict[str, Any] | None = None,
    ) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }
        body: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
        }
        if extra_body:
            body.update(extra_body)

        try:
            response = requests.post(
                self.config.base_url,
                headers=headers,
                json=body,
                timeout=self.config.request_timeout,
            )
        except requests.RequestException as exc:
            raise AIClientError(f"请求失败: {exc}") from exc

        if response.status_code >= 400:
            detail = response.text.strip() or "未知错误"
            raise AIClientError(f"接口返回 {response.status_code}: {detail}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise AIClientError("接口返回的不是合法 JSON。") from exc

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIClientError("响应中缺少 choices[0].message.content。") from exc

        if isinstance(content, list):
            text_parts = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            content = "\n".join(part for part in text_parts if part)

        if not isinstance(content, str) or not content.strip():
            raise AIClientError("接口返回了空答案。")

        return content.strip()

    def _build_system_prompt(self) -> str:
        prompt = self.config.system_prompt.strip() or "请直接回答用户问题。"
        if not self.config.keywords:
            return prompt
        keyword_text = "、".join(self.config.keywords)
        return f"{prompt}\n\n回答时优先关注这些关键词：{keyword_text}"

    @staticmethod
    def _build_data_url(image_bytes: bytes) -> str:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return f"data:image/png;base64,{encoded}"
