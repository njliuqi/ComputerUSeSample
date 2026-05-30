from abc import ABC, abstractmethod
import re
import shlex
from typing import Any

from app.core.config import get_settings
from app.schemas.events import EventType, new_event
from app.schemas.messages import MessageRole, new_message
from app.services.desktop_log import get_desktop_log_service
from app.services.session_manager import SessionManager
from app.services.relay_config import get_relay_config_service, normalize_anthropic_base_url
from computer_use_demo.loop import APIProvider, sampling_loop
from computer_use_demo.tools import ToolResult
from computer_use_demo.tools.run import run


class AgentRunnerError(RuntimeError):
    pass


VISIBLE_DESKTOP_PROMPT = """
You must complete the user's task visibly inside the Ubuntu VNC desktop on DISPLAY=:1.
For GUI applications started from bash, always set DISPLAY=:1.
If the user asks to open a terminal, immediately use the bash tool with:
DISPLAY=:1 xterm -geometry 100x30+60+60 -title "Computer Use Terminal" &
After launching a visible GUI application, take a screenshot to confirm it is visible.
Do not spend multiple turns only taking screenshots when a direct visible action is available.
"""


class BaseAgentRunner(ABC):
    def __init__(self, manager: SessionManager) -> None:
        self._manager = manager

    @abstractmethod
    async def run(
        self,
        session_id: str,
        prompt: str,
        user_id: str | None = None,
        relay_config_id: str | None = None,
        relay_api_url: str | None = None,
        relay_api_key: str | None = None,
        model: str | None = None,
        run_id: str | None = None,
    ) -> None:
        raise NotImplementedError


class MockAgentRunner(BaseAgentRunner):
    async def run(
        self,
        session_id: str,
        prompt: str,
        user_id: str | None = None,
        relay_config_id: str | None = None,
        relay_api_url: str | None = None,
        relay_api_key: str | None = None,
        model: str | None = None,
        run_id: str | None = None,
    ) -> None:
        self._manager.add_event(
            new_event(
                session_id=session_id,
                event_type=EventType.agent_message,
                payload={"content": f"Mock agent received: {prompt}", "run_id": run_id},
            )
        )
        self._manager.add_event(
            new_event(
                session_id=session_id,
                event_type=EventType.tool_started,
                payload={"tool": "computer", "action": "observe", "run_id": run_id},
            )
        )
        self._manager.add_event(
            new_event(
                session_id=session_id,
                event_type=EventType.tool_result,
                payload={"tool": "computer", "result": "Mock observation completed.", "run_id": run_id},
            )
        )
        self._manager.add_event(
            new_event(
                session_id=session_id,
                event_type=EventType.screenshot,
                payload={"url": None, "description": "Mock screenshot placeholder.", "run_id": run_id},
            )
        )

        assistant_message = new_message(
            session_id=session_id,
            role=MessageRole.assistant,
            content="Mock agent completed the requested task.",
        )
        self._manager.add_message(assistant_message)
        self._manager.add_event(
            new_event(
                session_id=session_id,
                event_type=EventType.completed,
                payload={"message_id": assistant_message.id, "run_id": run_id},
            )
        )


