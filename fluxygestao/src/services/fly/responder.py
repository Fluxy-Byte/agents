from datetime import date, datetime
from typing import Optional

import httpx

from src.services.fly import backend_client
from src.services.fly.agendamento import tratar_fluxo_agendamento
from src.services.fly.identify import resolve_authenticated_user
from src.services.fly.intent import classificar_pergunta, IntencaoFly

NAO_LOCALIZADO_MSG = (
    "Não consegui localizar um cadastro da Fluxy Gestão vinculado a este número de "
    "telefone. Verifique se este é o número cadastrado na sua conta ou entre em "
    "contato com o nosso suporte para regularizar o vínculo."
)

INSTABILIDADE_MSG = (
    "Estamos com uma instabilidade para consultar essa informação agora. "
    "Por favor, tente novamente em alguns instantes."
)

DIAMANTE_MSG = (
    "Essa informação é exclusiva do plano Diamante. No seu plano atual não é "
    "possível consultar dívidas, saídas de caixa ou o relatório financeiro por aqui."
)

NAO_ENTENDI_MSG = "Desculpa, não entendi sua pergunta. 🤔"

MENU_MSG = (
    "Posso te ajudar com estes temas:\n\n"
    "1️⃣ Faturamento e custos\n"
    "2️⃣ Ordens de serviço (por período, cliente ou número)\n"
    "3️⃣ Clientes cadastrados\n"
    "4️⃣ Serviços cadastrados\n"
    "5️⃣ Link do catálogo de um cliente\n"
    "6️⃣ Dívidas, saídas de caixa e relatório financeiro (plano Diamante)\n"
    "7️⃣ Boleto da sua assinatura\n\n"
    "É só perguntar sobre algum desses assuntos!"
)

PEDIR_PERIODO_MSG = (
    "Para quê período você gostaria de consultar essa informação? Pode ser "
    "\"hoje\", \"essa semana\", \"esse mês\" ou um intervalo específico de datas."
)

PEDIR_CLIENTE_MSG = "Qual é o nome do cliente que você quer consultar?"

PEDIR_NUMERO_OS_MSG = "Qual é o número da ordem de serviço que você quer consultar?"

STATUS_PAGAMENTO_LABEL = {
    "PENDING": "pendente",
    "PAID": "pago",
    "PARTIAL": "parcial",
    "OVERDUE": "atrasado",
}

STATUS_OS_LABEL = {
    "PENDING": "em andamento",
    "COMPLETED": "concluída",
    "CANCELED": "cancelada",
}


def _status_pagamento(value: Optional[str]) -> str:
    return STATUS_PAGAMENTO_LABEL.get(value, value or "—")


def _status_os(value: Optional[str]) -> str:
    return STATUS_OS_LABEL.get(value, value or "—")


def _brl(value) -> str:
    try:
        v = float(value or 0)
    except (TypeError, ValueError):
        v = 0.0
    text = f"{v:,.2f}"
    text = text.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {text}"


def _data_br(value: Optional[str]) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except ValueError:
        return str(value)


def _periodo_label(start: str, end: str) -> str:
    if start == end:
        return f"do dia {_data_br(start)}"
    return f"de {_data_br(start)} a {_data_br(end)}"


def _handle_faturamento(user_id: str, intencao: IntencaoFly) -> str:
    if not intencao.start or not intencao.end:
        return PEDIR_PERIODO_MSG

    hoje = date.today().isoformat()
    if intencao.start == hoje and intencao.end == hoje:
        dados = backend_client.get_dashboard(user_id)
        return (
            f"Faturamento de hoje: {_brl(dados['revenue'])}\n"
            f"Custo: {_brl(dados['cost'])}\n"
            f"Margem: {_brl(dados['margin'])}\n"
            f"Ordens de serviço do dia: {dados['todayCount']}"
        )

    dados = backend_client.get_report(user_id, intencao.start, intencao.end)
    totais = dados["totals"]
    label = _periodo_label(intencao.start, intencao.end)
    return (
        f"Faturamento {label}: {_brl(totais['revenue'])}\n"
        f"Custo: {_brl(totais['cost'])}\n"
        f"Margem: {_brl(totais['margin'])}"
    )


def _handle_custos(user_id: str, intencao: IntencaoFly) -> str:
    if not intencao.start or not intencao.end:
        return PEDIR_PERIODO_MSG

    dados = backend_client.get_report(user_id, intencao.start, intencao.end)
    totais = dados["totals"]
    label = _periodo_label(intencao.start, intencao.end)
    return f"Custo das ordens de serviço {label}: {_brl(totais['cost'])}"


def _handle_os_periodo(user_id: str, intencao: IntencaoFly) -> str:
    if not intencao.start or not intencao.end:
        return PEDIR_PERIODO_MSG

    dados = backend_client.get_report(user_id, intencao.start, intencao.end)
    totais = dados["totals"]
    label = _periodo_label(intencao.start, intencao.end)
    return (
        f"Ordens de serviço {label}:\n"
        f"Total: {totais['total']}\n"
        f"Pendentes: {totais['pending']}\n"
        f"Concluídas: {totais['completed']}\n"
        f"Canceladas: {totais['canceled']}"
    )


