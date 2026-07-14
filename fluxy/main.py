import os

from src.services.root.root import definir_categoria_da_pergunta
from src.services.produto.produtos import gerar_resposta_sobre_produtos
from src.services.suporte.suporte import gerar_resposta_sobre_suporte
from src.services.renda_extra.renda_extra import gerar_resposta_sobre_renda_extra


def gerar_resposta(pergunta: str, agent_id: str, agent_name: str):
    categoria = definir_categoria_da_pergunta(pergunta)

    if categoria == "produto":
        return gerar_resposta_sobre_produtos(pergunta, agent_id, agent_name, categoria)
    elif categoria == "renda-extra":
        return gerar_resposta_sobre_renda_extra(pergunta, agent_id, agent_name, categoria)
    return gerar_resposta_sobre_suporte(pergunta, agent_id, agent_name, categoria)


if __name__ == "__main__":
    print(gerar_resposta("Como ganho dinheiro com renda extra", "fluxy-id", "fluxy"))