class AnthropicAgentRunner(BaseAgentRunner):
    def __init__(self, manager: SessionManager) -> None:
        super().__init__(manager)
        self._tool_use_counts: dict[str, int] = {}

    async def run(
        self,
        session_id: str,
        prompt: str,
        user_id: str | None = None,
        relay_config_id: str | None = None,
        relay_api_url: str | None = None,
        relay_api_key: str | None = None,
        model: str | None = None,
        run_id: str | None = None,
    ) -> None:
        settings = get_settings()
        api_key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
        base_url = settings.anthropic_base_url
        selected_model = model or settings.anthropic_model
        request_api_url = relay_api_url.strip() if relay_api_url else ""
        request_api_key = relay_api_key.strip() if relay_api_key else ""

        if request_api_url and request_api_key:
            api_key = request_api_key
            base_url = normalize_anthropic_base_url(request_api_url)
            selected_model = model or selected_model
        elif user_id:
            service = get_relay_config_service()
            relay_config = (
                service.get_success_config(user_id, relay_config_id)
                if relay_config_id
                else service.get_latest_success_config(user_id)
            )
            if relay_config is None:
                raise AgentRunnerError("A tested Relay API configuration is required before running tasks.")
            api_key = relay_config.api_key
            base_url = normalize_anthropic_base_url(relay_config.api_url)
            selected_model = model or relay_config.model
            if selected_model not in relay_config.models:
                raise AgentRunnerError("Selected model is not available for the tested Relay API configuration.")

        if not api_key:
            raise AgentRunnerError("ANTHROPIC_API_KEY or a tested Relay API key is required.")

        self._manager.add_event(
            new_event(
                session_id=session_id,
                event_type=EventType.agent_message,
                payload={
                    "content": f"Starting Claude Computer Use with model: {selected_model}",
                    "model": selected_model,
                    "base_url": base_url,
                    "run_id": run_id,
                },
            )
        )

        visible_command = build_visible_desktop_command(prompt)
        if visible_command:
            await self._run_visible_desktop_command(session_id, visible_command, run_id)

        messages = [{"role": "user", "content": prompt}]
        api_error_message = None
        self._tool_use_counts[session_id] = 0

        def handle_api_response(request: Any, response: Any, error: Exception | None) -> None:
            nonlocal api_error_message
            if error:
                api_error_message = str(error)
            self._handle_api_response(session_id, request, response, error, run_id)

        system_prompt_suffix = "\n\n".join(
            part for part in (settings.anthropic_system_prompt_suffix, VISIBLE_DESKTOP_PROMPT) if part
        )
        try:
            await sampling_loop(
                model=selected_model,
                provider=APIProvider.ANTHROPIC,
                system_prompt_suffix=system_prompt_suffix,
                messages=messages,
                output_callback=lambda content: self._handle_output(session_id, content, run_id),
                tool_output_callback=lambda result, tool_id: self._handle_tool_output(
                    session_id, result, tool_id, run_id
                ),
                api_response_callback=handle_api_response,
                api_key=api_key,
                base_url=base_url,
                only_n_most_recent_images=settings.anthropic_only_n_most_recent_images,
                max_tokens=settings.anthropic_max_tokens,
                tool_version=settings.anthropic_tool_version,
                token_efficient_tools_beta=settings.anthropic_token_efficient_tools_beta,
                max_iterations=12,
            )
            if api_error_message:
                raise AgentRunnerError(format_computer_use_error(api_error_message))
            if self._tool_use_counts.get(session_id, 0) == 0 and not visible_command:
                raise AgentRunnerError(
                    "Relay model did not return any real Claude Computer Use tool calls. "
                    "No command was executed in the VNC desktop."
                )
            self._manager.add_event(
                new_event(
                    session_id=session_id,
                    event_type=EventType.completed,
                    payload={"mode": "anthropic", "run_id": run_id},
                )
            )
        finally:
            self._tool_use_counts.pop(session_id, None)

    async def _run_visible_desktop_command(self, session_id: str, command: str, run_id: str | None = None) -> None:
        self._manager.add_event(
            new_event(
                session_id=session_id,
                event_type=EventType.tool_started,
                payload={
                    "tool": "bash",
                    "input": {"command": command},
                    "source": "visible_desktop_command",
                    "run_id": run_id,
                },
            )
        )
        get_desktop_log_service().write_line(f"[visible] COMMAND: {command}")
        returncode, output, error = await run(command, timeout=15)
        self._manager.add_event(
            new_event(
                session_id=session_id,
                event_type=EventType.tool_result,
                payload={
                    "tool": "bash",
                    "output": output or f"Command exited with code {returncode}",
                    "error": error,
                    "source": "visible_desktop_command",
                    "run_id": run_id,
                },
            )
        )

    def _handle_output(self, session_id: str, content: dict[str, Any], run_id: str | None = None) -> None:
        content_type = content.get("type")
        if content_type == "text":
            text = content.get("text", "")
            if text:
                assistant_message = new_message(
                    session_id=session_id,
                    role=MessageRole.assistant,
                    content=text,
                )
                self._manager.add_message(assistant_message)
                self._manager.add_event(
                    new_event(
                        session_id=session_id,
                        event_type=EventType.agent_message,
                        payload={"message_id": assistant_message.id, "content": text, "run_id": run_id},
                    )
                )
            return

        if content_type == "tool_use":
            self._tool_use_counts[session_id] = self._tool_use_counts.get(session_id, 0) + 1
            self._manager.add_event(
                new_event(
                    session_id=session_id,
                    event_type=EventType.tool_started,
                    payload={
                        "tool_use_id": content.get("id"),
                        "tool": content.get("name"),
                        "input": content.get("input", {}),
                        "run_id": run_id,
                    },
                )
            )
            return

        self._manager.add_event(
            new_event(
                session_id=session_id,
                event_type=EventType.agent_message,
                payload={"content": content, "run_id": run_id},
            )
        )

    def _handle_tool_output(
        self,
        session_id: str,
        result: ToolResult,
        tool_id: str,
        run_id: str | None = None,
    ) -> None:
        self._manager.add_event(
            new_event(
                session_id=session_id,
                event_type=EventType.tool_result,
                payload={
                    "tool_use_id": tool_id,
                    "output": result.output,
                    "error": result.error,
                    "has_image": bool(result.base64_image),
                    "run_id": run_id,
                },
            )
        )
        if result.base64_image:
            self._manager.add_event(
                new_event(
                    session_id=session_id,
                    event_type=EventType.screenshot,
                    payload={
                        "tool_use_id": tool_id,
                        "media_type": "image/png",
                        "base64_image": result.base64_image,
                        "run_id": run_id,
                    },
                )
            )

    def _handle_api_response(
        self,
        session_id: str,
        request: Any,
        response: Any,
        error: Exception | None,
        run_id: str | None = None,
    ) -> None:
        if error:
            self._manager.add_event(
                new_event(
                    session_id=session_id,
                    event_type=EventType.error,
                    payload={"message": str(error), "run_id": run_id},
                )
            )