def _resolve_client(user_id: str, client_name: str):
    matches = backend_client.search_clients(user_id, client_name)
    if len(matches) == 0:
        return None, f'Não encontrei nenhum cliente com o nome "{client_name}".'
    if len(matches) > 1:
        nomes = ", ".join(c["name"] for c in matches[:5])
        return None, f"Encontrei mais de um cliente com esse nome: {nomes}. Pode confirmar o nome completo?"
    return matches[0], None


def _handle_os_cliente(user_id: str, intencao: IntencaoFly) -> str:
    if not intencao.client_name:
        return PEDIR_CLIENTE_MSG

    client, erro = _resolve_client(user_id, intencao.client_name)
    if erro:
        return erro

    orders = backend_client.get_client_orders(user_id, client["id"])
    if not orders:
        return f"O cliente {client['name']} ainda não tem nenhuma ordem de serviço registrada."

    linhas = [f"Ordens de serviço de {client['name']}:"]
    for o in orders[:10]:
        linhas.append(
            f"- OS #{o.get('numberOrder')}: {_status_os(o.get('statusOrder'))} — "
            f"{_brl(o.get('totalSale'))} — entrega {_data_br(o.get('deliveryDate'))} — "
            f"pagamento {_status_pagamento(o.get('paymentStatus'))}"
        )
    if len(orders) > 10:
        linhas.append(f"... e mais {len(orders) - 10} ordem(ns).")
    return "\n".join(linhas)


def _handle_os_detalhe(user_id: str, intencao: IntencaoFly) -> str:
    if not intencao.order_number:
        return PEDIR_NUMERO_OS_MSG

    order = backend_client.get_order_by_number(user_id, intencao.order_number)
    if not order:
        return f"Não encontrei nenhuma ordem de serviço com o número {intencao.order_number}."

    client = order.get("client") or {}
    linhas = [
        f"OS #{order.get('numberOrder')} — {client.get('name', '—')}",
        f"Status: {_status_os(order.get('statusOrder'))}",
        f"Valor total: {_brl(order.get('totalSale'))}",
        f"Data de entrega: {_data_br(order.get('deliveryDate'))}",
        f"Status de pagamento: {_status_pagamento(order.get('paymentStatus'))}",
    ]
    if order.get("paymentStatus") in ("PARTIAL", "PAID"):
        linhas.append(f"Valor pago: {_brl(order.get('amountPaid'))}")

    items = order.get("items") or []
    if items:
        linhas.append("Serviços:")
        for item in items:
            nome = (item.get("service") or {}).get("name", "—")
            linhas.append(f"- {nome}: {_brl(item.get('finalPrice'))}")

    if order.get("notes"):
        linhas.append(f"Observações: {order['notes']}")

    return "\n".join(linhas)


def _handle_servicos(user_id: str) -> str:
    services = backend_client.list_services(user_id)
    if not services:
        return "Você ainda não tem nenhum serviço cadastrado."

    linhas = [f"Você tem {len(services)} serviço(s) cadastrado(s):"]
    for s in services[:20]:
        linhas.append(f"- {s.get('name')}: {_brl(s.get('salePrice'))}")
    if len(services) > 20:
        linhas.append(f"... e mais {len(services) - 20} serviço(s).")
    return "\n".join(linhas)


def _handle_clientes(user_id: str) -> str:
    clients = backend_client.list_clients(user_id)
    if not clients:
        return "Você ainda não tem nenhum cliente cadastrado."

    linhas = [f"Você tem {len(clients)} cliente(s) cadastrado(s):"]
    for c in clients[:20]:
        linha = f"- {c.get('name')}"
        if c.get("phone"):
            linha += f" ({c['phone']})"
        linhas.append(linha)
    if len(clients) > 20:
        linhas.append(f"... e mais {len(clients) - 20} cliente(s).")
    return "\n".join(linhas)


def _handle_link_cliente(user_id: str, intencao: IntencaoFly) -> str:
    if not intencao.client_name:
        return PEDIR_CLIENTE_MSG

    client, erro = _resolve_client(user_id, intencao.client_name)
    if erro:
        return erro

    url = backend_client.get_client_link(user_id, client["id"])
    if not url:
        return f"Não consegui gerar o link do cliente {client['name']}."
    return f"Aqui está o link personalizado de {client['name']}: {url}"


def _handle_dividas(user_id: str, intencao: IntencaoFly) -> str:
    debts = backend_client.get_debts(user_id, intencao.start, intencao.end)
    if not debts:
        return "Você não tem nenhuma dívida registrada no momento."

    total = sum(float(d.get("amount", 0)) - float(d.get("amountPaid", 0)) for d in debts)
    linhas = [f"Você tem {len(debts)} dívida(s) registrada(s), totalizando {_brl(total)} em aberto:"]
    for d in debts[:10]:
        linhas.append(f"- {d.get('description')}: {_brl(d.get('amount'))} ({d.get('paymentStatus')})")
    return "\n".join(linhas)


