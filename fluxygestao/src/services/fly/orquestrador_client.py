import os

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("ORQUESTRADOR_BASE_URL", "http://localhost:5304")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")


def link_target(target_id: str, fluxy_user_id: str) -> None:
    resp = httpx.patch(
        f"{BASE_URL}/api/target/{target_id}/link",
        json={"fluxyUserId": fluxy_user_id},
        headers={"x-internal-api-key": INTERNAL_API_KEY},
        timeout=15,
    )
    resp.raise_for_status()


def update_target_metadata(target_id: str, metadata_patch: dict) -> None:
    """
    Faz merge de um patch em Target.metadata (o Orquestrador cuida de não sobrescrever
    as chaves que já existiam, ex: fluxyUserId). Usado pelo fluxo de agendamento pra
    guardar `agendamentoProposta`/`agendamentoEstado` entre uma mensagem e outra.
    """
    resp = httpx.patch(
        f"{BASE_URL}/api/target/{target_id}/metadata",
        json={"metadata": metadata_patch},
        headers={"x-internal-api-key": INTERNAL_API_KEY},
        timeout=15,
    )
    resp.raise_for_status()


def close_session(session_id: str) -> None:
    """
    Encerra a sessão de conversa atual — a próxima mensagem do contato abre uma sessão
    nova. Usado quando o fluxo de agendamento termina e não há mais nada pendente.
    """
    resp = httpx.patch(
        f"{BASE_URL}/api/session/{session_id}/close",
        headers={"x-internal-api-key": INTERNAL_API_KEY},
        timeout=15,
    )
    resp.raise_for_status()
