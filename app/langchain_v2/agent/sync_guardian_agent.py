from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_functions_agent, AgentExecutor, Tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable
from typing import List
import logging

from app.langchain_v2.prompts.system_prompt import __doc__ as SYSTEM_PROMPT
from app.langchain_v2.prompts.examples_prompt import __doc__ as EXAMPLES_PROMPT

from app.langchain_v2.tools.inventory import (
    get_inventory_by_sku,
    get_stock_forecast_by_sku,
    get_products_at_risk,
    get_top_revenue_skus_by_period,
    get_top_selling_inventory,
    get_top_selling_skus_by_period,
    list_products,
    list_available_warehouses,
)

from app.langchain_v2.tools.orders import (
    get_order_status_by_id,
    get_sku_sales_by_period,
    get_tracking_info_by_order_id,
    summarize_orders_by_period_by_marketplace,
    summarize_orders_by_period,
    warehouse_orders_tool,
    compare_sku_sales_by_period,
    compare_marketplaces_by_period,
    compare_sales_by_period,
    compare_revenue_by_period,
    summarize_orders_by_client,
    get_top_selling_products_by_client,
    summarize_order_status_by_client,
    summarize_revenue_trend_by_client,
    summarize_sales_by_period,
    list_sales_by_period,
)

from app.langchain_v2.tools.orders.list_order_products_by_id import list_order_products_by_id

from app.langchain_v2.tools.orders.get_shipping_details_by_order_id import get_shipping_details_by_order_id

from app.langchain_v2.tools.replenishment import (
    estimate_lead_time_by_sku_and_destination,
    estimate_lead_time_by_destination,
    get_replenishment_recommendation,
)

from app.langchain_v2.tools.fallback.handle_unknown_request import handle_unknown_request
from app.langchain_v2.tools.extensiv import (
    get_extensiv_order_status_by_id,
    get_extensiv_shipping_details_by_order_id,
    list_extensiv_order_products_by_id,
    get_extensiv_inventory_by_sku,
    summarize_extensiv_orders_by_period,
    get_pending_orders_alert,
    list_pending_orders_by_filters,
    summarize_order_lifecycle_by_warehouse,
    get_most_pending_warehouse,
    get_order_status_breakdown,
    get_order_progress_by_id,
    get_pending_aging_distribution,
    list_orders_at_risk_sla,
    get_order_details_extensiv,
    summarize_orders_volume_units_by_warehouse,
)

from app.langchain_v2.memory.session_memory import get_session_history_from_db


logger = logging.getLogger("sync-ai-agent")

VALID_USER_TYPES = {"owner", "client", "end_client"}
VALID_INTEGRATION_SOURCES = {"sellercloud", "extensiv", "mixed", "unknown"}
DEFAULT_COMPANY_NAME = "SynC Fulfillment"


def normalize_user_type(user_type: str) -> str:
    normalized = (user_type or "").strip().lower()
    return normalized if normalized in VALID_USER_TYPES else "client"


def normalize_integration_source(source: str) -> str:
    normalized = (source or "").strip().lower()
    return normalized if normalized in VALID_INTEGRATION_SOURCES else "unknown"


def normalize_company_name(company_name: str) -> str:
    normalized = (company_name or "").strip()
    return normalized or DEFAULT_COMPANY_NAME


