"""Deterministic quantities. Model output never supplies measured values."""

from decimal import Decimal, InvalidOperation

MEMORY_UNITS = {"bytes": 1, "KiB": 1024, "MiB": 1048576, "GiB": 1073741824,
                "KB": 1000, "MB": 1000000, "GB": 1000000000}


def quantity(value, unit: str, *, dimension: str = "memory") -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("A quantity must be a finite number, not text or a boolean.")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Invalid quantity.") from exc
    if not number.is_finite() or number < 0:
        raise ValueError("Quantities must be finite and nonnegative.")
    if dimension == "percentage":
        if unit != "percent" or number > 100:
            raise ValueError("Normalized percentages must be within 0 and 100.")
        return number
    if dimension not in {"memory", "disk"} or unit not in MEMORY_UNITS:
        raise ValueError("Unsupported quantity dimension or unit.")
    return number * MEMORY_UNITS[unit]


def memory_values(data: dict) -> dict:
    """Validate byte counters and calculate values independently of supplied derivatives."""
    result = {"memory_usage_mib": None, "memory_limit_mib": None, "memory_usage_percent": None}
    usage, limit = data.get("memory_usage_bytes"), data.get("memory_limit_bytes")
    if type(usage) is not int or usage < 0:
        return result
    result["memory_usage_mib"] = float((Decimal(usage) / 1048576).quantize(Decimal("0.01")))
    if type(limit) is not int or limit <= 0:
        return result
    result["memory_limit_mib"] = float((Decimal(limit) / 1048576).quantize(Decimal("0.01")))
    if usage <= limit:
        result["memory_usage_percent"] = float((Decimal(100) * usage / limit).quantize(Decimal("0.01")))
    return result


def at_memory_review_threshold(data: dict) -> bool:
    """Compare raw integer counters; display rounding must not trigger the policy."""
    return (memory_values(data)['memory_usage_percent'] is not None
        and data['memory_usage_bytes'] * 100 >= data['memory_limit_bytes'] * 90)
