import json

import pika


def publish_task_send(channel, task: dict) -> None:
    queue = "task.send.create"
    dlq = "task.send.dlq"

    channel.queue_declare(queue=dlq, durable=True)
    channel.queue_declare(
        queue=queue,
        durable=True,
        arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": dlq,
        },
    )

    channel.basic_publish(
        exchange="",
        routing_key=queue,
        body=json.dumps(task, ensure_ascii=False),
        properties=pika.BasicProperties(delivery_mode=2),
    )

    print(f"\n🟣 Publicou na fila {queue}")
