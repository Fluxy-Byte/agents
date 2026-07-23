import os

from google.adk.sessions import DatabaseSessionService

_session_service: DatabaseSessionService | None = None


def get_session_service() -> DatabaseSessionService:
    global _session_service
    if _session_service is None:
        _session_service = DatabaseSessionService(db_url=os.getenv("URL_ADK_SESSIONS"))
    return _session_service