def format_computer_use_error(message: str) -> str:
    lower_message = message.lower()
    if any(status in lower_message for status in ("403", "502", "bad_response_status_code", "upstream service")):
        return (
            "Relay API/model rejected Claude Computer Use execution. "
            "The connection test only verifies the Relay URL, API key, and model list; "
            f"Run Task requires Claude Computer Use beta tool support. Original error: {message}"
        )
    return message


def build_visible_desktop_command(prompt: str) -> str | None:
    prompt_text = prompt.strip()
    lower_prompt = prompt_text.lower()
    if "terminal" in lower_prompt and any(action in lower_prompt for action in ("open", "launch", "start")):
        return 'DISPLAY=:1 xterm -geometry 100x30+60+60 -title "Computer Use Terminal" &'

    url = extract_url_from_prompt(prompt_text)
    wants_browser = bool(url) or any(word in lower_prompt for word in ("firefox", "browser", "baidu", "website", "access", "visit"))
    wants_open = any(word in lower_prompt for word in ("open", "access", "visit", "go to", "navigate"))
    if not (wants_browser and wants_open):
        return None

    if not url:
        return None
    python_code = (
        "import os, subprocess, time; "
        "env=os.environ.copy(); "
        "env.update({"
        "'DISPLAY':':1',"
        "'HOME':'/home/computeruse',"
        "'NO_AT_BRIDGE':'1',"
        "'MOZ_DISABLE_CONTENT_SANDBOX':'1',"
        "'MOZ_DISABLE_GMP_SANDBOX':'1',"
        "'MOZ_DISABLE_RDD_SANDBOX':'1'"
        "}); "
        "profile='/home/computeruse/.firefox-agent-profile'; "
        "os.makedirs(profile, exist_ok=True); "
        "log=open('/home/computeruse/firefox-visible-command.log','ab'); "
        "proc=subprocess.Popen(["
        "'firefox-esr','--no-remote','--new-instance','--profile',profile,'--new-window',"
        f"{url!r}"
        "], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True); "
        "time.sleep(2); "
        "raise SystemExit(0 if proc.poll() is None else proc.returncode or 1)"
    )
    return (
        f"python3 -c {shlex.quote(python_code)} "
        "|| (echo 'Firefox did not stay running. See /home/computeruse/firefox-visible-command.log'; "
        "cat /home/computeruse/firefox-visible-command.log; exit 1)"
    )


def extract_url_from_prompt(prompt: str) -> str | None:
    match = re.search(r"((?:https?://)?(?:www\.)?[A-Za-z0-9.-]+\.[A-Za-z]{2,})(?:/[^\s]*)?", prompt)
    if not match:
        return None
    url = match.group(0).rstrip(".,;)")
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url


class FakeAnthropicAgentRunner(AnthropicAgentRunner):
    async def run(
        self,
        session_id: str,
        prompt: str,
        user_id: str | None = None,
        relay_config_id: str | None = None,
        relay_api_url: str | None = None,
        relay_api_key: str | None = None,
        model: str | None = None,
        run_id: str | None = None,
    ) -> None:
        self._handle_output(
            session_id,
            {
                "type": "text",
                "text": f"Fake Anthropic runner received: {prompt}",
            },
            run_id,
        )
        self._handle_output(
            session_id,
            {
                "type": "tool_use",
                "id": "fake-tool-use-1",
                "name": "computer",
                "input": {"action": "screenshot"},
            },
            run_id,
        )
        self._handle_tool_output(
            session_id,
            ToolResult(
                output="Fake computer screenshot completed.",
                base64_image="ZmFrZS1wbmc=",
            ),
            "fake-tool-use-1",
            run_id,
        )
        assistant_message = new_message(
            session_id=session_id,
            role=MessageRole.assistant,
            content="Fake Anthropic runner completed the task.",
        )
        self._manager.add_message(assistant_message)
        self._manager.add_event(
            new_event(
                session_id=session_id,
                event_type=EventType.completed,
                payload={"mode": "fake_anthropic", "message_id": assistant_message.id, "run_id": run_id},
            )
        )


def build_agent_runner(manager: SessionManager, mode: str | None = None) -> BaseAgentRunner:
    agent_mode = (mode or get_settings().agent_mode).lower()
    if agent_mode == "mock":
        return MockAgentRunner(manager)
    if agent_mode == "fake_anthropic":
        return FakeAnthropicAgentRunner(manager)
    if agent_mode == "anthropic":
        return AnthropicAgentRunner(manager)
    raise AgentRunnerError(f"Unsupported AGENT_MODE: {agent_mode}")


def get_agent_runner(manager: SessionManager) -> BaseAgentRunner:
    return build_agent_runner(manager)
