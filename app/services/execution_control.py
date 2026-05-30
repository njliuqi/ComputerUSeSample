import asyncio

from app.core.config import get_settings
from computer_use_demo.tools.run import run


class ExecutionControlService:
    async def cleanup_session_processes(self) -> None:
        cleanup_command = (
            "DISPLAY=:1 pkill -x firefox-esr || true; "
            "DISPLAY=:1 pkill -f 'xterm.*Computer Use Terminal' || true; "
            "DISPLAY=:1 pkill -f 'xterm.*Claude' || true; "
            "DISPLAY=:1 pkill -f 'xterm.*Computer Use' || true"
        )
        await run(cleanup_command, timeout=5)

    async def run_with_timeout(self, operation) -> None:
        timeout = get_settings().agent_run_timeout_seconds
        await asyncio.wait_for(operation, timeout=timeout)


execution_control_service = ExecutionControlService()


def get_execution_control_service() -> ExecutionControlService:
    return execution_control_service
