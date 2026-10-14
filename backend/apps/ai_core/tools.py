"""
The assistant's general-purpose tools: read anything and propose any
action in the catalog (apps.access.catalog), as the user who's asking.

There is deliberately not one tool per action. With ~35 resources and ~130
actions that would be a tool list too long to choose from well and one that
has to be hand-extended for every new endpoint. Instead the model gets a
compact index of what exists (in its system prompt), can look up the exact
fields of anything (`describe_resource`), and then uses five generic tools:

- `query_records`, `get_record` -- read, through the resource's own API view;
- `summarize_records` -- group and total records *in code*, for tables and
  charts whose numbers are computed, never typed out by the model;
- `propose_action` -- any create/update/delete/transition, as a proposal a
  person must approve (PendingApproval) -- never executed from here.

Every one of them goes through apps.access.dispatch, i.e. through the same
API view a screen would call, as the same user. So the assistant can do
exactly what that user can do, validated the same way and written to the
same audit trail -- and nothing more (technical.md §8.5).

Each tool returns `(payload, blocks)`: `payload` is what the model reads
back; `blocks` are what the person sees rendered with the reply. Block
shapes (mirrored by frontend/src/ai-panel/blocks/):

    {"type": "table",  "title", "resource", "columns": [key], "rows": [{...}], "total"}
    {"type": "chart",  "title", "chart": "bar"|"line"|"hbar", "format": "money"|"number",
                       "label_kind": "month"|"date"|"text", "series": [{"name", "points": [{"label","value"}]}]}
    {"type": "record", "resource", "id", "title", "fields": {...}}
    {"type": "proposal", "approval_id"}       (hydrated with live status when served)
"""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

from rest_framework import serializers as drf

from apps.access import catalog, dispatch
from apps.access.permissions import allowed

from .models import PendingApproval

MAX_ROWS_SCANNED = 2000  # per query -- reported to the model when it truncates
MAX_ROWS_RETURNED = 50
DEFAULT_ROWS_RETURNED = 20
MAX_COLUMNS = 8
MAX_GROUPS = 24

# Names that mark a decimal as money rather than a quantity.
_MONEY_HINTS = ("total", "amount", "balance", "price", "salary", "cost", "premium", "tax", "debit", "credit", "cash", "paid", "due", "value")


@dataclass
class Context:
    user: object
    tenant: object
    conversation: Optional[object] = None
    entity_id: Optional[int] = None


class ToolError(Exception):
    """A problem the model should read and correct (an unknown field, a
    missing permission) -- returned to it as the tool result, never raised
    to the user."""


# ---------------------------------------------------------------------------
# What the user can reach
# ---------------------------------------------------------------------------
def visible_resources(ctx: Context) -> list[catalog.Resource]:
    """Resources this user holds at least one action on, in active plugins.
    The administration area is left out even for admins: managing who can
    do what is deliberately a by-hand task, not something to talk an
    assistant into."""
    return [
        resource
        for resource in catalog.grantable_resources()
        if any(allowed(ctx.user, ctx.tenant, resource.code(op)) for op in resource.operations)
    ]


def catalog_index(ctx: Context) -> str:
    """The one-line-per-resource index that goes in the system prompt."""
    lines = []
    for resource in visible_resources(ctx):
        operations = [op for op in resource.operations if allowed(ctx.user, ctx.tenant, resource.code(op))]
        lines.append(f"- {resource.key} [{', '.join(operations)}]: {resource.description}")
    return "\n".join(lines) or "(This user has no access to any records.)"


def _resource(ctx: Context, key: str, operation: str) -> catalog.Resource:
    resource = catalog.get_resource(key)
    if resource is None or resource.admin_only:
        known = ", ".join(r.key for r in visible_resources(ctx))
        raise ToolError(f"There is no resource '{key}'. Resources: {known}")
    if operation not in resource.operations:
        raise ToolError(f"'{key}' has no '{operation}' operation. It has: {', '.join(resource.operations)}")
    if not allowed(ctx.user, ctx.tenant, resource.code(operation)):
        raise ToolError(f"The user does not have permission for {resource.code(operation)}. Tell them so; do not look for another way to do it.")
    return resource


