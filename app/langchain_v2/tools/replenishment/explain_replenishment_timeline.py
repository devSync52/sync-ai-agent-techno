from langchain.tools import Tool

def explain_replenishment_timeline():
    return (
        "**SynC**:\n\n"
        "To calculate the ideal reorder date and avoid stockouts, we consider two key elements:\n\n"
        "1. **Your current stock levels** – How many units you have available\n"
        "2. **Total replenishment lead time** – How long it takes for new stock to arrive\n\n"
        "---\n"
        "### 🧮 Example Replenishment Timeline (China → USA)\n\n"
        "| Step                         | Description                          | Estimated Days |\n"
        "|-----------------------------|---------------------------------------|----------------|\n"
        "| Production Readiness        | Manufacturing and packaging           | 7              |\n"
        "| Domestic Transport (CN)     | To port or airport                    | 2              |\n"
        "| Export Clearance (CN)       | Customs and port queue                | 5              |\n"
        "| Air Freight                 | China → USA (air)                     | 4              |\n"
        "| Sea Freight                 | China → USA (by sea)                  | 30             |\n"
        "| Import Clearance (USA)      | US customs and preparation            | 2              |\n"
        "| Final Delivery (USA)        | To your warehouse                     | 2              |\n\n"
        "---\n"
        "These are **example values**, used to explain the concept. The actual duration may vary depending on the supplier, location, or carrier.\n\n"
        "**Calculation logic**:\n"
        "- We sum all estimated days until arrival (air or sea)\n"
        "- Then subtract that from the estimated stock coverage period\n"
        "- The result is the ideal reorder date\n\n"
        "For a more accurate recommendation, we also analyze your **sales velocity** and **average daily consumption**."
    )

explain_replenishment_timeline_tool = Tool.from_function(
    name="explain_replenishment_timeline",
    description=(
        "Use this tool when the user asks how replenishment recommendations are calculated, "
        "including production lead time, shipping steps, and current stock levels. "
        "It returns a static explanation with example timeline and calculation logic."
    ),
    func=lambda _: explain_replenishment_timeline(),
)