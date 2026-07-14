import json

from main import gerar_resposta
from src.infra.rabbitmq.connection import RabbitMQ
from src.services.queue.publisher import publish_task_send

# Por enquanto só existe o agente "fluxy" cadastrado no orquestrador.
AGENT_NAME = "fluxy"
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
            resposta = gerar_resposta(pergunta, agent_info.get("id"), agent_info.get("name")) if pergunta else ""
        except Exception as e:
            print(f"❌ Erro ao gerar resposta do agente {AGENT_NAME}: {e}")
            resposta = agent_info.get("message") or ""

        send_task = {
            "target": payload.get("target"),
            "waba": payload.get("waba"),
            "session": payload.get("session"),
            "message": payload.get("message"),
            "answer": {
                "answer": resposta,
                "audio": "",
                "image": "",
            },
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