# ---------------------------------------------------------------------------
# describe_resource
# ---------------------------------------------------------------------------
def _resource_for_model(model) -> Optional[str]:
    for resource in catalog.all_resources():
        queryset = getattr(resource.view, "queryset", None)
        if queryset is not None and queryset.model is model:
            return resource.key
    return None


def _field_spec(field, depth: int = 0) -> dict:
    spec: dict = {}
    if isinstance(field, drf.ListSerializer):
        spec["type"] = "list of objects"
        if depth < 2:
            spec["fields"] = _fields_of(field.child, depth + 1)
    elif isinstance(field, drf.BaseSerializer):
        spec["type"] = "object"
        if depth < 2:
            spec["fields"] = _fields_of(field, depth + 1)
    elif isinstance(field, drf.ManyRelatedField):
        target = _resource_for_model(field.child_relation.queryset.model) if getattr(field.child_relation, "queryset", None) is not None else None
        spec["type"] = f"list of ids of {target}" if target else "list of ids"
    elif isinstance(field, drf.RelatedField):
        queryset = getattr(field, "queryset", None)
        target = _resource_for_model(queryset.model) if queryset is not None else None
        spec["type"] = f"id of {target}" if target else "id"
    elif isinstance(field, drf.ChoiceField):
        spec["type"] = "choice"
        spec["choices"] = list(field.choices)
    elif isinstance(field, drf.BooleanField):
        spec["type"] = "boolean"
    elif isinstance(field, drf.IntegerField):
        spec["type"] = "integer"
    elif isinstance(field, (drf.DecimalField, drf.FloatField)):
        spec["type"] = "decimal (as a string, e.g. \"1250.00\")"
    elif isinstance(field, drf.DateTimeField):
        spec["type"] = "datetime (ISO 8601)"
    elif isinstance(field, drf.DateField):
        spec["type"] = "date (YYYY-MM-DD)"
    elif isinstance(field, (drf.ListField, drf.DictField, drf.JSONField)):
        spec["type"] = "json"
    else:
        spec["type"] = "string"
    if field.read_only:
        spec["read_only"] = True
    elif field.required:
        spec["required"] = True
    if getattr(field, "help_text", None):
        spec["help"] = str(field.help_text)
    return spec


def _fields_of(serializer, depth: int = 0) -> dict:
    return {name: _field_spec(field, depth) for name, field in serializer.fields.items()}


def _serializer_class(resource: catalog.Resource):
    return getattr(resource.view, "serializer_class", None)


def describe_resource(ctx: Context, resource: str) -> tuple[dict, list]:
    res = next((r for r in visible_resources(ctx) if r.key == resource), None)
    if res is None:
        raise ToolError(f"There is no resource '{resource}' the user can access. Resources: {', '.join(r.key for r in visible_resources(ctx))}")
    serializer_class = _serializer_class(res)
    operations = {}
    for name, operation in res.operations.items():
        if not allowed(ctx.user, ctx.tenant, res.code(name)):
            continue
        entry: dict = {"kind": operation.kind, "needs_id": operation.detail}
        if name in (catalog.CREATE, catalog.UPDATE):
            entry["data"] = "this resource's writable fields (below)" + ("; only the fields being changed" if name == catalog.UPDATE else "")
        elif name in res.inputs:
            hint = res.inputs[name]
            entry["data"] = _fields_of(hint()) if isinstance(hint, type) else hint
        elif operation.kind == catalog.WRITE and name != catalog.DELETE:
            entry["data"] = "none"
        operations[name] = entry
    return (
        {
            "resource": res.key,
            "description": res.description,
            "operations": operations,
            "fields": _fields_of(serializer_class()) if serializer_class else "This is a report: query it to see its columns.",
            "filtering": "query_records/summarize_records filter on any field shown here via `where`.",
        },
        [],
    )


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------
def _fetch_all(ctx: Context, res: catalog.Resource) -> tuple[list[dict], bool]:
    """Every row of the resource the user may see, through its list view.
    Paginated views are walked page by page up to MAX_ROWS_SCANNED."""
    rows: list[dict] = []
    params = {"entity": ctx.entity_id} if ctx.entity_id else {}
    page = 1
    while True:
        result = dispatch.perform(ctx.user, ctx.tenant, res.key, catalog.VIEW, params={**params, "page": page})
        if not result.ok:
            raise ToolError(f"Could not read {res.key}: {result.error}")
        data = result.data
        if isinstance(data, dict) and "results" in data:
            rows.extend(data["results"])
            if not data.get("next") or len(rows) >= MAX_ROWS_SCANNED:
                return rows[:MAX_ROWS_SCANNED], bool(data.get("next"))
            page += 1
        else:
            rows = data if isinstance(data, list) else [data]
            return rows[:MAX_ROWS_SCANNED], len(rows) > MAX_ROWS_SCANNED


