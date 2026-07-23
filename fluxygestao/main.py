from src.services.fly.responder import responder


def gerar_resposta(pergunta: str, target: dict, agent_id: str, agent_name: str, history: list = None, session: dict = None):
    return responder(pergunta, target or {}, agent_id, agent_name, history, session)
