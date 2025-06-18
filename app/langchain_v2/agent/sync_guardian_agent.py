from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable

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

from app.langchain_v2.tools.replenishment import (
    estimate_lead_time_by_sku_and_destination,
    estimate_lead_time_by_destination,
    get_replenishment_recommendation,
)

from app.langchain_v2.tools.fallback.handle_unknown_request import handle_unknown_request

from app.langchain_v2.memory.session_memory import get_session_history_from_db


async def createSyncGuardianAgent(
    model: ChatOpenAI,
    account_id: str,
    user_id: str,
    session_id: str,
    user_type: str,
):
    """
    Cria o agente IA com ferramentas e contexto.
    """

    # 🔥 Histórico vindo da Supabase
    history_data = get_session_history_from_db(session_id)
    chat_history = []
    for row in history_data:
        if row["role"] == "user" and row.get("question"):
            chat_history.append({"role": "user", "content": row["question"]})
        elif row["role"] in ["ai", "assistant"] and row.get("answer"):
            chat_history.append({"role": "assistant", "content": row["answer"]})

    # 🔥 Prompt estruturado
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT + "\n\n" + EXAMPLES_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    tools = [
        get_inventory_by_sku,
        get_stock_forecast_by_sku,
        get_products_at_risk,
        get_top_revenue_skus_by_period,
        get_top_selling_inventory,
        get_top_selling_skus_by_period,
        list_products,
        list_available_warehouses,
        handle_unknown_request,
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
        estimate_lead_time_by_sku_and_destination,
        estimate_lead_time_by_destination,
        get_replenishment_recommendation,
        summarize_orders_by_client,
        get_top_selling_products_by_client,
        summarize_order_status_by_client,
        summarize_revenue_trend_by_client,
        summarize_sales_by_period,
        list_sales_by_period,
    ]

    # 🔥 Agente
    agent = create_openai_functions_agent(
        llm=model,
        prompt=prompt,
        tools=tools,
    )

    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
    )

    # 🔥 Retorna executor + histórico junto (como tuple ou dict)
    return executor, chat_history