def _value(row: dict, path: str):
    """`party.name` style paths into a serialized row."""
    current = row
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _number(value) -> Optional[Decimal]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _compare(left, right) -> Optional[int]:
    """-1/0/1, numerically when both sides are numbers, else as text (which
    orders ISO dates correctly)."""
    a, b = _number(left), _number(right)
    if a is None or b is None:
        if left is None or right is None:
            return None
        a, b = str(left).lower(), str(right).lower()
    return (a > b) - (a < b)


_OPERATORS = {
    "eq": lambda v, t: _compare(v, t) == 0 if v is not None else t is None,
    "ne": lambda v, t: not (_compare(v, t) == 0 if v is not None else t is None),
    "gt": lambda v, t: _compare(v, t) == 1,
    "gte": lambda v, t: _compare(v, t) in (0, 1),
    "lt": lambda v, t: _compare(v, t) == -1,
    "lte": lambda v, t: _compare(v, t) in (0, -1),
    "contains": lambda v, t: v is not None and str(t).lower() in str(v).lower(),
    "in": lambda v, t: any(_compare(v, option) == 0 for option in (t if isinstance(t, list) else [t])),
    "is_null": lambda v, t: (v is None or v == "") == bool(t),
}


def _check_fields(rows: list[dict], paths: list[str], res: catalog.Resource):
    """A mistyped field name must be an error the model can fix -- not a
    filter that silently matches nothing and reads as "there are none"."""
    if not rows:
        return
    known = set(rows[0])
    for path in paths:
        if path.split(".")[0] not in known:
            raise ToolError(f"'{res.key}' has no field '{path}'. Its fields are: {', '.join(sorted(known))}")


def _filter(rows: list[dict], where: Optional[list], res: catalog.Resource) -> list[dict]:
    conditions = where or []
    for condition in conditions:
        if condition.get("op") not in _OPERATORS:
            raise ToolError(f"Unknown operator '{condition.get('op')}'. Use one of: {', '.join(_OPERATORS)}")
    _check_fields(rows, [c["field"] for c in conditions], res)
    return [row for row in rows if all(_OPERATORS[c["op"]](_value(row, c["field"]), c.get("value")) for c in conditions)]


def _scalar_columns(rows: list[dict]) -> list[str]:
    if not rows:
        return []
    return [key for key, value in rows[0].items() if not isinstance(value, (dict, list))]


def query_records(ctx: Context, resource: str, where=None, order_by=None, limit=None, columns=None, title=None) -> tuple[dict, list]:
    res = _resource(ctx, resource, catalog.VIEW)
    rows, truncated = _fetch_all(ctx, res)
    matched = _filter(rows, where, res)

    if order_by:
        descending, field = order_by.startswith("-"), order_by.lstrip("-")
        _check_fields(matched, [field], res)
        present = [row for row in matched if _value(row, field) is not None]
        missing = [row for row in matched if _value(row, field) is None]
        present.sort(key=lambda row: (_number(_value(row, field)) is None, _number(_value(row, field)) or 0, str(_value(row, field)).lower()), reverse=descending)
        matched = present + missing

    limit = max(1, min(int(limit or DEFAULT_ROWS_RETURNED), MAX_ROWS_RETURNED))
    shown = matched[:limit]
    if columns:
        _check_fields(shown, columns, res)
    display_columns = (columns or _scalar_columns(shown))[:MAX_COLUMNS]

    payload = {"total_matching": len(matched), "returned": len(shown), "rows": shown}
    if truncated:
        payload["warning"] = f"Only the first {MAX_ROWS_SCANNED} records were examined; totals may be incomplete. Say so."
    blocks = []
    if shown:
        blocks.append(
            {
                "type": "table",
                "title": title or "",
                "resource": res.key,
                "columns": display_columns,
                "rows": [{column: _value(row, column) for column in display_columns} for row in shown],
                "total": len(matched),
            }
        )
    return payload, blocks


