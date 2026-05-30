import asyncio

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.auth import get_current_user
from app.schemas.auth import UserRead
from app.schemas.events import EventRead, EventType, new_event
from app.schemas.messages import MessageCreate, MessageRead, MessageRole, new_message
from app.schemas.run_history import RunDetailRead, RunHistoryRead
from app.schemas.sessions import SessionCreate, SessionRead, SessionStatus
from app.schemas.vnc import VncConnectionRead
from app.services.agent_runner import BaseAgentRunner, get_agent_runner
from app.services.execution_control import ExecutionControlService, get_execution_control_service
from app.services.session_manager import SessionManager, get_session_manager
from app.services.task_cancellation import TaskCancellationService, get_task_cancellation_service
from app.services.vnc import VncService, get_vnc_service

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def get_request_agent_runner(
    manager: SessionManager = Depends(get_session_manager),
) -> BaseAgentRunner:
    return get_agent_runner(manager)


@router.post("", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionCreate | None = None,
    current_user: UserRead = Depends(get_current_user),
    manager: SessionManager = Depends(get_session_manager),
    vnc: VncService = Depends(get_vnc_service),
) -> SessionRead:
    session = manager.create_session(
        name=payload.name if payload else None,
        user_id=current_user.id,
    )
    await vnc.reset_desktop()
    return session


@router.get("", response_model=list[SessionRead])
async def list_sessions(
    current_user: UserRead = Depends(get_current_user),
    manager: SessionManager = Depends(get_session_manager),
) -> list[SessionRead]:
    return manager.list_sessions(user_id=current_user.id)


@router.get("/history", response_model=list[RunHistoryRead])
async def list_run_history(
    current_user: UserRead = Depends(get_current_user),
    manager: SessionManager = Depends(get_session_manager),
) -> list[RunHistoryRead]:
    return manager.list_run_history(user_id=current_user.id)


