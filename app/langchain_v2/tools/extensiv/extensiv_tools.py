from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.langchain_v2.utils.date_parser import parse_period_input
from app.langchain_v2.utils.session_context import get_current_session_context
from app.utils.supabase_client import get_supabase_client

PENDING_STAGE_KEYS = {"created", "allocated", "picked", "packed"}
DEFAULT_SLA_WARNING_HOURS = 24
DEFAULT_SLA_CRITICAL_HOURS = 72
SLA_DISCLAIMER = (
    "SLA note: we are still structuring the formal SLA definitions. "
    "Thresholds shown below are temporary and may change."
)


def _fetch_all_rows(query, batch_size: int = 1000) -> List[Dict[str, Any]]:
    all_rows: List[Dict[str, Any]] = []
    offset = 0
    last_batch_tail_id: Optional[str] = None
    max_iterations = 5000
    iterations = 0

    while True:
        iterations += 1
        if iterations > max_iterations:
            break

        batch = query.range(offset, offset + batch_size - 1).execute()
        data = batch.data or []

        if not data:
            break

        all_rows.extend(data)

        # Protection against backends that ignore range/offset and keep returning
        # the same trailing row, which would otherwise loop forever.
        tail_id = str((data[-1] or {}).get("id") or "")
        if tail_id and tail_id == last_batch_tail_id:
            break
        last_batch_tail_id = tail_id

        # Advance by the amount actually returned. This avoids gaps when the API
        # enforces a page size lower than the requested batch size.
        offset += len(data)

    return all_rows


def _parse_options(input_text: str) -> Dict[str, Any]:
    raw = (input_text or "").strip()
    if not raw:
        return {}

    if raw.startswith("{") and raw.endswith("}"):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    return {"period": raw}


def _resolve_scope() -> Tuple[Optional[str], str, str]:
    ctx = get_current_session_context()
    account_id = ctx.get("account_id")
    user_type = (ctx.get("user_type") or "client").strip().lower()
    filter_column = "account_id_channel" if user_type == "client" else "account_id"
    return account_id, user_type, filter_column


def _parse_warehouses(options: Dict[str, Any]) -> List[str]:
    value = options.get("warehouses")
    if value is None:
        value = options.get("warehouse")

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]

    return []


def _parse_statuses(options: Dict[str, Any]) -> List[str]:
    value = options.get("statuses")
    if value is None:
        value = options.get("status")

    raw: List[str] = []
    if isinstance(value, list):
        raw = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, str):
        raw = [item.strip() for item in value.split(",") if item.strip()]

    return [_normalize_stage_key(item, False) for item in raw]


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _normalize_stage_key(stage: Any, status_closed: bool) -> str:
    raw = str(stage or "").strip().lower()
    key = "".join(ch for ch in raw if ch.isalnum())

    if key == "created":
        return "created"
    if key in {"allocated", "completed", "separated"}:
        return "allocated"
    if key in {"picked", "orderpickjobdone", "orderpickdone"}:
        return "picked"
    if key in {"packed", "orderpacked", "orderpaked"}:
        return "packed"
    if key in {"shipped", "confirmed", "closed", "fulfilled", "delivered"}:
        return "shipped"
    if status_closed:
        return "shipped"
    if key in {"cancelled", "canceled"}:
        return "cancelled"
    return "other"


def _stage_label(stage_key: str) -> str:
    mapping = {
        "created": "Created",
        "allocated": "Allocated",
        "picked": "Picked",
        "packed": "Packed",
        "shipped": "Shipped",
        "cancelled": "Cancelled",
        "other": "Other",
    }
    return mapping.get(stage_key, "Other")


def _extract_order_ref(row: Dict[str, Any]) -> str:
    return str(
        row.get("external_id")
        or row.get("order_number")
        or row.get("id")
        or "N/A"
    ).strip()


def _extract_created_at(row: Dict[str, Any]) -> Optional[datetime]:
    return _safe_parse_datetime(row.get("creation_date")) or _safe_parse_datetime(row.get("process_date"))


def _compute_age_hours(row: Dict[str, Any], now_utc: datetime) -> Optional[float]:
    created_at = _extract_created_at(row)
    if not created_at:
        return None

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    return max(0.0, (now_utc - created_at.astimezone(timezone.utc)).total_seconds() / 3600.0)


def _resolve_period(options: Dict[str, Any], fallback_input_text: str = "", default_days: int = 7) -> Tuple[str, str]:
    start = str(options.get("start_date") or options.get("date_from") or "").strip()
    end = str(options.get("end_date") or options.get("date_to") or "").strip()
    if start and end:
        return start, end

    period_input = str(options.get("period") or fallback_input_text or "").strip()
    if period_input:
        try:
            p_start, p_end = parse_period_input(period_input)
            return str(p_start), str(p_end)
        except Exception:
            pass

    now = datetime.now(timezone.utc).date()
    start_date = now - timedelta(days=max(1, default_days))
    return start_date.isoformat(), now.isoformat()