def get_record(ctx: Context, resource: str, id) -> tuple[dict, list]:
    res = _resource(ctx, resource, catalog.VIEW)
    if not res.is_viewset or not hasattr(res.view, "retrieve"):
        raise ToolError(f"'{res.key}' has no single records; use query_records.")
    result = dispatch.perform(ctx.user, ctx.tenant, res.key, catalog.VIEW, pk=id, handler="retrieve")
    if not result.ok:
        raise ToolError(f"Could not read {res.key} {id}: {result.error}")
    return result.data, [{"type": "record", "resource": res.key, "id": str(id), "title": "", "fields": result.data}]


# ---------------------------------------------------------------------------
# summarize_records
# ---------------------------------------------------------------------------
def _bucket(value, bucket: Optional[str]) -> str:
    if value is None or value == "":
        return ""
    text = str(value)
    if bucket == "year":
        return text[:4]
    if bucket == "month":
        return text[:7]
    if bucket == "day":
        return text[:10]
    return text


def _is_money(field: Optional[str]) -> bool:
    return bool(field) and any(hint in field.lower() for hint in _MONEY_HINTS)


def summarize_records(ctx: Context, resource: str, group_by: str, aggregate: str = "count", measure=None, where=None, bucket=None, chart=None, top=None, title=None) -> tuple[dict, list]:
    res = _resource(ctx, resource, catalog.VIEW)
    if aggregate not in ("count", "sum", "avg", "min", "max"):
        raise ToolError("aggregate must be one of: count, sum, avg, min, max")
    if aggregate != "count" and not measure:
        raise ToolError(f"aggregate '{aggregate}' needs a numeric `measure` field.")
    if bucket not in (None, "day", "month", "year"):
        raise ToolError("bucket must be one of: day, month, year")

    rows, truncated = _fetch_all(ctx, res)
    matched = _filter(rows, where, res)
    _check_fields(matched, [group_by] + ([measure] if measure else []), res)

    groups: dict[str, list[Decimal]] = defaultdict(list)
    for row in matched:
        key = _bucket(_value(row, group_by), bucket)
        if aggregate == "count":
            groups[key].append(Decimal(1))
        else:
            number = _number(_value(row, measure))
            if number is not None:
                groups[key].append(number)

    def total(values: list[Decimal]) -> Decimal:
        if aggregate in ("count", "sum"):
            return sum(values, Decimal(0))
        if aggregate == "avg":
            return (sum(values, Decimal(0)) / len(values)).quantize(Decimal("0.01")) if values else Decimal(0)
        return (min(values) if aggregate == "min" else max(values)) if values else Decimal(0)

    results = [(key, total(values)) for key, values in groups.items()]
    is_time = bucket is not None
    if is_time:
        results.sort(key=lambda item: item[0])  # chronological
        results = results[-MAX_GROUPS:]
    else:
        results.sort(key=lambda item: item[1], reverse=True)  # ranked
        results = results[: max(1, min(int(top or 12), MAX_GROUPS))]

    payload = {
        "groups": [{"group": key, "value": str(value)} for key, value in results],
        "records_summarized": len(matched),
        "group_count": len(groups),
    }
    if truncated:
        payload["warning"] = f"Only the first {MAX_ROWS_SCANNED} records were examined; totals may be incomplete. Say so."

    blocks = []
    if results:
        chart_type = chart if chart in ("bar", "line", "hbar", "none") else ("line" if is_time else "hbar")
        fmt = "money" if aggregate != "count" and _is_money(measure) else "number"
        series_name = "count" if aggregate == "count" else f"{aggregate} of {measure}"
        if chart_type != "none":
            blocks.append(
                {
                    "type": "chart",
                    "title": title or "",
                    "chart": chart_type,
                    "format": fmt,
                    "label_kind": {"month": "month", "day": "date"}.get(bucket, "text"),
                    "series": [{"name": series_name, "points": [{"label": key, "value": str(value)} for key, value in results]}],
                }
            )
        else:
            blocks.append(
                {
                    "type": "table",
                    "title": title or "",
                    "resource": res.key,
                    "columns": [group_by, series_name],
                    "rows": [{group_by: key, series_name: str(value)} for key, value in results],
                    "total": len(results),
                }
            )
    return payload, blocks


