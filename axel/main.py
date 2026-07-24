from src.services.adk.runner import gerar_resposta_adk


def gerar_resposta(pergunta: str, target: dict, agent_id: str, agent_name: str, history: list = None, session: dict = None):
    session = session or {}
    target = target or {}

    session_id = session.get("id")
    user_id = session.get("targetId") or target.get("id")

    if not session_id or not user_id:
        raise ValueError("Sessão sem 'id'/'targetId' — não é possível abrir a sessão no ADK.")

    return gerar_resposta_adk(pergunta, user_id=user_id, session_id=session_id)
