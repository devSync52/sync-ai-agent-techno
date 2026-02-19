from langchain.tools import tool
from app.langchain_v2.utils.session_context import get_current_session_context


@tool
def handle_unknown_request() -> str:
    """
    Fallback tool to handle unknown or unsupported user requests.
    It forwards the request to the SynC support team.
    """
    session = get_current_session_context()
    company_name = str(session.get("company_name") or "SynC Fulfillment").strip() or "SynC Fulfillment"

    return (
        "Thank you for reaching out with your question. "
        f"I'm still learning to provide you with the best experience at {company_name}.\n\n"
        "I’ve forwarded your request to our SynC Team at info@synccomusa.com and ctelles@synccomusa.com. "
        "They will get back to you shortly."
    )


handle_unknown_request_tool = handle_unknown_request