def _fetch_extensiv_orders(
    start_date: str,
    end_date: str,
    warehouses: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    supabase = get_supabase_client()
    account_id, _, filter_column = _resolve_scope()
    if not account_id:
        return []

    select_with_event = (
        "id,external_id,order_number,customer_name,facility_name,status,status_closed,"
        "status_fully_allocated,last_event_name,creation_date,process_date,tracking_number,"
        "total_weight,total_volume"
    )
    select_without_event = (
        "id,external_id,order_number,customer_name,facility_name,status,status_closed,"
        "status_fully_allocated,creation_date,process_date,tracking_number,total_weight,total_volume"
    )

    def run_query(select_clause: str) -> List[Dict[str, Any]]:
        query = (
            supabase.table("extensiv_orders")
            .select(select_clause)
            .eq(filter_column, account_id)
            .gte("creation_date", start_date)
            .lte("creation_date", end_date)
            .order("creation_date", desc=True)
            .order("id", desc=True)
        )
        if warehouses:
            query = query.in_("facility_name", warehouses)
        return _fetch_all_rows(query)

    try:
        return run_query(select_with_event)
    except Exception:
        rows = run_query(select_without_event)
        for row in rows:
            row["last_event_name"] = None
        return rows


def _filter_by_search(rows: List[Dict[str, Any]], search: str) -> List[Dict[str, Any]]:
    term = (search or "").strip().lower()
    if not term:
        return rows

    filtered: List[Dict[str, Any]] = []
    for row in rows:
        haystack = " ".join(
            [
                _extract_order_ref(row),
                str(row.get("customer_name") or ""),
                str(row.get("facility_name") or ""),
                str(row.get("tracking_number") or ""),
            ]
        ).lower()
        if term in haystack:
            filtered.append(row)
    return filtered


def _lifecycle_by_warehouse(
    rows: List[Dict[str, Any]],
    top_warehouses: Optional[int] = None,
) -> List[Dict[str, Any]]:
    summary: Dict[str, Dict[str, Any]] = {}

    for row in rows:
        warehouse = str(row.get("facility_name") or "Unassigned Warehouse").strip() or "Unassigned Warehouse"
        stage_key = _normalize_stage_key(row.get("last_event_name"), bool(row.get("status_closed")))

        if warehouse not in summary:
            summary[warehouse] = {
                "warehouse": warehouse,
                "total": 0,
                "created": 0,
                "allocated": 0,
                "picked": 0,
                "packed": 0,
                "shipped": 0,
                "other": 0,
            }

        summary[warehouse]["total"] += 1
        if stage_key in summary[warehouse]:
            summary[warehouse][stage_key] += 1
        else:
            summary[warehouse]["other"] += 1

    rows_sorted = sorted(summary.values(), key=lambda item: item["total"], reverse=True)
    if top_warehouses is None or top_warehouses <= 0:
        return rows_sorted

    if len(rows_sorted) <= top_warehouses:
        return rows_sorted

    top = rows_sorted[:top_warehouses]
    rest = rows_sorted[top_warehouses:]
    aggregated = {
        "warehouse": f"Other Warehouses ({len(rest)})",
        "total": 0,
        "created": 0,
        "allocated": 0,
        "picked": 0,
        "packed": 0,
        "shipped": 0,
        "other": 0,
    }
    for row in rest:
        aggregated["total"] += row["total"]
        for key in ("created", "allocated", "picked", "packed", "shipped", "other"):
            aggregated[key] += row[key]

    top.append(aggregated)
    return top


def _severity_label(age_hours: float, warning_hours: float, critical_hours: float) -> str:
    if age_hours >= critical_hours:
        return "critical"
    if age_hours >= warning_hours:
        return "warning"
    return "watch"


def _fetch_order_items(order_ids: List[int]) -> List[Dict[str, Any]]:
    if not order_ids:
        return []

    supabase = get_supabase_client()
    chunks: List[List[int]] = [order_ids[i:i + 300] for i in range(0, len(order_ids), 300)]
    all_items: List[Dict[str, Any]] = []

    for chunk in chunks:
        response = (
            supabase.table("extensiv_order_items")
            .select("order_id,sku,qty,unit_name,weight_imperial")
            .in_("order_id", chunk)
            .execute()
        )
        all_items.extend(response.data or [])

    return all_items


def get_pending_orders_alert(input_text: str = "") -> str:
    """
    Extensiv pending orders alert with warning/critical split.
    Accepts a JSON string or natural language period.
    """
    options = _parse_options(input_text)
    start_date, end_date = _resolve_period(options, input_text)
    warehouses = _parse_warehouses(options)
    warning_hours = _to_float(options.get("warning_hours"), DEFAULT_SLA_WARNING_HOURS)
    critical_hours = _to_float(options.get("critical_hours"), DEFAULT_SLA_CRITICAL_HOURS)
    limit = max(1, _to_int(options.get("limit"), 10))

    rows = _fetch_extensiv_orders(start_date, end_date, warehouses)
    now_utc = datetime.now(timezone.utc)

    pending: List[Dict[str, Any]] = []
    for row in rows:
        stage_key = _normalize_stage_key(row.get("last_event_name"), bool(row.get("status_closed")))
        if stage_key not in PENDING_STAGE_KEYS:
            continue

        age_hours = _compute_age_hours(row, now_utc)
        if age_hours is None:
            continue

        pending.append(
            {
                "order_ref": _extract_order_ref(row),
                "warehouse": str(row.get("facility_name") or "Unassigned Warehouse"),
                "stage": _stage_label(stage_key),
                "age_hours": age_hours,
                "severity": _severity_label(age_hours, warning_hours, critical_hours),
            }
        )

    if not pending:
        return (
            f"{SLA_DISCLAIMER}\n"
            f"No pending orders found between {start_date} and {end_date}."
        )

    pending.sort(key=lambda item: item["age_hours"], reverse=True)
    critical_count = sum(1 for item in pending if item["severity"] == "critical")
    warning_count = sum(1 for item in pending if item["severity"] == "warning")

    shown = min(limit, len(pending))
    lines = [
        SLA_DISCLAIMER,
        "Pending Orders Alert",
        f"Period: {start_date} to {end_date}",
        "",
        "Summary:",
        f"- Pending Orders: {len(pending)}",
        f"- Critical: {critical_count}",
        f"- Warning: {warning_count}",
        "",
        f"Top pending orders (showing {shown}):",
    ]

    for index, item in enumerate(pending[:limit], start=1):
        lines.extend(
            [
                f"{index}. Order {item['order_ref']}",
                f"   Warehouse: {item['warehouse']}",
                f"   Stage: {item['stage']}",
                f"   Age: {int(item['age_hours'])}h",
                f"   Severity: {item['severity']}",
                "",
            ]
        )

    return "\n".join(lines).strip()


def list_pending_orders_by_filters(input_text: str = "") -> str:
    """
    Extensiv pending orders list with filters (search/status/warehouse/date/page).
    Accepts JSON string.
    """
    options = _parse_options(input_text)
    start_date, end_date = _resolve_period(options, input_text)
    warehouses = _parse_warehouses(options)
    statuses = set(_parse_statuses(options))
    search = str(options.get("search") or options.get("q") or "").strip()
    page = max(1, _to_int(options.get("page"), 1))
    page_size = max(1, min(200, _to_int(options.get("page_size"), 20)))

    rows = _fetch_extensiv_orders(start_date, end_date, warehouses)
    now_utc = datetime.now(timezone.utc)

    filtered: List[Dict[str, Any]] = []
    for row in rows:
        stage_key = _normalize_stage_key(row.get("last_event_name"), bool(row.get("status_closed")))
        if stage_key not in PENDING_STAGE_KEYS:
            continue
        if statuses and stage_key not in statuses:
            continue

        age_hours = _compute_age_hours(row, now_utc)
        filtered.append(
            {
                "order_ref": _extract_order_ref(row),
                "marketplace_id": str(row.get("order_number") or row.get("external_id") or "N/A"),
                "client": str(row.get("customer_name") or "N/A"),
                "warehouse": str(row.get("facility_name") or "Unassigned Warehouse"),
                "stage": _stage_label(stage_key),
                "age_hours": int(age_hours) if age_hours is not None else None,
                "created_at": str(row.get("creation_date") or row.get("process_date") or "N/A"),
            }
        )

    if search:
        search_rows = []
        for row in filtered:
            haystack = " ".join(
                [
                    row["order_ref"],
                    row["marketplace_id"],
                    row["client"],
                    row["warehouse"],
                ]
            ).lower()
            if search.lower() in haystack:
                search_rows.append(row)
        filtered = search_rows

    total = len(filtered)
    if total == 0:
        return (
            f"{SLA_DISCLAIMER}\n"
            f"No pending orders matched the filters between {start_date} and {end_date}."
        )

    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_rows = filtered[start_idx:end_idx]
    total_pages = max(1, (total + page_size - 1) // page_size)

    lines = [
        SLA_DISCLAIMER,
        "Pending Orders",
        f"Period: {start_date} to {end_date}",
        f"Page: {page}/{total_pages}",
        f"Total matching rows: {total}",
        "",
    ]
    for index, row in enumerate(page_rows, start=start_idx + 1):
        lines.extend(
            [
                f"{index}. Order {row['order_ref']}",
                f"   Marketplace ID: {row['marketplace_id']}",
                f"   Client: {row['client']}",
                f"   Warehouse: {row['warehouse']}",
                f"   Stage: {row['stage']}",
                f"   Created At: {row['created_at']}",
                f"   Age: {row['age_hours']}h",
                "",
            ]
        )

    return "\n".join(lines).strip()


def summarize_order_lifecycle_by_warehouse(input_text: str = "") -> str:
    """
    Extensiv lifecycle summary by warehouse (Created/Allocated/Picked/Packed/Shipped/Other).
    Accepts JSON string or natural language period.
    """
    options = _parse_options(input_text)
    start_date, end_date = _resolve_period(options, input_text)
    warehouses = _parse_warehouses(options)
    top_warehouses: Optional[int] = None
    top_warehouses_raw = options.get("top_warehouses")
    if top_warehouses_raw not in (None, "", "all", "ALL"):
        top_warehouses = max(1, _to_int(top_warehouses_raw, 0))

    rows = _fetch_extensiv_orders(start_date, end_date, warehouses)
    if not rows:
        return f"No Extensiv orders found between {start_date} and {end_date}."

    lifecycle = _lifecycle_by_warehouse(rows, top_warehouses=top_warehouses)

    total_orders = len(rows)
    totals = {
        "created": sum(item["created"] for item in lifecycle),
        "allocated": sum(item["allocated"] for item in lifecycle),
        "picked": sum(item["picked"] for item in lifecycle),
        "packed": sum(item["packed"] for item in lifecycle),
        "shipped": sum(item["shipped"] for item in lifecycle),
        "other": sum(item["other"] for item in lifecycle),
    }

    lines = [
        "Order Lifecycle by Warehouse",
        f"Period: {start_date} to {end_date}",
        "",
        "Summary:",
        f"- Total Orders: {total_orders}",
        "- Totals by stage:",
        f"  Created: {totals['created']}",
        f"  Allocated: {totals['allocated']}",
        f"  Picked: {totals['picked']}",
        f"  Packed: {totals['packed']}",
        f"  Shipped: {totals['shipped']}",
        f"  Other: {totals['other']}",
        "",
        f"Warehouses ({len(lifecycle)}):",
    ]

    for index, item in enumerate(lifecycle, start=1):
        lines.extend(
            [
                f"{index}. {item['warehouse']}",
                f"   Total: {item['total']}",
                f"   Created: {item['created']}",
                f"   Allocated: {item['allocated']}",
                f"   Picked: {item['picked']}",
                f"   Packed: {item['packed']}",
                f"   Shipped: {item['shipped']}",
                f"   Other: {item['other']}",
                "",
            ]
        )

    return "\n".join(lines).strip()


def get_most_pending_warehouse(input_text: str = "") -> str:
    """
    Returns the warehouse with the largest pending backlog for the selected period.
    """
    options = _parse_options(input_text)
    start_date, end_date = _resolve_period(options, input_text)
    warehouses = _parse_warehouses(options)

    rows = _fetch_extensiv_orders(start_date, end_date, warehouses)
    if not rows:
        return f"No Extensiv orders found between {start_date} and {end_date}."

    lifecycle = _lifecycle_by_warehouse(rows)
    ranked = []
    for item in lifecycle:
        pending = item["created"] + item["allocated"] + item["picked"] + item["packed"]
        ranked.append({"warehouse": item["warehouse"], "pending": pending, "total": item["total"]})

    ranked.sort(key=lambda row: row["pending"], reverse=True)
    top = ranked[0] if ranked else None
    if not top:
        return f"No pending orders found between {start_date} and {end_date}."

    return (
        f"Most pending warehouse ({start_date} to {end_date}):\n"
        f"- Warehouse: {top['warehouse']}\n"
        f"- Pending Orders: {top['pending']}\n"
        f"- Total Orders: {top['total']}"
    )


def get_order_status_breakdown(input_text: str = "") -> str:
    """
    Returns status chips breakdown for Extensiv orders in the selected period.
    """
    options = _parse_options(input_text)
    start_date, end_date = _resolve_period(options, input_text)
    warehouses = _parse_warehouses(options)

    rows = _fetch_extensiv_orders(start_date, end_date, warehouses)
    if not rows:
        return f"No Extensiv orders found between {start_date} and {end_date}."

    counts = {
        "created": 0,
        "allocated": 0,
        "picked": 0,
        "packed": 0,
        "shipped": 0,
        "cancelled": 0,
        "other": 0,
    }

    for row in rows:
        key = _normalize_stage_key(row.get("last_event_name"), bool(row.get("status_closed")))
        if key not in counts:
            key = "other"
        counts[key] += 1

    return (
        f"Order status breakdown ({start_date} to {end_date}):\n"
        f"- Created: {counts['created']}\n"
        f"- Allocated: {counts['allocated']}\n"
        f"- Picked: {counts['picked']}\n"
        f"- Packed: {counts['packed']}\n"
        f"- Shipped: {counts['shipped']}\n"
        f"- Cancelled: {counts['cancelled']}\n"
        f"- Other: {counts['other']}"
    )


def _find_extensiv_order(order_id: str) -> Optional[Dict[str, Any]]:
    supabase = get_supabase_client()
    account_id, _, filter_column = _resolve_scope()
    identifier = (order_id or "").strip()

    if not identifier or not account_id:
        return None

    candidates: List[Tuple[str, Any]] = []
    if identifier.isdigit():
        candidates.append(("id", int(identifier)))

    candidates.extend(
        [
            ("external_id", identifier),
            ("order_number", identifier),
        ]
    )

    select_with_event = (
        "id,external_id,order_number,customer_name,facility_name,status,status_closed,"
        "status_fully_allocated,last_event_name,creation_date,process_date,tracking_number,"
        "total_weight,total_volume"
    )
    select_without_event = (
        "id,external_id,order_number,customer_name,facility_name,status,status_closed,"
        "status_fully_allocated,creation_date,process_date,tracking_number,total_weight,total_volume"
    )

    for field, value in candidates:
        try:
            response = (
                supabase.table("extensiv_orders")
                .select(select_with_event)
                .eq(field, value)
                .eq(filter_column, account_id)
                .maybe_single()
                .execute()
            )
        except Exception:
            response = (
                supabase.table("extensiv_orders")
                .select(select_without_event)
                .eq(field, value)
                .eq(filter_column, account_id)
                .maybe_single()
                .execute()
            )

        if response and response.data:
            data = response.data
            data.setdefault("last_event_name", None)
            return data

    return None


def get_order_progress_by_id(order_id: str) -> str:
    """
    Returns current progress stage and timeline fields for a specific Extensiv order.
    """
    try:
        order = _find_extensiv_order(order_id)
        if not order:
            return f"No Extensiv order found with ID/reference `{order_id}`."

        stage_key = _normalize_stage_key(order.get("last_event_name"), bool(order.get("status_closed")))
        stage_label = _stage_label(stage_key)

        steps = ["Created", "Allocated", "Picked", "Packed", "Shipped"]
        current_index = steps.index(stage_label) if stage_label in steps else -1
        progress_line = " > ".join(
            [
                f"[x] {step}" if idx <= current_index and current_index >= 0 else f"[ ] {step}"
                for idx, step in enumerate(steps)
            ]
        )

        timeline_line = "No detailed timeline events available."
        try:
            supabase = get_supabase_client()
            timing = (
                supabase.table("ai_fulfillment_timing_extensiv")
                .select(
                    "creation_date,process_date,pick_started,pick_done,pick_ticket_printed,"
                    "fully_allocated,fulfillment_time,order_number"
                )
                .eq("order_number", order.get("order_number"))
                .limit(1)
                .maybe_single()
                .execute()
            )
            if timing and timing.data:
                t = timing.data
                timeline_line = (
                    f"Created: {t.get('creation_date') or 'N/A'} | "
                    f"Allocated: {t.get('fully_allocated') or 'N/A'} | "
                    f"Pick Start: {t.get('pick_started') or 'N/A'} | "
                    f"Pick Done: {t.get('pick_done') or 'N/A'} | "
                    f"Processed: {t.get('process_date') or 'N/A'}"
                )
        except Exception:
            pass

        return (
            f"Order progress for `{_extract_order_ref(order)}`:\n"
            f"- Current Stage: {stage_label}\n"
            f"- Progress: {progress_line}\n"
            f"- Timeline: {timeline_line}"
        )
    except Exception as e:
        return f"Error while retrieving order progress for `{order_id}`: {str(e)}"


def _parse_buckets(options: Dict[str, Any]) -> List[Tuple[float, Optional[float], str]]:
    raw = options.get("buckets")
    parsed: List[str] = []

    if isinstance(raw, list):
        parsed = [str(item).strip() for item in raw if str(item).strip()]
    elif isinstance(raw, str):
        parsed = [item.strip() for item in raw.split(",") if item.strip()]

    if not parsed:
        parsed = ["0-12", "12-24", "24-48", "48+"]

    buckets: List[Tuple[float, Optional[float], str]] = []
    for item in parsed:
        if item.endswith("+"):
            start = _to_float(item[:-1], 0)
            buckets.append((start, None, item))
            continue
        if "-" in item:
            left, right = item.split("-", 1)
            start = _to_float(left, 0)
            end = _to_float(right, start)
            buckets.append((start, end, item))

    if not buckets:
        buckets = [(0, 12, "0-12"), (12, 24, "12-24"), (24, 48, "24-48"), (48, None, "48+")]

    return buckets


def get_pending_aging_distribution(input_text: str = "") -> str:
    """
    Returns pending order aging distribution by configurable hour buckets.
    """
    options = _parse_options(input_text)
    start_date, end_date = _resolve_period(options, input_text)
    warehouses = _parse_warehouses(options)
    buckets = _parse_buckets(options)

    rows = _fetch_extensiv_orders(start_date, end_date, warehouses)
    now_utc = datetime.now(timezone.utc)

    values: List[float] = []
    for row in rows:
        stage_key = _normalize_stage_key(row.get("last_event_name"), bool(row.get("status_closed")))
        if stage_key not in PENDING_STAGE_KEYS:
            continue
        age = _compute_age_hours(row, now_utc)
        if age is not None:
            values.append(age)

    if not values:
        return (
            f"{SLA_DISCLAIMER}\n"
            f"No pending orders found between {start_date} and {end_date}."
        )

    counts = {label: 0 for _, _, label in buckets}
    for age in values:
        for start, end, label in buckets:
            if end is None and age >= start:
                counts[label] += 1
                break
            if end is not None and start <= age < end:
                counts[label] += 1
                break

    lines = [
        SLA_DISCLAIMER,
        f"Pending aging distribution ({start_date} to {end_date}):",
    ]
    for _, _, label in buckets:
        lines.append(f"- {label}h: {counts[label]}")

    return "\n".join(lines)


def list_orders_at_risk_sla(input_text: str = "") -> str:
    """
    Lists pending orders at risk by SLA thresholds.
    """
    options = _parse_options(input_text)
    start_date, end_date = _resolve_period(options, input_text)
    warehouses = _parse_warehouses(options)
    warning_hours = _to_float(options.get("warning_hours"), DEFAULT_SLA_WARNING_HOURS)
    critical_hours = _to_float(options.get("critical_hours"), DEFAULT_SLA_CRITICAL_HOURS)
    limit = max(1, _to_int(options.get("limit"), 20))

    rows = _fetch_extensiv_orders(start_date, end_date, warehouses)
    now_utc = datetime.now(timezone.utc)

    at_risk: List[Dict[str, Any]] = []
    for row in rows:
        stage_key = _normalize_stage_key(row.get("last_event_name"), bool(row.get("status_closed")))
        if stage_key not in PENDING_STAGE_KEYS:
            continue

        age = _compute_age_hours(row, now_utc)
        if age is None or age < warning_hours:
            continue

        severity = _severity_label(age, warning_hours, critical_hours)
        time_to_critical = max(0.0, critical_hours - age)
        at_risk.append(
            {
                "order_ref": _extract_order_ref(row),
                "warehouse": str(row.get("facility_name") or "Unassigned Warehouse"),
                "stage": _stage_label(stage_key),
                "age_hours": age,
                "severity": severity,
                "time_to_critical": time_to_critical,
            }
        )

    if not at_risk:
        return (
            f"{SLA_DISCLAIMER}\n"
            f"No orders at SLA risk in the selected period ({start_date} to {end_date})."
        )

    at_risk.sort(key=lambda item: item["age_hours"], reverse=True)
    shown = min(limit, len(at_risk))
    lines = [
        SLA_DISCLAIMER,
        "Orders at SLA Risk",
        f"Period: {start_date} to {end_date}",
        f"Total at risk: {len(at_risk)}",
        f"Showing: {shown}",
        "",
    ]
    for index, row in enumerate(at_risk[:limit], start=1):
        lines.extend(
            [
                f"{index}. Order {row['order_ref']}",
                f"   Warehouse: {row['warehouse']}",
                f"   Stage: {row['stage']}",
                f"   Age: {int(row['age_hours'])}h",
                f"   Severity: {row['severity']}",
                f"   Time to critical: {int(row['time_to_critical'])}h",
                "",
            ]
        )

    return "\n".join(lines).strip()


def get_order_details_extensiv(order_id: str) -> str:
    """
    Returns full Extensiv order details including item list.
    """
    try:
        order = _find_extensiv_order(order_id)
        if not order:
            return f"No Extensiv order found with ID/reference `{order_id}`."

        supabase = get_supabase_client()
        items_response = (
            supabase.table("extensiv_order_items")
            .select("sku,qty,unit_name,weight_imperial")
            .eq("order_id", order.get("id"))
            .execute()
        )
        items = items_response.data or []
        units_total = sum(float(item.get("qty") or 0) for item in items)

        lines = [
            f"Extensiv order details for `{_extract_order_ref(order)}`:",
            f"- Internal ID: {order.get('id', 'N/A')}",
            f"- Order Number: {order.get('order_number', 'N/A')}",
            f"- Customer: {order.get('customer_name', 'N/A')}",
            f"- Warehouse: {order.get('facility_name', 'N/A')}",
            f"- Created At: {order.get('creation_date', 'N/A')}",
            f"- Process Date: {order.get('process_date', 'N/A')}",
            f"- Tracking Number: {order.get('tracking_number', 'N/A')}",
            f"- Total Weight: {order.get('total_weight', 0) or 0}",
            f"- Total Volume: {order.get('total_volume', 0) or 0}",
            f"- Item Count: {len(items)}",
            f"- Units Total: {units_total}",
        ]

        if items:
            lines.append("")
            lines.append("Items:")
            for item in items[:100]:
                lines.append(
                    f"- SKU: {item.get('sku') or 'N/A'} | Qty: {item.get('qty') or 0} | "
                    f"Unit: {item.get('unit_name') or '-'} | "
                    f"Weight: {item.get('weight_imperial') if item.get('weight_imperial') is not None else 'N/A'}"
                )

        return "\n".join(lines)
    except Exception as e:
        return f"Error while fetching Extensiv order details for `{order_id}`: {str(e)}"


def summarize_orders_volume_units_by_warehouse(input_text: str = "") -> str:
    """
    Summarizes order count, units, weight and volume by warehouse for Extensiv.
    """
    options = _parse_options(input_text)
    start_date, end_date = _resolve_period(options, input_text)
    warehouses = _parse_warehouses(options)

    rows = _fetch_extensiv_orders(start_date, end_date, warehouses)
    if not rows:
        return f"No Extensiv orders found between {start_date} and {end_date}."

    order_ids = [int(row["id"]) for row in rows if str(row.get("id") or "").isdigit()]
    items = _fetch_order_items(order_ids)

    units_by_order: Dict[int, float] = {}
    for item in items:
        oid = item.get("order_id")
        if oid is None:
            continue
        try:
            oid_int = int(oid)
        except Exception:
            continue
        units_by_order[oid_int] = units_by_order.get(oid_int, 0.0) + float(item.get("qty") or 0)

    per_wh: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        warehouse = str(row.get("facility_name") or "Unassigned Warehouse")
        if warehouse not in per_wh:
            per_wh[warehouse] = {
                "orders": 0,
                "units": 0.0,
                "weight": 0.0,
                "volume": 0.0,
            }

        wh = per_wh[warehouse]
        wh["orders"] += 1
        order_id = row.get("id")
        try:
            order_id_int = int(order_id)
        except Exception:
            order_id_int = None

        if order_id_int is not None:
            wh["units"] += units_by_order.get(order_id_int, 0.0)

        wh["weight"] += float(row.get("total_weight") or 0)
        wh["volume"] += float(row.get("total_volume") or 0)

    sorted_rows = sorted(per_wh.items(), key=lambda kv: kv[1]["orders"], reverse=True)
    lines = [
        "Orders Volume and Units by Warehouse",
        f"Period: {start_date} to {end_date}",
        "",
    ]
    for index, (warehouse, data) in enumerate(sorted_rows, start=1):
        lines.extend(
            [
                f"{index}. {warehouse}",
                f"   Orders: {data['orders']}",
                f"   Units: {data['units']:.0f}",
                f"   Weight: {data['weight']:.2f}",
                f"   Volume: {data['volume']:.2f}",
                "",
            ]
        )

    return "\n".join(lines).strip()


def get_extensiv_order_status_by_id(order_id: str) -> str:
    """
    Extensiv-specific order status lookup by internal ID, external_id, or order_number.
    """
    try:
        order = _find_extensiv_order(order_id)
        if not order:
            return f"No Extensiv order found with ID/reference `{order_id}`."

        stage_key = _normalize_stage_key(order.get("last_event_name"), bool(order.get("status_closed")))
        status_label = _stage_label(stage_key)
        return (
            f"- Internal ID: {order.get('id', 'N/A')}\n"
            f"- External ID: {order.get('external_id', 'N/A')}\n"
            f"- Order Number: {order.get('order_number', 'N/A')}\n"
            f"- Status: {status_label}\n"
            f"- Last Event: {order.get('last_event_name') or 'N/A'}\n"
            f"- Created At: {order.get('creation_date', 'N/A')}\n"
            f"- Process Date: {order.get('process_date', 'N/A')}\n"
            f"- Customer: {order.get('customer_name', 'N/A')}\n"
            f"- Facility: {order.get('facility_name', 'N/A')}"
        )
    except Exception as e:
        return f"Error while fetching Extensiv order `{order_id}`: {str(e)}"


def get_extensiv_shipping_details_by_order_id(order_id: str) -> str:
    """
    Extensiv-specific shipping details lookup by order ID/reference.
    """
    try:
        order = _find_extensiv_order(order_id)
        if not order:
            return f"No Extensiv shipping data found for order `{order_id}`."

        stage_key = _normalize_stage_key(order.get("last_event_name"), bool(order.get("status_closed")))
        return (
            f"Shipping details for order `{order_id}`:\n"
            f"- Status: {_stage_label(stage_key)}\n"
            f"- Tracking Number: {order.get('tracking_number') or 'N/A'}\n"
            f"- Facility: {order.get('facility_name', 'N/A')}\n"
            f"- Process Date: {order.get('process_date', 'N/A')}\n"
            f"- Created At: {order.get('creation_date', 'N/A')}"
        )
    except Exception as e:
        return f"Error while fetching Extensiv shipping info for `{order_id}`: {str(e)}"


def list_extensiv_order_products_by_id(order_id: str) -> str:
    """
    Extensiv-specific item list by order ID/reference.
    """
    try:
        order = _find_extensiv_order(order_id)
        if not order:
            return f"No Extensiv order found with ID/reference `{order_id}`."

        supabase = get_supabase_client()
        response = (
            supabase.table("extensiv_order_items")
            .select("sku,qty,unit_name,weight_imperial")
            .eq("order_id", order.get("id"))
            .execute()
        )
        items = response.data or []
        if not items:
            return f"No items found for Extensiv order `{order_id}`."

        lines = [
            f"Products in Extensiv order `{order.get('order_number') or order.get('external_id') or order.get('id')}`:",
        ]
        for item in items[:100]:
            sku = item.get("sku") or "N/A"
            qty = item.get("qty") or 0
            unit = item.get("unit_name") or "-"
            weight = item.get("weight_imperial")
            weight_label = f"{weight} lb" if weight is not None else "N/A"
            lines.append(f"- SKU: {sku} | Qty: {qty} | Unit: {unit} | Weight: {weight_label}")

        return "\n".join(lines)
    except Exception as e:
        return f"Error while listing Extensiv products for order `{order_id}`: {str(e)}"


def get_extensiv_inventory_by_sku(sku: str) -> str:
    """
    Extensiv-specific inventory lookup by SKU.
    """
    try:
        normalized_sku = (sku or "").strip().upper()
        if not normalized_sku:
            return "Please provide a valid SKU."

        supabase = get_supabase_client()
        account_id, user_type, _ = _resolve_scope()
        if not account_id:
            return "No account context available for this request."
        filter_column = "channel_account_id" if user_type == "client" else "account_id"

        response = (
            supabase.table("extensiv_inventory")
            .select("sku,quantity_available,quantity_on_hand,last_updated_at")
            .eq("sku", normalized_sku)
            .eq(filter_column, account_id)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return f"No Extensiv inventory found for SKU `{normalized_sku}`."

        qty_available = sum(float(row.get("quantity_available") or 0) for row in rows)
        qty_on_hand = sum(float(row.get("quantity_on_hand") or 0) for row in rows)
        last_updated = max((row.get("last_updated_at") or "" for row in rows), default="N/A")

        return (
            f"SKU `{normalized_sku}` (Extensiv):\n"
            f"- Quantity Available: {qty_available}\n"
            f"- Quantity On Hand: {qty_on_hand}\n"
            f"- Last Updated: {last_updated}\n"
            f"- Records Aggregated: {len(rows)}"
        )
    except Exception as e:
        return f"Error retrieving Extensiv inventory for SKU `{sku}`: {str(e)}"


def summarize_extensiv_orders_by_period(input_text: str) -> str:
    """
    Extensiv-specific order summary by period.
    Example: 'last 30 days', 'this month', 'May 2025'.
    """
    options = _parse_options(input_text)
    start_date, end_date = _resolve_period(options, input_text)
    warehouses = _parse_warehouses(options)

    rows = _fetch_extensiv_orders(start_date, end_date, warehouses)
    if not rows:
        return f"No Extensiv orders found between {start_date} and {end_date}."

    total_orders = len(rows)
    stage_counts = {
        "created": 0,
        "allocated": 0,
        "picked": 0,
        "packed": 0,
        "shipped": 0,
        "other": 0,
    }
    total_weight = 0.0
    total_volume = 0.0

    for row in rows:
        stage_key = _normalize_stage_key(row.get("last_event_name"), bool(row.get("status_closed")))
        if stage_key not in stage_counts:
            stage_key = "other"
        stage_counts[stage_key] += 1
        total_weight += float(row.get("total_weight") or 0)
        total_volume += float(row.get("total_volume") or 0)

    return (
        f"Extensiv Orders Summary ({start_date} to {end_date}):\n"
        f"- Total Orders: {total_orders}\n"
        f"- Created: {stage_counts['created']}\n"
        f"- Allocated: {stage_counts['allocated']}\n"
        f"- Picked: {stage_counts['picked']}\n"
        f"- Packed: {stage_counts['packed']}\n"
        f"- Shipped: {stage_counts['shipped']}\n"
        f"- Other: {stage_counts['other']}\n"
        f"- Total Weight: {total_weight:.2f}\n"
        f"- Total Volume: {total_volume:.2f}"
    )
