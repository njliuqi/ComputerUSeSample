import asyncio
from threading import RLock


class TaskCancellationService:
    def __init__(self) -> None:
        self._lock = RLock()
        self._tasks: dict[str, asyncio.Task] = {}

    def register(self, session_id: str, task: asyncio.Task) -> None:
        with self._lock:
            self._tasks[session_id] = task

    def unregister(self, session_id: str, task: asyncio.Task) -> None:
        with self._lock:
            if self._tasks.get(session_id) is task:
                del self._tasks[session_id]

    def cancel(self, session_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(session_id)
            if task is None or task.done():
                return False
            task.cancel()
            return True


task_cancellation_service = TaskCancellationService()


def get_task_cancellation_service() -> TaskCancellationService:
    return task_cancellation_service
