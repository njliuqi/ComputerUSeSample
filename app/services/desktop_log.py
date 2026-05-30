from datetime import datetime
from pathlib import Path
from typing import Any

from app.schemas.events import EventRead


LOG_PATH = Path("/tmp/agent-session.log")


class DesktopLogService:
    def reset(self) -> None:
        LOG_PATH.write_text(
            "Agent execution log is ready.\nRun Task to start visible execution.\n\n",
            encoding="utf-8",
        )

    def ensure(self) -> None:
        if not LOG_PATH.exists():
            self.reset()

    def write_event(self, event: EventRead) -> None:
        line = self._format_event(event)
        if not line:
            return
        self.write_line(line)

    def write_line(self, line: str) -> None:
        with LOG_PATH.open("a", encoding="utf-8") as log_file:
            log_file.write(line)
            log_file.write("\n")

    def _format_event(self, event: EventRead) -> str:
        timestamp = event.created_at.strftime("%H:%M:%S") if isinstance(event.created_at, datetime) else "--:--:--"
        payload = event.payload
        event_type = event.type.value

        if event_type == "user_message":
            return f"[{timestamp}] USER: {payload.get('content', '')}"
        if event_type == "agent_message":
            content = payload.get("content", "")
            if isinstance(content, dict):
                content = content.get("thinking") or content.get("text") or str(content)
            return f"[{timestamp}] AGENT: {self._compact(content)}"
        if event_type == "tool_started":
            return (
                f"[{timestamp}] TOOL START: {payload.get('tool', 'unknown')} "
                f"{self._compact(payload.get('input', {}))}"
            )
        if event_type == "tool_result":
            if payload.get("error"):
                return f"[{timestamp}] TOOL ERROR: {self._compact(payload.get('error'))}"
            if payload.get("has_image"):
                return f"[{timestamp}] TOOL RESULT: screenshot captured"
            return f"[{timestamp}] TOOL RESULT: {self._compact(payload.get('output', 'done'))}"
        if event_type == "screenshot":
            artifact = payload.get("artifact_url") or payload.get("artifact_id") or "captured"
            return f"[{timestamp}] SCREENSHOT: {artifact}"
        if event_type == "completed":
            return f"[{timestamp}] COMPLETED: {self._compact(payload)}"
        if event_type == "error":
            return f"[{timestamp}] ERROR: {self._compact(payload.get('message', payload))}"
        return f"[{timestamp}] {event_type.upper()}: {self._compact(payload)}"

    def _compact(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, dict):
            value = {key: item for key, item in value.items() if key != "base64_image"}
        text = str(value).replace("\n", " ").strip()
        if len(text) > 500:
            return f"{text[:497]}..."
        return text


desktop_log_service = DesktopLogService()


def get_desktop_log_service() -> DesktopLogService:
    return desktop_log_service
