import os
from datetime import date, datetime
from typing import Literal, Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.services.fly import orquestrador_client

load_dotenv()

modelo = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    api_key=os.getenv("OPENAI_API_KEY"),
)

# Estados do fluxo, guardados em Target.metadata.agendamentoEstado entre uma mensagem e
# outra (o worker não mantém nenhum estado em memória — cada mensagem é processada do
# zero, então o "estado da conversa" precisa viver em algum lugar persistente).
ESTADO_AGUARDANDO_RESPOSTA_INICIAL = "aguardando_resposta_remarcar"
ESTADO_AGUARDANDO_NOVO_HORARIO = "aguardando_novo_horario"
ESTADO_AGUARDANDO_CONFIRMACAO_FINAL = "aguardando_confirmacao_final"
ESTADO_AGUARDANDO_MOTIVO_CANCELAMENTO = "aguardando_motivo_cancelamento"
ESTADO_AGUARDANDO_NOVO_AGENDAMENTO_POS_CANCELAMENTO = "aguardando_novo_agendamento_pos_cancelamento"

FORA_DE_ESCOPO_MSG = (
    "Por aqui só conseguimos marcar ou remarcar o seu agendamento. Outros assuntos "
    "só podem ser tratados no dia da reunião."
)


class RespostaAgendamento(BaseModel):
    intencao: Literal["remarcar", "cancelar", "outro"] = Field(
        description="Classifique a resposta do cliente à pergunta sobre o agendamento existente: "
        "'remarcar' se ele quer remarcar/trocar a data ou respondeu afirmativamente, "
        "'cancelar' se ele quer cancelar o agendamento, "
        "'outro' se ele não respondeu isso claramente (fez outra pergunta, mudou de assunto, ficou em dúvida)."
    )


class RespostaSimNao(BaseModel):
    resposta: Literal["sim", "nao", "outro"] = Field(
        description="Classifique a resposta do cliente à pergunta feita: 'sim' se ele confirmou/concordou, "
        "'nao' se ele recusou/negou, 'outro' se a resposta não for objetiva."
    )


class NovaDataHora(BaseModel):
    data_hora: Optional[str] = Field(
        default=None,
        description="Dia e horário que o cliente sugeriu para o agendamento, em texto legível "
        "(ex: '25/08/2026 às 14h'). Deixe vazio se a mensagem não contém um dia e/ou horário claro.",
    )


def _classificar(pergunta_feita: str, resposta_usuario: str, schema):
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "Você está avaliando a resposta de um cliente, por WhatsApp, a uma pergunta sobre um "
            f"agendamento. Pergunta feita: \"{pergunta_feita}\"",
        ),
        ("human", "{resposta}"),
    ])
    classificador = prompt | modelo.with_structured_output(schema)
    return classificador.invoke({"resposta": resposta_usuario})


def _extrair_nova_data_hora(mensagem: str) -> Optional[str]:
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            f"Hoje é {date.today().isoformat()}. Extraia o dia e horário que o cliente sugeriu para o "
            "agendamento, a partir da mensagem dele por WhatsApp.",
        ),
        ("human", "{mensagem}"),
    ])
    classificador = prompt | modelo.with_structured_output(NovaDataHora)
    resultado = classificador.invoke({"mensagem": mensagem})
    return resultado.data_hora


def _agendamento_no_futuro(agendamento_proposta: Optional[str]) -> bool:
    if not agendamento_proposta:
        return False
    texto = str(agendamento_proposta).strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto[: len(fmt) + 4], fmt).date() >= date.today()
        except ValueError:
            continue
    # Formato não reconhecido — por segurança, trata como um agendamento ainda pendente
    # em vez de ignorá-lo silenciosamente.
    return True


def _atualizar_metadata(target: dict, patch: dict) -> None:
    target_id = target.get("id")
    if not target_id:
        return
    orquestrador_client.update_target_metadata(target_id, patch)
    # Mantém o dict local coerente, caso o mesmo `target` seja reaproveitado nesta execução.
    target["metadata"] = {**(target.get("metadata") or {}), **patch}


def _limpar_fluxo_e_fechar_sessao(target: dict, session: Optional[dict], manter_agendamento: bool) -> None:
    patch = {"agendamentoEstado": None}
    if not manter_agendamento:
        patch["agendamentoProposta"] = None
    _atualizar_metadata(target, patch)

    session_id = (session or {}).get("id")
    if session_id:
        orquestrador_client.close_session(session_id)