def build_extensiv_tools_for_user_type(user_type: str) -> List:
    normalized_user_type = normalize_user_type(user_type)

    extensiv_order_tools = [
        Tool(
            name="get_order_status_by_id",
            func=get_extensiv_order_status_by_id,
            description="Gets the status of an Extensiv order by internal ID, external_id or order_number.",
            return_direct=True,
        ),
        Tool(
            name="get_shipping_details_by_order_id",
            func=get_extensiv_shipping_details_by_order_id,
            description="Returns Extensiv shipping and tracking details for an order.",
            return_direct=True,
        ),
        Tool(
            name="get_tracking_info_by_order_id",
            func=get_extensiv_shipping_details_by_order_id,
            description="Returns tracking details for an Extensiv order.",
            return_direct=True,
        ),
        Tool(
            name="list_order_products_by_id",
            func=list_extensiv_order_products_by_id,
            description="Returns SKU items and quantities from an Extensiv order.",
            return_direct=True,
        ),
    ]

    if normalized_user_type == "end_client":
        return [handle_unknown_request, *extensiv_order_tools]

    base_tools = [
        handle_unknown_request,
        *extensiv_order_tools,
        Tool(
            name="get_inventory_by_sku",
            func=get_extensiv_inventory_by_sku,
            description="Retrieves Extensiv inventory levels for a SKU.",
            return_direct=True,
        ),
        Tool(
            name="summarize_orders_by_period",
            func=summarize_extensiv_orders_by_period,
            description="Provides an Extensiv order summary for a given period.",
            return_direct=True,
        ),
        Tool(
            name="get_pending_orders_alert",
            func=get_pending_orders_alert,
            description="Builds pending-orders alert, including warning and critical buckets.",
            return_direct=True,
        ),
        Tool(
            name="list_pending_orders_by_filters",
            func=list_pending_orders_by_filters,
            description="Lists pending Extensiv orders with search/status/warehouse/date filters.",
            return_direct=True,
        ),
        Tool(
            name="summarize_order_lifecycle_by_warehouse",
            func=summarize_order_lifecycle_by_warehouse,
            description="Summarizes Created/Allocated/Picked/Packed/Shipped distribution by warehouse.",
            return_direct=True,
        ),
        Tool(
            name="get_most_pending_warehouse",
            func=get_most_pending_warehouse,
            description="Returns the warehouse with highest pending backlog.",
            return_direct=True,
        ),
        Tool(
            name="get_order_status_breakdown",
            func=get_order_status_breakdown,
            description="Returns status breakdown counts for Extensiv orders.",
            return_direct=True,
        ),
        Tool(
            name="get_order_progress_by_id",
            func=get_order_progress_by_id,
            description="Returns progress/timeline details for one Extensiv order.",
            return_direct=True,
        ),
        Tool(
            name="get_pending_aging_distribution",
            func=get_pending_aging_distribution,
            description="Returns pending-order aging distribution using SLA-like hour buckets.",
            return_direct=True,
        ),
        Tool(
            name="list_orders_at_risk_sla",
            func=list_orders_at_risk_sla,
            description="Lists pending orders currently at risk against temporary SLA thresholds.",
            return_direct=True,
        ),
        Tool(
            name="get_order_details_extensiv",
            func=get_order_details_extensiv,
            description="Returns detailed Extensiv order header and item lines.",
            return_direct=True,
        ),
        Tool(
            name="summarize_orders_volume_units_by_warehouse",
            func=summarize_orders_volume_units_by_warehouse,
            description="Summarizes orders, units, weight and volume by warehouse.",
            return_direct=True,
        ),
    ]

    return base_tools


def build_sellercloud_tools_for_user_type(user_type: str) -> List:
    normalized = normalize_user_type(user_type)

    common_order_tools = [
        Tool(
            name="get_order_status_by_id",
            func=get_order_status_by_id,
            description="Gets the status of an order by its ID",
            return_direct=True,
        ),
        Tool(
            name="get_shipping_details_by_order_id",
            func=get_shipping_details_by_order_id,
            description="Returns shipping and logistics info for an order, such as tracking number, carrier, delivery estimate, and warehouse.",
            return_direct=True,
        ),
        Tool(
            name="list_order_products_by_id",
            func=list_order_products_by_id,
            description="Returns the list of products inside a specific order, such as SKUs, names, quantity and unit price. Use this tool when the user wants to see the items or products included in an order, not the status or sales summary.",
            return_direct=True,
        ),
        get_tracking_info_by_order_id,
    ]

    # End clients: only order visibility + fallback.
    if normalized == "end_client":
        return [handle_unknown_request, *common_order_tools]

    scoped_inventory_tools = [
        get_inventory_by_sku,
        get_stock_forecast_by_sku,
        get_products_at_risk,
        get_top_revenue_skus_by_period,
        get_top_selling_inventory,
        get_top_selling_skus_by_period,
        list_products,
    ]

    scoped_order_tools = [
        get_sku_sales_by_period,
        summarize_orders_by_period_by_marketplace,
        summarize_orders_by_period,
        compare_sku_sales_by_period,
        compare_marketplaces_by_period,
        compare_sales_by_period,
        compare_revenue_by_period,
        summarize_orders_by_client,
        get_top_selling_products_by_client,
        summarize_order_status_by_client,
        summarize_sales_by_period,
        list_sales_by_period,
    ]

    # Owners only: tools that can read global/less scoped data.
    owner_only_tools = [
        list_available_warehouses,
        warehouse_orders_tool,
        summarize_revenue_trend_by_client,
        estimate_lead_time_by_sku_and_destination,
        estimate_lead_time_by_destination,
        get_replenishment_recommendation,
    ]

    base_tools = [handle_unknown_request, *common_order_tools, *scoped_inventory_tools, *scoped_order_tools]

    if normalized == "owner":
        return [*base_tools, *owner_only_tools]

    # client
    return base_tools


