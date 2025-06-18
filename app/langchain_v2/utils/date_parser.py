from datetime import datetime, timedelta
import calendar
import re
from dateparser.search import search_dates


# 🚀 Tradução multilíngue (PT → EN), pode expandir pra ES fácil.
def translate_period_input(input_text: str) -> str:
    """
    Translates period input from Portuguese to English before parsing.
    """
    translations = {
    "este mês": "this month",
    "este mes": "this month",
    "esse mês": "this month",
    "esse mes": "this month",
    "mês passado": "last month",
    "mes passado": "last month",
    "esta semana": "this week",
    "essa semana": "this week",
    "semana passada": "last week",
    "últimos 30 dias": "last 30 days",
    "ultimos 30 dias": "last 30 days"
    }
    lowered = input_text.lower()

    for pt_text, en_text in translations.items():
        if pt_text in lowered:
            lowered = lowered.replace(pt_text, en_text)

    return lowered


# 🔥 Parser principal
def parse_period_input(input_text: str):
    """
    Parse absolute periods like 'May', 'last month', 'this week', 'May 2024', etc.
    Returns (start_date, end_date) as isoformat strings.
    """

    input_text = translate_period_input(input_text)
    lowered = input_text.lower()
    today = datetime.utcnow().date()

    months = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,

        # ✅ Opcional: suporte a português
        "janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4,
        "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
        "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12
    }

    # 👉 Last 30 days
    if "last 30 days" in lowered:
        return (today - timedelta(days=30)).isoformat(), today.isoformat()

    # 👉 Last month
    if "last month" in lowered:
        year = today.year
        month = today.month - 1
        if month == 0:
            month = 12
            year -= 1
        start = datetime(year, month, 1).date()
        end = datetime(year, month, calendar.monthrange(year, month)[1]).date()
        return start.isoformat(), end.isoformat()

    # 👉 This month
    if "this month" in lowered:
        start = today.replace(day=1)
        end = today  # ✅ até hoje
        return start.isoformat(), end.isoformat()

    # 👉 Last week
    if "last week" in lowered:
        end = today - timedelta(days=today.weekday() + 1)
        start = end - timedelta(days=6)
        return start.isoformat(), end.isoformat()

    # 👉 This week
    if "this week" in lowered:
        start = today - timedelta(days=today.weekday())
        end = today
        return start.isoformat(), end.isoformat()

    # 👉 Named months (e.g., 'May' ou 'May 2024')
    for name, num in months.items():
        if name in lowered:
            year = today.year
            year_match = re.search(rf"{name} (\d{{4}})", lowered)
            if year_match:
                year = int(year_match.group(1))
            start = datetime(year, num, 1).date()
            end = datetime(year, num, calendar.monthrange(year, num)[1]).date()
            return start.isoformat(), end.isoformat()

    # 👉 Fallback: busca datas naturais
    dates = search_dates(input_text, settings={"PREFER_DATES_FROM": "past"})
    if dates and len(dates) >= 2:
        start = dates[0][1].date()
        end = dates[1][1].date()
        return start.isoformat(), end.isoformat()
    elif dates and len(dates) == 1:
        start = dates[0][1].date()
        end = today
        return start.isoformat(), end.isoformat()

    raise ValueError("❌ Could not parse the period from input.")


# 🔁 Período anterior simples (baseado em quantidade de dias)
def get_previous_period(start_date_str: str, end_date_str: str):
    """
    Given a start_date and end_date, returns the previous period with same length.
    """
    start_date = datetime.fromisoformat(start_date_str).date()
    end_date = datetime.fromisoformat(end_date_str).date()

    period_length = (end_date - start_date).days + 1

    previous_end = start_date - timedelta(days=1)
    previous_start = previous_end - timedelta(days=period_length - 1)

    return previous_start.isoformat(), previous_end.isoformat()


# 🚀 Período anterior inteligente (mês, semana, 30 dias)
def get_comparative_period_smart(input_text: str, start_date_str: str, end_date_str: str):
    """
    Smarter comparative period.
    If the period is 'this month' (ex: 2025-06-01 to 2025-06-17),
    then compares to the full last month (2025-05-01 to 2025-05-31).
    Otherwise, falls back to period of same length.
    """
    lowered = input_text.lower()
    start_date = datetime.fromisoformat(start_date_str).date()
    end_date = datetime.fromisoformat(end_date_str).date()

    # Check for "this month"
    if any(kw in lowered for kw in ["this month", "este mês", "este mes"]):
        # 🔥 Current month = start_date to today
        # 🔥 Previous = full last month
        prev_month = start_date.month - 1 or 12
        prev_year = start_date.year - 1 if prev_month == 12 else start_date.year

        prev_start = datetime(prev_year, prev_month, 1).date()
        prev_end = datetime(
            prev_year, prev_month, calendar.monthrange(prev_year, prev_month)[1]
        ).date()

        return prev_start.isoformat(), prev_end.isoformat()

    # Check for "this week"
    if any(kw in lowered for kw in ["this week", "esta semana"]):
        start_of_this_week = start_date - timedelta(days=start_date.weekday())
        start_of_last_week = start_of_this_week - timedelta(days=7)

        return (
            start_of_last_week.isoformat(),
            (start_of_last_week + timedelta(days=6)).isoformat(),
        )

    # Check for "last 30 days"
    if any(kw in lowered for kw in ["last 30 days", "últimos 30 dias", "ultimos 30 dias"]):
        prev_end = start_date - timedelta(days=1)
        prev_start = prev_end - timedelta(days=29)

        return prev_start.isoformat(), prev_end.isoformat()

    # 🔁 Default fallback: same length
    period_length = (end_date - start_date).days + 1
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_length - 1)

    return prev_start.isoformat(), prev_end.isoformat()

def parse_dual_period_input(input_text: str):
    """
    Parse inputs like 'this month versus last month' or 'May compared to April'.
    Returns ((start1, end1), (start2, end2)) as isoformat strings.
    """
    lowered = translate_period_input(input_text.lower())

    # 🔥 Check for 'this month versus last month'
    if "this month" in lowered and "last month" in lowered:
        today = datetime.utcnow().date()
        # This month
        start1 = today.replace(day=1)
        end1 = today

        # Last month
        prev_month = start1.month - 1 or 12
        prev_year = start1.year - 1 if prev_month == 12 else start1.year
        start2 = datetime(prev_year, prev_month, 1).date()
        end2 = datetime(
            prev_year, prev_month, calendar.monthrange(prev_year, prev_month)[1]
        ).date()

        return ((start1.isoformat(), end1.isoformat()), (start2.isoformat(), end2.isoformat()))

    # 🔥 Aqui pode expandir depois pra outros padrões como 'May vs April'

    raise ValueError("❌ Could not parse dual period from input.")