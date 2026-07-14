from typing import Optional

from src.services.fly import backend_client
from src.services.fly import orquestrador_client


def resolve_authenticated_user(target: dict) -> Optional[dict]:
    """
    Resolve o usuário da Fluxy Gestão dono da conversa.

    Ordem: usa o vínculo já salvo em target.metadata.fluxyUserId; se não houver,
    procura um usuário cadastrado com esse telefone e, se achar, vincula o contato
    (metadata.fluxyUserId) para as próximas mensagens não precisarem buscar de novo.
    Retorna None se o telefone não estiver vinculado a nenhum cadastro.
    """
    metadata = target.get("metadata") or {}
    fluxy_user_id = metadata.get("fluxyUserId")

    if fluxy_user_id:
        user = backend_client.get_user(fluxy_user_id)
        if user:
            return user

    phone = target.get("phone") or ""
    if not phone:
        return None

    user = backend_client.get_user_by_phone(phone)
    if not user:
        return None

    target_id = target.get("id")
    if target_id:
        orquestrador_client.link_target(target_id, user["id"])

    return user
