import os
from datetime import date
from typing import Literal, Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

load_dotenv()

modelo = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    api_key=os.getenv("OPENAI_API_KEY"),
)

Categoria = Literal[
    "faturamento",
    "custos",
    "os_cliente",
    "os_periodo",
    "dividas",
    "saidas_caixa",
    "relatorio",
    "boleto",
    "link_cliente",
    "fora_de_escopo",
]


class IntencaoFly(BaseModel):
    categoria: Categoria = Field(description="Categoria da pergunta do usuário.")
    start: Optional[str] = Field(
        default=None,
        description="Data inicial do período perguntado, formato YYYY-MM-DD. Só preencha se o período estiver claro (explícito ou um termo relativo óbvio como 'hoje', 'essa semana', 'esse mês', 'mês passado'). Deixe vazio se não estiver claro.",
    )
    end: Optional[str] = Field(
        default=None,
        description="Data final do período perguntado, formato YYYY-MM-DD. Mesmas regras de 'start'.",
    )
    client_name: Optional[str] = Field(
        default=None,
        description="Nome do cliente mencionado, para perguntas sobre ordens de serviço de um cliente específico ou o link personalizado de um cliente.",
    )


prompt_intencao = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
Você classifica mensagens recebidas por WhatsApp de donos de empresas já autenticados numa plataforma de gestão de ordens de serviço (Fluxy Gestão).

Categorias possíveis:
- faturamento: quanto a empresa faturou (dinheiro que entrou), hoje ou em um período.
- custos: custo das ordens de serviço em um período.
- os_cliente: ordens de serviço de um cliente específico, identificado pelo nome.
- os_periodo: quantidade/lista de ordens de serviço abertas em um período ou no dia (não é sobre dinheiro, é sobre as ordens em si).
- dividas: dívidas da empresa.
- saidas_caixa: despesas / saídas de caixa da empresa.
- relatorio: relatório comparando saídas de caixa com faturamento.
- boleto: boleto/fatura de pagamento da própria assinatura da plataforma Fluxy Gestão (não é dívida do cliente do usuário).
- link_cliente: link personalizado/catálogo de um cliente específico para ele mesmo comprar.
- fora_de_escopo: use SOMENTE quando o assunto em si não tem nenhuma relação com os temas acima — ex: saudações genéricas sem pedido nenhum, temas ilegais, drogas, sexologia, ou qualquer coisa fora do escopo da plataforma.

IMPORTANTE: se a pergunta é claramente sobre um dos temas de negócio acima mas está faltando um detalhe (período, nome do cliente etc.), a categoria continua sendo a mesma daquele tema — NUNCA classifique como fora_de_escopo só porque falta um detalhe. Faltar informação não é a mesma coisa que estar fora de escopo. Exemplo: "quero saber meu faturamento" é categoria "faturamento" com start/end vazios (não "fora_de_escopo").

Hoje é {hoje}. Se o usuário mencionar um período relativo ("hoje", "essa semana", "esse mês", "mês passado"), converta para datas absolutas no formato YYYY-MM-DD. Nunca invente um período que o usuário não sugeriu — se a categoria precisar de período e não estiver claro, deixe start/end vazios.

Use as mensagens anteriores abaixo (se houver) só para entender referências da pergunta atual, como "e ontem?" ou "e desse cliente?" continuando um assunto já iniciado — a classificação é sempre sobre a pergunta atual.

{historico}
""",
        ),
        ("human", "{query}"),
    ]
)

classificador = prompt_intencao | modelo.with_structured_output(IntencaoFly)


def _formatar_historico(historico: Optional[list]) -> str:
    if not historico:
        return "(sem mensagens anteriores)"

    linhas = []
    for item in historico[-3:]:
        pergunta = item.get("question_message")
        resposta = item.get("answer_message")
        if pergunta:
            linhas.append(f"Usuário: {pergunta}")
        if resposta:
            linhas.append(f"Fly: {resposta}")
    return "\n".join(linhas) if linhas else "(sem mensagens anteriores)"


def classificar_pergunta(pergunta: str, historico: Optional[list] = None) -> IntencaoFly:
    return classificador.invoke({
        "query": pergunta,
        "hoje": date.today().isoformat(),
        "historico": _formatar_historico(historico),
    })