def tratar_fluxo_agendamento(pergunta: str, target: dict, session: Optional[dict]) -> Optional[list[str]]:
    """
    Fluxo determinístico de agendamento (marcar/remarcar/cancelar), verificado ANTES da
    identificação/classificação normal do Fly — atende também leads sem cadastro na Fluxy
    Gestão, já que aqui não depende de `resolve_authenticated_user`. Retorna None quando
    não há nada a fazer aqui, deixando o fluxo normal do Fly seguir.
    """
    metadata = target.get("metadata") or {}
    agendamento_proposta = metadata.get("agendamentoProposta")
    estado = metadata.get("agendamentoEstado")

    if not agendamento_proposta and not estado:
        return None

    # Nenhuma conversa em andamento sobre o agendamento ainda — só entra em ação se o
    # agendamento existente for para uma data que ainda não passou.
    if not estado:
        if not _agendamento_no_futuro(agendamento_proposta):
            return None
        _atualizar_metadata(target, {"agendamentoEstado": ESTADO_AGUARDANDO_RESPOSTA_INICIAL})
        return [f"Vi que você fez o agendamento para o dia {agendamento_proposta}, deseja remarcar?"]

    if estado == ESTADO_AGUARDANDO_RESPOSTA_INICIAL:
        resultado = _classificar(
            f"Vi que você fez o agendamento para o dia {agendamento_proposta}, deseja remarcar?",
            pergunta,
            RespostaAgendamento,
        )
        if resultado.intencao == "remarcar":
            _atualizar_metadata(target, {"agendamentoEstado": ESTADO_AGUARDANDO_NOVO_HORARIO})
            return ["Qual o melhor dia e horário para você?"]
        if resultado.intencao == "cancelar":
            _atualizar_metadata(target, {"agendamentoEstado": ESTADO_AGUARDANDO_MOTIVO_CANCELAMENTO})
            return ["Entendo. Qual é o motivo do cancelamento?"]
        return [FORA_DE_ESCOPO_MSG]

    if estado == ESTADO_AGUARDANDO_NOVO_HORARIO:
        nova_data_hora = _extrair_nova_data_hora(pergunta)
        if not nova_data_hora:
            return ["Não consegui entender o dia e horário. Pode me dizer, por exemplo, \"25/08 às 14h\"?"]
        _atualizar_metadata(target, {
            "agendamentoProposta": nova_data_hora,
            "agendamentoEstado": ESTADO_AGUARDANDO_CONFIRMACAO_FINAL,
        })
        return [f"Combinado, remarcado para {nova_data_hora}. Precisa de mais alguma informação?"]

    if estado == ESTADO_AGUARDANDO_CONFIRMACAO_FINAL:
        resultado = _classificar("Precisa de mais alguma informação?", pergunta, RespostaSimNao)
        if resultado.resposta == "nao":
            _limpar_fluxo_e_fechar_sessao(target, session, manter_agendamento=True)
            return ["Perfeito, seu agendamento está confirmado. Até lá! 👋"]
        if resultado.resposta == "sim":
            _atualizar_metadata(target, {"agendamentoEstado": None})
            return ["Claro, me conta o que você precisa."]
        return ["Você precisa de mais alguma informação sobre o agendamento?"]

    if estado == ESTADO_AGUARDANDO_MOTIVO_CANCELAMENTO:
        _atualizar_metadata(target, {
            "agendamentoMotivoCancelamento": pergunta,
            "agendamentoEstado": ESTADO_AGUARDANDO_NOVO_AGENDAMENTO_POS_CANCELAMENTO,
        })
        return ["Seria possível marcarmos um outro dia só para você conhecer melhor o nosso produto?"]

    if estado == ESTADO_AGUARDANDO_NOVO_AGENDAMENTO_POS_CANCELAMENTO:
        resultado = _classificar(
            "Seria possível marcarmos um outro dia só para você conhecer melhor o nosso produto?",
            pergunta,
            RespostaSimNao,
        )
        if resultado.resposta == "sim":
            _atualizar_metadata(target, {"agendamentoEstado": ESTADO_AGUARDANDO_NOVO_HORARIO})
            return ["Ótimo! Qual o melhor dia e horário para você?"]
        if resultado.resposta == "nao":
            _limpar_fluxo_e_fechar_sessao(target, session, manter_agendamento=False)
            return ["Sem problemas, o agendamento foi cancelado. Se mudar de ideia, é só chamar por aqui! 👋"]
        return ["Você gostaria de marcar um outro dia só para conhecer melhor o nosso produto?"]

    return None
