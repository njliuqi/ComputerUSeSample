from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status

from app.api.auth import get_user_from_token
from app.services.auth import AuthService, get_auth_service
from app.services.session_manager import SessionManager, get_session_manager
from app.services.websocket_manager import get_websocket_manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/sessions/{session_id}")
async def session_events_websocket(
    websocket: WebSocket,
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    token = websocket.query_params.get("token", "")
    try:
        current_user = get_user_from_token(token, auth_service)
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    session = manager.get_session(session_id)
    if session is None or session.user_id != current_user.id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    websocket_manager = get_websocket_manager()
    await websocket_manager.connect(session_id, websocket)
    try:
        await websocket.send_json(
            {
                "type": "connected",
                "session_id": session_id,
                "payload": {},
            }
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(session_id, websocket)