def build_tools_for_context(user_type: str, integration_source: str) -> List:
    normalized_integration = normalize_integration_source(integration_source)
    if normalized_integration == "extensiv":
        return build_extensiv_tools_for_user_type(user_type)

    return build_sellercloud_tools_for_user_type(user_type)


async def createSyncGuardianAgent(
    model: ChatOpenAI,
    account_id: str,
    user_id: str,
    session_id: str,
    user_type: str,
    integration_source: str = "sellercloud",
    company_name: str = DEFAULT_COMPANY_NAME,
):
    """
    Cria o agente IA com ferramentas e contexto.
    """
    resolved_user_type = normalize_user_type(user_type)
    resolved_integration_source = normalize_integration_source(integration_source)
    resolved_company_name = normalize_company_name(company_name)

    # 🔥 Histórico vindo da Supabase
    history_data = get_session_history_from_db(session_id)
    chat_history = []
    for row in history_data:
        if row["role"] == "user" and row.get("question"):
            chat_history.append({"role": "user", "content": row["question"]})
        elif row["role"] in ["ai", "assistant"] and row.get("answer"):
            chat_history.append({"role": "assistant", "content": row["answer"]})

    # 🔥 Prompt estruturado
    dynamic_system_prompt = (SYSTEM_PROMPT or "").replace(DEFAULT_COMPANY_NAME, resolved_company_name)
    dynamic_examples_prompt = (EXAMPLES_PROMPT or "").replace(DEFAULT_COMPANY_NAME, resolved_company_name)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", dynamic_system_prompt + "\n\n" + dynamic_examples_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    tools = build_tools_for_context(
        user_type=resolved_user_type,
        integration_source=resolved_integration_source,
    )
    tool_names = [getattr(t, "name", str(t)) for t in tools]
    logger.info(
        f"[Agent] user_type={resolved_user_type} | integration_source={resolved_integration_source} | company_name={resolved_company_name} | tools={tool_names}"
    )

    # 🔥 Agente
    agent = create_openai_functions_agent(
        llm=model,
        prompt=prompt,
        tools=tools,
    )

    from langchain_core.runnables import RunnableLambda

    executor = (
        RunnableLambda(lambda x: {
            "input": x["input"],
            "chat_history": x["chat_history"],  # ✅ Corrigido para incluir chat_history
            "account_id": x.get("account_id"),
            "user_id": x.get("user_id"),
            "session_id": x.get("session_id"),
            "user_type": normalize_user_type(x.get("user_type")),
            "integration_source": normalize_integration_source(x.get("integration_source")),
            "company_name": normalize_company_name(x.get("company_name")),
        }) | AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            handle_parsing_errors=True,
        )
    )

    # 🔥 Retorna executor + histórico junto (como tuple ou dict)
    return executor, chat_history

async def stream_response(agent, input_data):
    final_answer = ""
    async for chunk in agent.astream(input_data):
        yield chunk
        final_answer += chunk.get("text", "")
    # log_final_response(session_id, user_id, final_answer)