def _handle_saidas_caixa(user_id: str, intencao: IntencaoFly) -> str:
    expenses = backend_client.get_expenses(user_id, intencao.start, intencao.end)
    if not expenses:
        return "Não encontrei nenhuma saída de caixa registrada nesse período."

    total = sum(float(e.get("amount", 0)) for e in expenses)
    linhas = [f"Saídas de caixa: {len(expenses)} lançamento(s), totalizando {_brl(total)}:"]
    for e in expenses[:10]:
        linhas.append(f"- {e.get('description')}: {_brl(e.get('amount'))} ({e.get('status')})")
    return "\n".join(linhas)


def _handle_relatorio(user_id: str, intencao: IntencaoFly) -> str:
    if not intencao.start or not intencao.end:
        return PEDIR_PERIODO_MSG

    dados = backend_client.get_financial_report(user_id, intencao.start, intencao.end)
    label = _periodo_label(intencao.start, intencao.end)
    return (
        f"Relatório saídas x faturamento {label}:\n"
        f"Entrada de caixa: {_brl(dados['cashIn'])}\n"
        f"Saídas de caixa: {_brl(dados['totalExpenses'])} "
        f"(pago: {_brl(dados['totalPaidExpenses'])}, pendente: {_brl(dados['totalPendingExpenses'])})\n"
        f"Dívidas em aberto: {_brl(dados['totalDebtOutstanding'])}\n"
        f"Caixa atual: {_brl(dados['currentCash'])}"
    )


def _handle_boleto(user_id: str) -> str:
    invoice = backend_client.get_invoice(user_id)
    if not invoice:
        return "Não encontrei nenhuma fatura da sua assinatura Fluxy Gestão."

    status_label = {"paid": "paga", "open": "em aberto", "overdue": "vencida"}.get(invoice["displayStatus"], invoice["displayStatus"])
    texto = (
        f"Fatura de referência {invoice['referenceMonth']}: {_brl(invoice['amount'])} — {status_label}\n"
        f"Vencimento: {_data_br(invoice['dueDate'])}"
    )
    if invoice.get("invoiceUrl") and invoice["displayStatus"] != "paid":
        texto += f"\nLink para pagamento: {invoice['invoiceUrl']}"
    return texto


def responder(
    pergunta: str,
    target: dict,
    agent_id: str,
    agent_name: str,
    history: Optional[list] = None,
    session: Optional[dict] = None,
) -> list[str]:
    # Verificado antes de qualquer identificação/classificação normal — atende também
    # leads sem cadastro na Fluxy Gestão que só marcaram uma reunião/demo. Só entra em
    # ação quando o contato tem um agendamento pendente (Target.metadata.agendamentoProposta).
    resposta_agendamento = tratar_fluxo_agendamento(pergunta, target, session)
    if resposta_agendamento is not None:
        return resposta_agendamento

    user = resolve_authenticated_user(target)
    if not user:
        return [NAO_LOCALIZADO_MSG]

    try:
        intencao = classificar_pergunta(pergunta, history)
    except Exception:
        return [INSTABILIDADE_MSG]

    if intencao.categoria == "fora_de_escopo":
        return [NAO_ENTENDI_MSG, MENU_MSG]

    try:
        if intencao.categoria == "faturamento":
            return [_handle_faturamento(user["id"], intencao)]
        if intencao.categoria == "custos":
            return [_handle_custos(user["id"], intencao)]
        if intencao.categoria == "os_periodo":
            return [_handle_os_periodo(user["id"], intencao)]
        if intencao.categoria == "os_cliente":
            return [_handle_os_cliente(user["id"], intencao)]
        if intencao.categoria == "os_detalhe":
            return [_handle_os_detalhe(user["id"], intencao)]
        if intencao.categoria == "link_cliente":
            return [_handle_link_cliente(user["id"], intencao)]
        if intencao.categoria == "servicos":
            return [_handle_servicos(user["id"])]
        if intencao.categoria == "clientes":
            return [_handle_clientes(user["id"])]
        if intencao.categoria == "dividas":
            return [_handle_dividas(user["id"], intencao)]
        if intencao.categoria == "saidas_caixa":
            return [_handle_saidas_caixa(user["id"], intencao)]
        if intencao.categoria == "relatorio":
            return [_handle_relatorio(user["id"], intencao)]
        if intencao.categoria == "boleto":
            return [_handle_boleto(user["id"])]
    except backend_client.DiamanteRequiredError:
        return [DIAMANTE_MSG]
    except httpx.HTTPError:
        return [INSTABILIDADE_MSG]

    return [NAO_ENTENDI_MSG, MENU_MSG]
