import json

from main import gerar_resposta
from src.infra.rabbitmq.connection import RabbitMQ
from src.services.queue.publisher import publish_task_send

AGENT_NAME = "axel"
QUEUE = f"task.agent.{AGENT_NAME}.create"
DLQ = f"task.agent.{AGENT_NAME}.dlq"


def _extrair_pergunta(message: dict) -> str:
    if not message:
        return ""
    return (message.get("text") or {}).get("body", "")


def _on_message(channel, method, properties, body):
    try:
        payload = json.loads(body)
        agent_info = payload.get("agent") or {}

        try:
            pergunta = _extrair_pergunta(payload.get("message"))
            # Cada item é um dict {"texto": ..., "imagem_url": opcional} — um imóvel com
            # foto vira texto (legenda) + imagem na mesma "parte", cada parte é uma
            # mensagem/bolha separada no WhatsApp.
            partes = gerar_resposta(
                pergunta,
                payload.get("target") or {},
                agent_info.get("id"),
                agent_info.get("name"),
                payload.get("history"),
                payload.get("session"),
            ) if pergunta else [{"texto": ""}]
        except Exception as e:
            print(f"❌ Erro ao gerar resposta do agente {AGENT_NAME}: {e}")

            if agent_info.get("errorEnabled") and agent_info.get("errorMessage"):
                partes = [{"texto": agent_info.get("errorMessage")}]
            else:
                # Toggle de erro desligado: não responde nada nesse turno (o lock de
                # processamento da sessão se libera sozinho após alguns minutos, no
                # Orquestrador). Só confirma a mensagem da fila e encerra.
                channel.basic_ack(delivery_tag=method.delivery_tag)
                return

        # Uma tarefa de envio por parte — quando o agente responde com mais de uma (ex:
        # texto + fotos dos imóveis), cada uma vira uma bolha separada no WhatsApp. A
        # sessão só é liberada (finishesProcessing) na última, para não deixar uma
        # mensagem nova do usuário se intercalar entre elas.
        for idx, parte in enumerate(partes):
            send_task = {
                "target": payload.get("target"),
                "waba": payload.get("waba"),
                "session": payload.get("session"),
                "message": payload.get("message"),
                "answer": {
                    "answer": parte.get("texto") or "",
                    "audio": "",
                    "image": parte.get("imagem_url") or "",
                },
                "finishesProcessing": idx == len(partes) - 1,
            }
            publish_task_send(channel, send_task)

        channel.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"❌ Erro ao processar mensagem do agente {AGENT_NAME}: {e}")
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def start_consumer() -> None:
    rabbitmq = RabbitMQ()
    channel = rabbitmq.connect()

    channel.queue_declare(queue=DLQ, durable=True)
    channel.queue_declare(
        queue=QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": DLQ,
        },
    )

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=QUEUE, on_message_callback=_on_message)

    print(f"🟢 Aguardando mensagens na fila {QUEUE}")
    channel.start_consuming()
