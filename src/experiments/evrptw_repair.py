from dataclasses import dataclass, field
from heapq import heappop, heappush
from itertools import count
from math import ceil


EPS = 1e-9


@dataclass(frozen=True)
class RouteRepairResult:
    feasible: bool
    route: list[str]
    distance: int = 0
    return_time: int = 0
    charging_count: int = 0
    charging_time: int = 0
    reason: str = ""


@dataclass(frozen=True)
class RepairPlan:
    feasible: bool
    routes: list[list[str]]
    split_count: int
    station_insertions: int
    attempts: list[dict] = field(default_factory=list)
    unsolved: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class Label:
    location_name: str
    position: int
    time: float
    battery: float
    distance: int
    path: list[str]
    charging_count: int = 0
    charging_time: int = 0


def repair_routes_with_splitting(customer_routes, instance):
    """Repairs PyVRP customer routes by inserting stations and splitting failures."""

    pending = [list(route) for route in customer_routes if route]
    repaired_routes = []
    attempts = []
    unsolved = []
    split_count = 0

    while pending:
        if len(repaired_routes) + len(pending) > instance.num_vehicles:
            unsolved.append(
                {
                    "reason": "vehicle_limit_exceeded",
                    "available": instance.num_vehicles,
                    "needed_at_least": len(repaired_routes) + len(pending),
                    "pending_routes": pending,
                }
            )
            break

        route = pending.pop(0)
        result = repair_customer_sequence(route, instance)
        attempts.append(
            {
                "customers": route,
                "feasible": result.feasible,
                "reason": result.reason,
            }
        )

        if result.feasible:
            repaired_routes.append(result.route)
            continue

        if len(route) == 1:
            unsolved.append(
                {
                    "reason": result.reason or "single_customer_unrepairable",
                    "customers": route,
                }
            )
            continue

        midpoint = len(route) // 2
        pending.insert(0, route[midpoint:])
        pending.insert(0, route[:midpoint])
        split_count += 1

    feasible = not unsolved and len(repaired_routes) <= instance.num_vehicles
    return RepairPlan(
        feasible=feasible,
        routes=repaired_routes,
        split_count=split_count,
        station_insertions=sum(count_station_visits(route, instance) for route in repaired_routes),
        attempts=attempts,
        unsolved=unsolved,
    )


def repair_customer_sequence(customer_names, instance):
    """Finds a feasible EVRP-TW route for one fixed customer visit order."""

    customers_by_name = {customer.name: customer for customer in instance.clients}
    stations = list(instance.charging_stations)
    ordered_customers = []
    for name in customer_names:
        customer = customers_by_name.get(name)
        if customer is None:
            return RouteRepairResult(False, [], reason=f"unknown_customer:{name}")
        ordered_customers.append(customer)

    if sum(customer.demand for customer in ordered_customers) > instance.vehicle_capacity:
        return RouteRepairResult(False, [], reason="capacity_exceeded")

    depot = instance.depot
    initial_battery = route_initial_battery(instance)
    battery_capacity = route_battery_capacity(instance)
    energy_rate = route_energy_rate(instance)
    minimum_battery = route_minimum_battery(instance)
    locations = {depot.name: depot}
    locations.update({customer.name: customer for customer in ordered_customers})
    locations.update({station.name: station for station in stations})

    if not ordered_customers:
        return RouteRepairResult(True, [depot.name, depot.name])

    queue = []
    serial = count()
    start = Label(
        location_name=depot.name,
        position=0,
        time=0,
        battery=initial_battery,
        distance=0,
        path=[depot.name],
    )
    labels = {(depot.name, 0): [start]}
    heappush(queue, (0, 0, next(serial), start))

    while queue:
        _distance_key, _time_key, _serial_key, label = heappop(queue)
        current = locations[label.location_name]

        if label.position == len(ordered_customers):
            returned = try_return_to_depot(
                label=label,
                current=current,
                depot=depot,
                instance=instance,
                energy_rate=energy_rate,
                minimum_battery=minimum_battery,
            )
            if returned is not None:
                return returned

        for next_label in next_labels(
            label=label,
            current=current,
            ordered_customers=ordered_customers,
            stations=stations,
            instance=instance,
            battery_capacity=battery_capacity,
            energy_rate=energy_rate,
            minimum_battery=minimum_battery,
        ):
            key = (next_label.location_name, next_label.position)
            old_labels = labels.setdefault(key, [])
            if is_dominated(old_labels, next_label):
                continue
            old_labels[:] = [
                old for old in old_labels if not dominates(next_label, old)
            ]
            old_labels.append(next_label)
            heappush(
                queue,
                (
                    next_label.distance,
                    next_label.time,
                    next(serial),
                    next_label,
                ),
            )

    return RouteRepairResult(False, [], reason="no_station_repair_found")


