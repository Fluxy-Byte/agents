import asyncio
import os

from google.adk.errors.already_exists_error import AlreadyExistsError
from google.adk.runners import Runner
from google.genai import types

from src.infra.adk.session_service import get_session_service
from src.services.adk.agent import root_agent

APP_NAME = os.getenv("GOOGLE_ADK_APP_NAME", "axel")


async def _abrir_sessao(session_service, user_id: str, session_id: str) -> None:
    """Abre a sessão do ADK usando o id da sessão aberta na nossa plataforma
    (Orquestrador) como session_id — assim o histórico do ADK fica alinhado 1:1
    com a sessão de conversa do usuário no WhatsApp."""
    sessao = await session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
    if sessao is not None:
        return

    try:
        await session_service.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
    except AlreadyExistsError:
        pass


async def _executar(pergunta: str, user_id: str, session_id: str) -> str:
    # session_service (e o engine/pool do asyncpg por trás dele) é criado e descartado
    # dentro do mesmo event loop desta chamada — o worker roda cada mensagem num
    # asyncio.run() próprio (novo loop a cada vez), e um pool asyncpg criado num loop
    # não pode ser reaproveitado noutro (dá "attached to a different loop"/"Event loop
    # is closed" na segunda mensagem em diante). Por isso nada aqui é cacheado a nível
    # de módulo.
    async with get_session_service() as session_service:
        await _abrir_sessao(session_service, user_id, session_id)

        runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)
        mensagem = types.Content(role="user", parts=[types.Part(text=pergunta)])

        resposta = ""
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=mensagem):
            if event.is_final_response() and event.content and event.content.parts:
                resposta = event.content.parts[0].text or resposta

        return resposta


def gerar_resposta_adk(pergunta: str, user_id: str, session_id: str) -> str:
    return asyncio.run(_executar(pergunta, user_id, session_id))
