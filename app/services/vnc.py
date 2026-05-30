from urllib.parse import urlencode
import shlex

from app.core.config import get_settings
from app.schemas.vnc import VncConnectionRead, VncStatus
from app.services.desktop_log import get_desktop_log_service
from computer_use_demo.tools.run import run


class VncService:
    def get_connection(self, session_id: str) -> VncConnectionRead:
        settings = get_settings()
        base_url = settings.vnc_base_url.rstrip("/")
        path = settings.vnc_path.lstrip("/")
        params = {"session_id": session_id}

        if not base_url:
            return VncConnectionRead(
                session_id=session_id,
                status=VncStatus.unavailable,
                url=None,
            )

        url = f"{base_url}/{path}?{urlencode(params)}"
        view_only_url = f"{base_url}/{path}?{urlencode({**params, 'view_only': 'true'})}"
        return VncConnectionRead(
            session_id=session_id,
            status=VncStatus.ready,
            url=url,
            view_only_url=view_only_url,
        )

    async def reset_desktop(self) -> None:
        get_desktop_log_service().reset()
        cleanup_command = (
            "DISPLAY=:1 pkill -x firefox-esr || true; "
            "DISPLAY=:1 pkill -x xterm || true; "
            "DISPLAY=:1 xdotool mousemove 20 20 || true; "
            "DISPLAY=:1 xsetroot -solid '#1f2937' || true"
        )
        await run(cleanup_command, timeout=5)
        await self.ensure_log_window()

    async def ensure_log_window(self) -> None:
        get_desktop_log_service().ensure()
        python_code = (
            "import os, subprocess; "
            "env = os.environ.copy(); "
            "env['DISPLAY'] = ':1'; "
            "log = open('/tmp/vnc-session-marker.log', 'ab'); "
            "subprocess.Popen(['xterm', '-fa', 'Monospace', '-fs', '10', "
            "'-geometry', '112x10+18+18', '-title', 'Agent Execution Log', "
            "'-e', 'tail -n +1 -f /tmp/agent-session.log'], "
            "stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, "
            "env=env, start_new_session=True)"
        )
        check_command = (
            "DISPLAY=:1 xdotool search --name 'Agent Execution Log' >/dev/null 2>&1 "
            f"|| python3 -c {shlex.quote(python_code)}"
        )
        await run(check_command, timeout=5)


vnc_service = VncService()


def get_vnc_service() -> VncService:
    return vnc_service
