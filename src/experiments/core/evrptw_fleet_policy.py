"""Shared fleet-size policy for EVRPTW experiments."""

from __future__ import annotations

from math import ceil


FLEET_DIVISOR = 4
FLEET_POLICY_NAME = "ceil((clients + charging_stations) / 4)"


def evrptw_vehicle_limit(data: dict) -> int:
    """Returns the mandatory EVRPTW fleet limit for a project-schema instance."""

    clients = data.get("clients") or []
    stations = data.get("charging_stations") or []
    return max(1, ceil((len(clients) + len(stations)) / FLEET_DIVISOR))


def apply_evrptw_vehicle_limit(data: dict) -> int | None:
    """Applies the shared fleet limit in place and records its provenance."""

    if str(data.get("problem_type", "")).upper() != "EVRPTW":
        return None

    client_count = len(data.get("clients") or [])
    station_count = len(data.get("charging_stations") or [])
    limit = evrptw_vehicle_limit(data)
    data.setdefault("vehicles", {})["num_available"] = limit
    data["vehicle_limit_policy"] = {
        "formula": FLEET_POLICY_NAME,
        "rounding": "ceiling",
        "client_count": client_count,
        "charging_station_count": station_count,
        "vehicle_limit": limit,
    }
    return limit