@router.get("/history/{run_id}", response_model=RunDetailRead)
async def get_run_history_detail(
    run_id: str,
    current_user: UserRead = Depends(get_current_user),
    manager: SessionManager = Depends(get_session_manager),
):
    run = manager.get_run_history(run_id, user_id=current_user.id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    from app.services.artifacts import get_artifact_service

    artifacts = get_artifact_service().list_session_artifacts(run.session_id, run_id=run.id)
    detail = manager.get_run_detail(run.id, artifacts=artifacts, user_id=current_user.id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return detail


@router.get("/{session_id}", response_model=SessionRead)
async def get_session(
    session_id: str,
    current_user: UserRead = Depends(get_current_user),
    manager: SessionManager = Depends(get_session_manager),
) -> SessionRead:
    return get_owned_session(session_id, current_user, manager)


@router.delete("/{session_id}", response_model=SessionRead)
async def terminate_session(
    session_id: str,
    current_user: UserRead = Depends(get_current_user),
    manager: SessionManager = Depends(get_session_manager),
) -> SessionRead:
    get_owned_session(session_id, current_user, manager)
    session = manager.terminate_session(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


@router.post("/{session_id}/cancel", response_model=SessionRead)
async def cancel_session_task(
    session_id: str,
    current_user: UserRead = Depends(get_current_user),
    manager: SessionManager = Depends(get_session_manager),
    cancellation: TaskCancellationService = Depends(get_task_cancellation_service),
    execution: ExecutionControlService = Depends(get_execution_control_service),
) -> SessionRead:
    session = get_owned_session(session_id, current_user, manager)
    if session.status != SessionStatus.running:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session is not running")
    cancellation.cancel(session_id)
    await execution.cleanup_session_processes()
    cancelled = manager.fail_session(session_id, "Task cancelled by user.")
    return cancelled or session


@router.post("/{session_id}/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
async def create_message(
    session_id: str,
    payload: MessageCreate,
    current_user: UserRead = Depends(get_current_user),
    manager: SessionManager = Depends(get_session_manager),
    runner: BaseAgentRunner = Depends(get_request_agent_runner),
    cancellation: TaskCancellationService = Depends(get_task_cancellation_service),
    execution: ExecutionControlService = Depends(get_execution_control_service),
) -> MessageRead:
    session = get_owned_session(session_id, current_user, manager)
    if session.status == SessionStatus.terminated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot send messages to a terminated session",
        )
    if session.status == SessionStatus.running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session is already running",
        )

    user_message = new_message(session_id, MessageRole.user, payload.content)
    manager.add_message(user_message)
    task_run = manager.create_task_run(
        session_id=session_id,
        user_id=current_user.id,
        message_id=user_message.id,
        prompt=payload.content,
        model=payload.model or "",
        base_url=payload.relay_api_url or "",
    )
    manager.add_event(
        new_event(
            session_id=session_id,
            event_type=EventType.user_message,
            payload={"message_id": user_message.id, "content": payload.content, "run_id": task_run.id},
        )
    )

    manager.start_session(session_id)

    task = asyncio.create_task(
        run_agent_message_task(
            session_id=session_id,
            payload=payload,
            manager=manager,
            runner=runner,
            cancellation=cancellation,
            execution=execution,
            user_id=current_user.id,
            run_id=task_run.id,
        )
    )
    cancellation.register(session_id, task)
    return user_message


async def run_agent_message_task(
    session_id: str,
    payload: MessageCreate,
    manager: SessionManager,
    runner: BaseAgentRunner,
    cancellation: TaskCancellationService,
    execution: ExecutionControlService,
    user_id: str,
    run_id: str,
) -> None:
    current_task = asyncio.current_task()
    try:
        await execution.run_with_timeout(
            runner.run(
                session_id=session_id,
                prompt=payload.content,
                user_id=user_id,
                relay_config_id=payload.relay_config_id,
                relay_api_url=payload.relay_api_url,
                relay_api_key=payload.relay_api_key,
                model=payload.model,
                run_id=run_id,
            )
        )
    except asyncio.CancelledError:
        session = manager.get_session(session_id)
        if session and session.status == SessionStatus.running:
            manager.fail_session(session_id, "Task cancelled by user.", run_id=run_id)
        manager.finish_task_run(run_id, "failed", "Task cancelled by user.")
        raise
    except Exception as exc:
        await execution.cleanup_session_processes()
        error_message = classify_run_task_error(str(exc))
        manager.fail_session(session_id, error_message, run_id=run_id)
        manager.finish_task_run(run_id, "failed", error_message)
    else:
        session = manager.get_session(session_id)
        if session and session.status == SessionStatus.running:
            manager.complete_session(session_id)
        manager.finish_task_run(run_id, "success")
    finally:
        if current_task is not None:
            cancellation.unregister(session_id, current_task)


def classify_run_task_error(message: str) -> str:
    lower_message = message.lower()
    if "selected model is not available" in lower_message:
        return "Model selection failed: the selected model is not available for the tested Relay API configuration."
    if "did not return any real claude computer use tool calls" in lower_message:
        return "Model compatibility failed: the selected model did not produce Claude Computer Use tool calls."
    if "computer use beta" in lower_message or "rejected claude computer use" in lower_message:
        return (
            "Model compatibility failed: the Relay API or selected model rejected Claude Computer Use beta tools. "
            f"Original error: {message}"
        )
    if "api key" in lower_message or "401" in lower_message or "unauthorized" in lower_message:
        return f"Relay authentication failed: check the Relay API key. Original error: {message}"
    if "403" in lower_message or "forbidden" in lower_message:
        return (
            "Model compatibility failed: the Relay API returned 403 during Run Task. "
            "The connection test can pass even when Computer Use beta tools are blocked. "
            f"Original error: {message}"
        )
    if "502" in lower_message or "upstream service" in lower_message or "temporarily unavailable" in lower_message:
        return f"Relay upstream failed: the provider returned a temporary upstream error. Original error: {message}"
    if "timed out" in lower_message or "timeout" in lower_message:
        return f"Execution timed out: the task or desktop command took too long. Original error: {message}"
    if "firefox did not stay running" in lower_message:
        return f"Desktop execution failed: Firefox did not stay running in VNC. Original error: {message}"
    return message


@router.get("/{session_id}/messages", response_model=list[MessageRead])
async def list_messages(
    session_id: str,
    current_user: UserRead = Depends(get_current_user),
    manager: SessionManager = Depends(get_session_manager),
) -> list[MessageRead]:
    get_owned_session(session_id, current_user, manager)
    messages = manager.list_messages(session_id)
    if messages is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return messages


@router.get("/{session_id}/events", response_model=list[EventRead])
async def list_events(
    session_id: str,
    run_id: str | None = None,
    current_user: UserRead = Depends(get_current_user),
    manager: SessionManager = Depends(get_session_manager),
) -> list[EventRead]:
    get_owned_session(session_id, current_user, manager)
    events = manager.list_events(session_id, run_id=run_id)
    if events is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return events


@router.get("/{session_id}/vnc", response_model=VncConnectionRead)
async def get_vnc_connection(
    session_id: str,
    current_user: UserRead = Depends(get_current_user),
    manager: SessionManager = Depends(get_session_manager),
    vnc: VncService = Depends(get_vnc_service),
) -> VncConnectionRead:
    get_owned_session(session_id, current_user, manager)
    await vnc.ensure_log_window()
    return vnc.get_connection(session_id)


def get_owned_session(
    session_id: str,
    current_user: UserRead,
    manager: SessionManager,
) -> SessionRead:
    session = manager.get_session(session_id)
    if session is None or session.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session
