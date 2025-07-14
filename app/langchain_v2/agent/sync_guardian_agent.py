from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_functions_agent, AgentExecutor, Tool
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

from app.langchain_v2.tools.orders.list_order_products_by_id import list_order_products_by_id

from app.langchain_v2.tools.orders.get_shipping_details_by_order_id import get_shipping_details_by_order_id

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
        Tool(
            name="get_order_status_by_id",
            func=get_order_status_by_id,
            description="Gets the status of an order by its ID",
            return_direct=True
        ),
        Tool(
            name="get_shipping_details_by_order_id",
            func=get_shipping_details_by_order_id,
            description="Returns shipping and logistics info for an order, such as tracking number, carrier, delivery estimate, and warehouse.",
            return_direct=True
        ),
        Tool(
            name="list_order_products_by_id",
            func=list_order_products_by_id,
            description="Returns the list of products inside a specific order, such as SKUs, names, quantity and unit price. Use this tool when the user wants to see the items or products included in an order, not the status or sales summary.",
            return_direct=True
        ),
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

    from langchain_core.runnables import RunnableLambda

    executor = (
        RunnableLambda(lambda x: {
            "input": x["input"],
            "chat_history": x["chat_history"],  # ✅ Corrigido para incluir chat_history
            "account_id": x.get("account_id"),
            "user_id": x.get("user_id"),
            "session_id": x.get("session_id"),
            "user_type": x.get("user_type"),
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