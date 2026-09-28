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


# ---------------------------------------------------------------------------
# 主数据接口（对应 aps /open/md/*，供 masterdata 角色核对基础数据）
#   字段名以 aps 实际返回为准：物料的 initial_inventory / min_inventory /
#   max_inventory、工序的 step_order（数据库真实列名为 step_order，非旧文档的 step_no）
# ---------------------------------------------------------------------------
async def aps_md_materials(code: str = "", search: str = "", category: str = "",
                           page: int = 1, page_size: int = 50) -> dict:
    """物料台账：编码精确 / 名称或编码模糊 / 类别过滤 + 分页"""
    return await aps_request("GET", "/open/md/materials", params={
        "code": code, "search": search, "category": category,
        "page": page, "page_size": page_size,
    })


async def aps_md_bom(parent_material_code: str, max_level: int = 5) -> dict:
    """BOM 多级展开：从 parent_material_code 向下展开 max_level 层"""
    return await aps_request("GET", "/open/md/bom", params={
        "parent_material_code": parent_material_code, "max_level": max_level,
    })


async def aps_md_routing(material_code: str, routing_id: int | None = None) -> dict:
    """工艺路线：按物料编码返回路线与工序明细（可选只取某条 routing_id）"""
    params: dict[str, Any] = {"material_code": material_code}
    if routing_id is not None:
        params["routing_id"] = routing_id
    return await aps_request("GET", "/open/md/routing", params=params)


async def aps_md_resources(code: str = "", resource_type: str = "",
                           page: int = 1, page_size: int = 50) -> dict:
    """设备/工装台账：编码精确 / 类型（EQUIPMENT / FIXTURE 或中文 设备 / 工装）+ 分页"""
    return await aps_request("GET", "/open/md/resources", params={
        "code": code, "type": resource_type,
        "page": page, "page_size": page_size,
    })
