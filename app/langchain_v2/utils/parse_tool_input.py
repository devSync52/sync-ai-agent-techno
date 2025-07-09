def parse_tool_input(tool_input: dict, session_data: dict) -> dict:
    """
    Overrides tool input values with session data if needed.
    """
    parsed_input = tool_input.copy()
    for key in session_data:
        if key in parsed_input and session_data[key] not in [None, "", "123456"]:
            parsed_input[key] = session_data[key]
    return parsed_input