# ---------------------------------------------------------------------------
# propose_action
# ---------------------------------------------------------------------------
def _changes(before: Optional[dict], data: dict) -> list[dict]:
    if not isinstance(before, dict):
        return []
    return [{"field": key, "before": before.get(key), "after": value} for key, value in data.items() if before.get(key) != value]


def _accepted_fields(res: catalog.Resource, operation: str) -> Optional[list[str]]:
    """The field names an operation's body may contain, or None where that
    isn't known (an operation whose view reads its body by hand and
    declared no `inputs`)."""
    if operation in (catalog.CREATE, catalog.UPDATE):
        serializer_class = _serializer_class(res)
        if serializer_class is None:
            return None
        return [name for name, field in serializer_class().fields.items() if not field.read_only]
    hint = res.inputs.get(operation)
    if isinstance(hint, type):
        return list(hint().fields)
    if isinstance(hint, dict):
        return list(hint)
    return None if hint else []


def _check_data_fields(res: catalog.Resource, operation: str, data: dict):
    """Refuses a body with a field the operation doesn't take. The API
    itself quietly ignores unknown fields -- harmless when a screen sends
    them, but a model that guesses `unit` for `unit_of_measure` would get a
    record created with the default unit and a proposal card that showed
    the user the value they asked for. Better an error it can correct."""
    accepted = _accepted_fields(res, operation)
    if accepted is None:
        return
    unknown = sorted(set(data) - set(accepted))
    if unknown:
        fields = ", ".join(accepted) if accepted else "none -- this operation takes no data"
        raise ToolError(f"{res.code(operation)} does not take: {', '.join(unknown)}. Fields it takes: {fields}")


def propose_action(ctx: Context, resource: str, operation: str, id=None, data=None, reason: str = "") -> tuple[dict, list]:
    """Checks the action and records it as a proposal. Nothing is changed
    here -- only PendingApproval.approve(), called when a person clicks
    Approve, performs it."""
    res = _resource(ctx, resource, operation)
    op = res.operations[operation]
    if op.kind != catalog.WRITE:
        raise ToolError(f"{res.code(operation)} only reads data; use query_records or get_record.")
    if op.detail and id is None:
        raise ToolError(f"{res.code(operation)} acts on one record: pass its `id` (find it with query_records).")
    if not op.detail:
        id = None
    data = data or {}
    _check_data_fields(res, operation, data)

    outcome = dispatch.check(
        ctx.user, ctx.tenant, res.key, operation, pk=id, data=data, handler="partial_update" if operation == catalog.UPDATE else None
    )
    if not outcome.ok:
        raise ToolError(f"This would be rejected: {outcome.error}. Fix the data (describe_resource shows the fields) and propose again.")

    changes = _changes(outcome.before, data) if operation == catalog.UPDATE else []
    if operation == catalog.UPDATE and not changes:
        raise ToolError("Nothing would change: the record already has these values.")

    approval = PendingApproval.objects.create(
        action_name=res.code(operation),
        resource=res.key,
        operation=operation,
        target_id="" if id is None else str(id),
        action_input=data,
        preview={"target_label": outcome.label, "changes": changes, "reason": (reason or "")[:300]},
        summary=f"{res.code(operation)} {outcome.label}".strip()[:500],
        requested_by=ctx.user,
        conversation=ctx.conversation,
    )
    return (
        {
            "status": "awaiting_user_approval",
            "proposal_id": approval.id,
            "note": "NOT done yet. The user sees an Approve/Reject card for this. Tell them it's ready for their approval; never say it has been done.",
        },
        [{"type": "proposal", "approval_id": approval.id}],
    )


# ---------------------------------------------------------------------------
# Tool definitions handed to the model
# ---------------------------------------------------------------------------
_WHERE_SCHEMA = {
    "type": "array",
    "description": "Conditions that must all hold. Dates compare as YYYY-MM-DD strings.",
    "items": {
        "type": "object",
        "properties": {
            "field": {"type": "string", "description": "A field of the resource; `a.b` reaches into a nested object."},
            "op": {"type": "string", "enum": list(_OPERATORS)},
            "value": {"description": "The value to compare with (a list for `in`; true/false for `is_null`)."},
        },
        "required": ["field", "op"],
    },
}

