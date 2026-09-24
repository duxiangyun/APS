"""APS HTTP 客户端：agent 后端与 aps 系统交互的唯一通道。

严格通过 HTTP 访问 aps 的 /open/* 开放接口，不 import aps 的任何内部模块。
"""
from typing import Any

import httpx

from .config import APS_BASE_URL


class APSApiError(Exception):
    """APS 接口调用失败"""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"APS API {status_code}: {detail}")


async def aps_request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> Any:
    """调用 APS 开放接口，非 2xx 抛出 APSApiError"""
    url = f"{APS_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.request(method, url, params=params, json=json_body)
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise APSApiError(resp.status_code, str(detail))
    if resp.status_code == 204 or not resp.content:
        return None
    return resp.json()


# ---------------------------------------------------------------------------
# 具体接口封装（对应 aps /open/* 路由）
# ---------------------------------------------------------------------------
async def aps_health() -> dict:
    return await aps_request("GET", "/open/health")


async def aps_kpi_summary() -> dict:
    return await aps_request("GET", "/open/kpi/summary")


async def aps_kpi_delivery() -> dict:
    return await aps_request("GET", "/open/kpi/delivery")


async def aps_orders(search: str = "", page: int = 1, page_size: int = 50) -> dict:
    return await aps_request("GET", "/open/orders", params={
        "search": search, "page": page, "page_size": page_size,
    })


async def aps_order_detail(order_id: int) -> dict:
    return await aps_request("GET", f"/open/orders/{order_id}")


async def aps_result_views() -> dict:
    return await aps_request("GET", "/open/results/views")


async def aps_result_data(view_key: str, page: int = 1, page_size: int = 50) -> dict:
    return await aps_request("GET", f"/open/results/{view_key}", params={
        "page": page, "page_size": page_size,
    })


async def aps_equip_load() -> dict:
    return await aps_request("GET", "/open/equip-load")


async def aps_iis(inf_type: str = "") -> dict:
    return await aps_request("GET", "/open/iis", params={"inf_type": inf_type})


async def aps_solve_status() -> dict:
    return await aps_request("GET", "/open/solve/status")


async def aps_solve_start() -> dict:
    return await aps_request("POST", "/open/solve/start")