def next_labels(
    label,
    current,
    ordered_customers,
    stations,
    instance,
    battery_capacity,
    energy_rate,
    minimum_battery,
):
    labels = []
    if label.position < len(ordered_customers):
        customer = ordered_customers[label.position]
        next_label = travel_to_customer(
            label=label,
            current=current,
            customer=customer,
            instance=instance,
            energy_rate=energy_rate,
            minimum_battery=minimum_battery,
        )
        if next_label is not None:
            labels.append(next_label)

    if battery_capacity is None or energy_rate is None:
        return labels

    for station in stations:
        if station.name == label.location_name:
            continue
        next_label = travel_to_station(
            label=label,
            current=current,
            station=station,
            instance=instance,
            battery_capacity=battery_capacity,
            energy_rate=energy_rate,
            minimum_battery=minimum_battery,
        )
        if next_label is not None:
            labels.append(next_label)

    return labels


def travel_to_customer(label, current, customer, instance, energy_rate, minimum_battery):
    leg_distance = instance.distance(current, customer)
    next_battery = consume(label.battery, leg_distance, energy_rate)
    if next_battery < minimum_battery - EPS:
        return None

    arrival = label.time + instance.travel_duration(current, customer)
    start_service = max(arrival, customer.tw_early)
    if start_service > customer.tw_late:
        return None

    return Label(
        location_name=customer.name,
        position=label.position + 1,
        time=start_service + customer.service_duration,
        battery=next_battery,
        distance=label.distance + leg_distance,
        path=[*label.path, customer.name],
        charging_count=label.charging_count,
        charging_time=label.charging_time,
    )


def travel_to_station(
    label,
    current,
    station,
    instance,
    battery_capacity,
    energy_rate,
    minimum_battery,
):
    leg_distance = instance.distance(current, station)
    next_battery = consume(label.battery, leg_distance, energy_rate)
    if next_battery < minimum_battery - EPS:
        return None

    energy_needed = max(0, battery_capacity - next_battery)
    if energy_needed <= EPS:
        return None

    charging_rate = station.charging_rate
    if charging_rate is None:
        charging_rate = instance.charging.charging_rate
    if charging_rate is None or charging_rate <= 0:
        return None

    arrival = label.time + instance.travel_duration(current, station)
    start_service = max(arrival, station.tw_early)
    if start_service > station.tw_late:
        return None

    charge_time = ceil(energy_needed / charging_rate)
    return Label(
        location_name=station.name,
        position=label.position,
        time=start_service + station.service_duration + charge_time,
        battery=battery_capacity,
        distance=label.distance + leg_distance,
        path=[*label.path, station.name],
        charging_count=label.charging_count + 1,
        charging_time=label.charging_time + charge_time,
    )


def try_return_to_depot(
    label,
    current,
    depot,
    instance,
    energy_rate,
    minimum_battery,
):
    return_distance = instance.distance(current, depot)
    return_battery = consume(label.battery, return_distance, energy_rate)
    if return_battery < minimum_battery - EPS:
        return None

    return_time = label.time + instance.travel_duration(current, depot)
    if return_time > depot.tw_late:
        return None

    return RouteRepairResult(
        feasible=True,
        route=[*label.path, depot.name],
        distance=label.distance + return_distance,
        return_time=return_time,
        charging_count=label.charging_count,
        charging_time=label.charging_time,
    )


def consume(battery, distance, energy_rate):
    if energy_rate is None:
        return battery
    return battery - distance * energy_rate


def route_initial_battery(instance):
    if instance.vehicle.initial_battery is not None:
        return instance.vehicle.initial_battery
    if instance.vehicle.battery_capacity is not None:
        return instance.vehicle.battery_capacity
    return float("inf")


def route_battery_capacity(instance):
    return instance.vehicle.battery_capacity


def route_energy_rate(instance):
    return instance.energy.consumption_per_distance


def route_minimum_battery(instance):
    if instance.energy.minimum_battery is None:
        return 0
    return instance.energy.minimum_battery


def dominates(left, right):
    return (
        left.time <= right.time + EPS
        and left.battery >= right.battery - EPS
        and left.distance <= right.distance + EPS
    )


def is_dominated(existing_labels, candidate):
    return any(dominates(old, candidate) for old in existing_labels)


def count_station_visits(route, instance):
    station_names = {station.name for station in instance.charging_stations}
    return sum(1 for name in route if name in station_names)
