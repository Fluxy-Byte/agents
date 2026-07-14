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
