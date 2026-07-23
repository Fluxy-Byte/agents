from dotenv import load_dotenv

from src.services.queue.consumer import start_consumer

load_dotenv()

if __name__ == "__main__":
    start_consumer()
