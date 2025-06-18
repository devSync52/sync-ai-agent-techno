from langchain.tools import tool


@tool
def handle_unknown_request() -> str:
    """
    Fallback tool to handle unknown or unsupported user requests.
    It forwards the request to the SynC support team.
    """
    return (
        "Thank you for reaching out with your question. "
        "I'm still learning to provide you with the best experience at SynC Fulfillment.\n\n"
        "I’ve forwarded your request to our SynC Team at info@synccomusa.com and ctelles@synccomusa.com. "
        "They will get back to you shortly."
    )


handle_unknown_request_tool = handle_unknown_request