TOOL_SPECS = [
    {
        "name": "describe_resource",
        "description": "The exact fields of a resource, the operations the user may perform on it, and what data each operation takes. Call this before filtering on a field you haven't seen or proposing a create/update, rather than guessing field names.",
        "input_schema": {"type": "object", "properties": {"resource": {"type": "string"}}, "required": ["resource"]},
    },
    {
        "name": "query_records",
        "description": "List records of a resource (or the rows of a report), filtered and sorted. The result is also shown to the user as a table, so don't repeat every row in your reply -- summarize and point to the table.",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource": {"type": "string"},
                "where": _WHERE_SCHEMA,
                "order_by": {"type": "string", "description": "A field name; prefix with - for descending."},
                "limit": {"type": "integer", "description": f"Rows to return (default {DEFAULT_ROWS_RETURNED}, max {MAX_ROWS_RETURNED}). `total_matching` always counts all matches."},
                "columns": {"type": "array", "items": {"type": "string"}, "description": "Which fields to show in the table (up to 8). Omit for a sensible default."},
                "title": {"type": "string", "description": "A short title for the table, in the user's language."},
            },
            "required": ["resource"],
        },
    },
    {
        "name": "get_record",
        "description": "One record in full, including nested lines. Shown to the user as a detail card.",
        "input_schema": {"type": "object", "properties": {"resource": {"type": "string"}, "id": {"type": ["integer", "string"]}}, "required": ["resource", "id"]},
    },
    {
        "name": "summarize_records",
        "description": "Group records and compute a count/sum/average per group -- the way to answer 'how many/how much per X' and to draw a chart. The numbers are computed by the system and shown to the user as a chart (or a table with chart='none'). Use bucket to group a date field by day/month/year (drawn as a line over time); otherwise groups are ranked largest first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource": {"type": "string"},
                "group_by": {"type": "string", "description": "The field to group on."},
                "aggregate": {"type": "string", "enum": ["count", "sum", "avg", "min", "max"]},
                "measure": {"type": "string", "description": "The numeric field to aggregate (not needed for count)."},
                "where": _WHERE_SCHEMA,
                "bucket": {"type": "string", "enum": ["day", "month", "year"], "description": "Only when group_by is a date."},
                "chart": {"type": "string", "enum": ["bar", "line", "hbar", "none"], "description": "Omit to let the system pick."},
                "top": {"type": "integer", "description": "How many groups to keep when ranking (default 12)."},
                "title": {"type": "string", "description": "A short title for the chart, in the user's language."},
            },
            "required": ["resource", "group_by"],
        },
    },
    {
        "name": "propose_action",
        "description": "Propose a change: create, update or delete a record, or run one of a resource's other operations (post, send, approve, receive...). It is validated immediately and then shown to the user as a card they must approve -- it is NOT performed by this call. For an update, pass only the fields that change. One call per record; to change several records, call it once for each.",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource": {"type": "string"},
                "operation": {"type": "string", "description": "create, update, delete, or another operation listed for the resource."},
                "id": {"type": ["integer", "string"], "description": "The record to act on. Required for everything except create and collection-level operations."},
                "data": {"type": "object", "description": "The request body, using the field names from describe_resource."},
                "reason": {"type": "string", "description": "One short sentence, in the user's language, on why -- shown on the approval card."},
            },
            "required": ["resource", "operation"],
        },
    },
]

_HANDLERS = {
    "describe_resource": describe_resource,
    "query_records": query_records,
    "get_record": get_record,
    "summarize_records": summarize_records,
    "propose_action": propose_action,
}


def is_tool(name: str) -> bool:
    return name in _HANDLERS


def run(ctx: Context, name: str, arguments: dict) -> tuple[dict, list]:
    """Runs one tool call. A ToolError (or a bad argument) comes back as an
    `error` payload for the model to act on."""
    try:
        return _HANDLERS[name](ctx, **(arguments or {}))
    except ToolError as exc:
        return {"error": str(exc)}, []
    except TypeError as exc:
        return {"error": f"Bad arguments for {name}: {exc}"}, []
    except dispatch.UnknownAction as exc:
        return {"error": str(exc)}, []
