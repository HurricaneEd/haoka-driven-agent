# -*- coding: utf-8 -*-
from langchain_core.tools import tool

# Mock 订单数据：真实项目中应改为查询订单服务/数据库
MOCK_ORDERS = {
    "ORD-1001": {"status": "已发货", "items": "流量卡",    "eta": "2026-08-10"},
    "ORD-1002": {"status": "处理中", "items": "流量套餐",  "eta": "2026-08-12"},
    "ORD-1003": {"status": "已送达", "items": "补换卡",    "eta": "2026-08-01"},
}


@tool
def search_order(order_id: str) -> str:
    """当用户询问订单状态、物流进度、包裹到哪了时使用。参数为订单号，如 ORD-1001。"""
    oid = (order_id or "").strip().upper()
    order = MOCK_ORDERS.get(oid)
    if not order:
        return f"未找到订单 {oid}，请确认订单号格式（如 ORD-1001）。"
    return (
        f"订单 {oid} 当前状态：{order['status']}，"
        f"商品：{order['items']}，预计送达：{order['eta']}。"
    )


@tool
def transfer_to_human() -> str:
    """当用户要求转人工、投诉、情绪激动或机器人无法解决时使用。无参数。"""
    return "已为您转接人工客服，工号 1012 正在接听，请稍候……"


@tool
def reset_password(email: str) -> str:
    """当用户要重置密码时使用。参数为用户的注册邮箱。"""
    return f"已向 {email} 发送密码重置链接，请在 5 分钟内完成修改。"


# 纯工具（与实例无关）：Agent 内部再把 search_knowledge 加进来组装 TOOLS。
BASE_TOOLS = [search_order, transfer_to_human, reset_password]
