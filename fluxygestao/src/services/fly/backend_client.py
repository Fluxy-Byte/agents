import os
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("FLUXY_BACKEND_BASE_URL", "http://localhost:6501")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")

_HEADERS = {"x-internal-api-key": INTERNAL_API_KEY}
_TIMEOUT = 15


class DiamanteRequiredError(Exception):
    """Levantado quando o usuário pede um dado exclusivo do plano Diamante e não é Diamante."""


def _clean(params: dict) -> dict:
    return {k: v for k, v in params.items() if v is not None}


def _get(path: str, params: Optional[dict] = None) -> httpx.Response:
    return httpx.get(
        f"{BASE_URL}/api/internal/assistant{path}",
        params=_clean(params or {}),
        headers=_HEADERS,
        timeout=_TIMEOUT,
    )


def get_user_by_phone(phone: str) -> Optional[dict]:
    resp = _get("/users/by-phone", {"phone": phone})
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def get_user(user_id: str) -> Optional[dict]:
    resp = _get(f"/users/{user_id}")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def get_dashboard(user_id: str) -> dict:
    resp = _get(f"/users/{user_id}/dashboard")
    resp.raise_for_status()
    return resp.json()


def get_report(user_id: str, start: str, end: str) -> dict:
    resp = _get(f"/users/{user_id}/report", {"start": start, "end": end})
    resp.raise_for_status()
    return resp.json()


def search_clients(user_id: str, name: str) -> list:
    resp = _get(f"/users/{user_id}/clients", {"name": name})
    resp.raise_for_status()
    return resp.json()


def list_clients(user_id: str) -> list:
    resp = _get(f"/users/{user_id}/clients/all")
    resp.raise_for_status()
    return resp.json()


def list_services(user_id: str) -> list:
    resp = _get(f"/users/{user_id}/services")
    resp.raise_for_status()
    return resp.json()


def get_order_by_number(user_id: str, number_order: int) -> Optional[dict]:
    resp = _get(f"/users/{user_id}/orders/{number_order}")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def get_client_orders(user_id: str, client_id: str) -> list:
    resp = _get(f"/users/{user_id}/clients/{client_id}/orders")
    resp.raise_for_status()
    return resp.json()


def get_client_link(user_id: str, client_id: str) -> Optional[str]:
    resp = _get(f"/users/{user_id}/clients/{client_id}/link")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()["url"]


def get_debts(user_id: str, start: Optional[str] = None, end: Optional[str] = None) -> list:
    resp = _get(f"/users/{user_id}/debts", {"start": start, "end": end})
    if resp.status_code == 403:
        raise DiamanteRequiredError()
    resp.raise_for_status()
    return resp.json()


def get_expenses(user_id: str, start: Optional[str] = None, end: Optional[str] = None) -> list:
    resp = _get(f"/users/{user_id}/expenses", {"start": start, "end": end})
    if resp.status_code == 403:
        raise DiamanteRequiredError()
    resp.raise_for_status()
    return resp.json()


def get_financial_report(user_id: str, start: str, end: str) -> dict:
    resp = _get(f"/users/{user_id}/financial-report", {"start": start, "end": end})
    if resp.status_code == 403:
        raise DiamanteRequiredError()
    resp.raise_for_status()
    return resp.json()


def get_invoice(user_id: str) -> Optional[dict]:
    resp = _get(f"/users/{user_id}/invoice")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()
