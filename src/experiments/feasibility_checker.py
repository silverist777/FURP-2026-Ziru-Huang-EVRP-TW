from dataclasses import dataclass, field
from math import hypot


@dataclass(frozen=True)
class DepotSpec:
    """Minimal depot data needed by the independent feasibility checker."""

    name: str
    x: float
    y: float
    tw_early: int
    tw_late: int


@dataclass(frozen=True)
class CustomerSpec:
    """Customer data used to recompute route load and time-window feasibility."""

    name: str
    x: float
    y: float
    demand: int
    service_duration: int
    tw_early: int
    tw_late: int


@dataclass(frozen=True)
class CheckerConfig:
    """Global checker settings shared by all routes in one instance."""

    vehicle_capacity: int
    distance_scale: int
    duration_scale: int
    # Reserved for the later EVRP-TW step: battery capacity and edge energy use.
    battery_capacity: float | None = None
    energy_per_distance: float | None = None
    minimum_battery: float | None = None


@dataclass(frozen=True)
class Violation:
    """One constraint violation, with enough context for failure analysis."""

    constraint: str
    route_index: int | None
    location: str
    detail: str


@dataclass(frozen=True)
class RouteMetrics:
    """Metrics for one vehicle route after independently replaying the visits."""

    route_index: int
    visits: list[str]
    load: int
    distance: int
    duration: int
    wait_time: int
    return_time: int
    time_window_violations: int
    capacity_violations: int
    # These are zero for plain VRPTW, but keep the report shape EVRP-ready.
    energy_violations: int = 0
    charging_count: int = 0
    charging_time: int = 0
    synchronization_violations: int = 0


@dataclass(frozen=True)
class FeasibilityReport:
    """Full benchmark-style report for a solved instance."""

    feasible: bool
    total_distance: int
    total_duration: int
    makespan: int
    served_customers: int
    missing_customers: list[str]
    duplicate_customers: list[str]
    time_window_violations: int
    capacity_violations: int
    energy_violations: int
    charging_count: int
    charging_time: int
    synchronization_violations: int
    route_metrics: list[RouteMetrics] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)


def distance_between(a, b, scale):
    """Returns scaled Euclidean distance between two points as an integer."""

    return round(scale * hypot(a.x - b.x, a.y - b.y))


def check_solution(solution, depot, customers, config):
    """Checks every route in a PyVRP solution and aggregates benchmark metrics.

    PyVRP gives us routes as customer indices. This function maps those indices
    back to our own customer specs, checks route-level feasibility, then checks
    global coverage: every customer should appear exactly once.
    """

    customer_by_index = {idx: customer for idx, customer in enumerate(customers, start=1)}
    visit_counts = {idx: 0 for idx in customer_by_index}
    route_metrics = []
    violations = []

    for route_idx, route in enumerate(solution.routes(), start=1):
        metrics, route_violations = check_route(
            route_idx=route_idx,
            visits=route.visits(),
            depot=depot,
            customer_by_index=customer_by_index,
            config=config,
            visit_counts=visit_counts,
        )
        route_metrics.append(metrics)
        violations.extend(route_violations)

    missing = []
    duplicates = []
    for customer_idx, count in visit_counts.items():
        customer = customer_by_index[customer_idx]
        if count == 0:
            missing.append(customer.name)
            violations.append(
                Violation(
                    constraint="customer_coverage",
                    route_index=None,
                    location=customer.name,
                    detail="Customer was not visited.",
                )
            )
        elif count > 1:
            duplicates.append(customer.name)
            violations.append(
                Violation(
                    constraint="customer_coverage",
                    route_index=None,
                    location=customer.name,
                    detail=f"Customer was visited {count} times.",
                )
            )

    # Aggregate route-level values into the same metrics used by the project
    # benchmark document: objective proxy, feasibility, runtime, and violations.
    total_distance = sum(route.distance for route in route_metrics)
    total_duration = sum(route.duration for route in route_metrics)
    makespan = max((route.return_time for route in route_metrics), default=0)
    time_window_violations = sum(route.time_window_violations for route in route_metrics)
    capacity_violations = sum(route.capacity_violations for route in route_metrics)
    energy_violations = sum(route.energy_violations for route in route_metrics)
    charging_count = sum(route.charging_count for route in route_metrics)
    charging_time = sum(route.charging_time for route in route_metrics)
    synchronization_violations = sum(
        route.synchronization_violations for route in route_metrics
    )

    feasible = not (
        missing
        or duplicates
        or time_window_violations
        or capacity_violations
        or energy_violations
        or synchronization_violations
    )

    return FeasibilityReport(
        feasible=feasible,
        total_distance=total_distance,
        total_duration=total_duration,
        makespan=makespan,
        served_customers=sum(1 for count in visit_counts.values() if count == 1),
        missing_customers=missing,
        duplicate_customers=duplicates,
        time_window_violations=time_window_violations,
        capacity_violations=capacity_violations,
        energy_violations=energy_violations,
        charging_count=charging_count,
        charging_time=charging_time,
        synchronization_violations=synchronization_violations,
        route_metrics=route_metrics,
        violations=violations,
    )


def check_route(route_idx, visits, depot, customer_by_index, config, visit_counts):
    """Replays one route and returns route metrics plus detailed violations.

    The replay starts at the depot at time 0, travels through each customer in
    the route order, waits if it arrives before a customer's early time window,
    adds service duration, and finally returns to the depot.
    """

    current = depot
    current_time = 0
    load = 0
    route_distance = 0
    wait_time = 0
    time_window_violations = 0
    capacity_violations = 0
    energy_violations = 0
    remaining_energy = config.battery_capacity
    minimum_battery = 0 if config.minimum_battery is None else config.minimum_battery
    visit_names = []
    violations = []

    for customer_idx in visits:
        customer = customer_by_index[customer_idx]
        visit_counts[customer_idx] += 1
        visit_names.append(customer.name)

        leg_distance = distance_between(current, customer, config.distance_scale)
        leg_duration = distance_between(current, customer, config.duration_scale)
        route_distance += leg_distance
        arrival = current_time + leg_duration
        start_service = max(arrival, customer.tw_early)
        wait_time += max(0, customer.tw_early - arrival)
        if remaining_energy is not None and config.energy_per_distance is not None:
            remaining_energy -= leg_distance * config.energy_per_distance
            if remaining_energy < minimum_battery:
                energy_violations += 1
                violations.append(
                    Violation(
                        constraint="energy",
                        route_index=route_idx,
                        location=customer.name,
                        detail=(
                            f"remaining_energy={remaining_energy:.2f}, "
                            f"minimum_battery={minimum_battery}"
                        ),
                    )
                )

        # A late service start is the first point where the route becomes
        # infeasible for this customer.
        if start_service > customer.tw_late:
            time_window_violations += 1
            violations.append(
                Violation(
                    constraint="time_window",
                    route_index=route_idx,
                    location=customer.name,
                    detail=(
                        f"arrival={arrival}, start_service={start_service}, "
                        f"latest={customer.tw_late}"
                    ),
                )
            )

        current_time = start_service + customer.service_duration
        load += customer.demand
        current = customer

    # Close the route by returning to the depot and checking the depot window.
    return_distance = distance_between(current, depot, config.distance_scale)
    route_distance += return_distance
    return_time = current_time + distance_between(current, depot, config.duration_scale)
    if remaining_energy is not None and config.energy_per_distance is not None:
        remaining_energy -= return_distance * config.energy_per_distance
        if remaining_energy < minimum_battery:
            energy_violations += 1
            violations.append(
                Violation(
                    constraint="energy",
                    route_index=route_idx,
                    location=depot.name,
                    detail=(
                        f"remaining_energy={remaining_energy:.2f}, "
                        f"minimum_battery={minimum_battery}"
                    ),
                )
            )

    if return_time > depot.tw_late:
        time_window_violations += 1
        violations.append(
            Violation(
                constraint="time_window",
                route_index=route_idx,
                location=depot.name,
                detail=f"return_time={return_time}, latest={depot.tw_late}",
            )
        )

    if load > config.vehicle_capacity:
        capacity_violations += 1
        violations.append(
            Violation(
                constraint="capacity",
                route_index=route_idx,
                location="route",
                detail=f"load={load}, capacity={config.vehicle_capacity}",
            )
        )

    return (
        RouteMetrics(
            route_index=route_idx,
            visits=visit_names,
            load=load,
            distance=route_distance,
            duration=return_time,
            wait_time=wait_time,
            return_time=return_time,
            time_window_violations=time_window_violations,
            capacity_violations=capacity_violations,
            energy_violations=energy_violations,
        ),
        violations,
    )


def print_benchmark_report(report, runtime_seconds=None, seed=None, solver="PyVRP"):
    """Prints the feasibility report using the project's benchmark vocabulary."""

    print("Benchmark metrics:")
    print(f"  solver={solver}")
    if seed is not None:
        print(f"  seed={seed}")
    if runtime_seconds is not None:
        print(f"  runtime={runtime_seconds:.2f}s")
    print(f"  feasible={report.feasible}")
    print(f"  total_distance={report.total_distance}")
    print(f"  total_duration={report.total_duration}")
    print(f"  makespan={report.makespan}")
    print(f"  served_customers={report.served_customers}")
    print(f"  missing_customers={len(report.missing_customers)}")
    print(f"  duplicate_customers={len(report.duplicate_customers)}")
    print(f"  time_window_violations={report.time_window_violations}")
    print(f"  capacity_violations={report.capacity_violations}")
    print(f"  energy_violations={report.energy_violations}")
    print(f"  charging_count={report.charging_count}")
    print(f"  charging_time={report.charging_time}")
    print(f"  synchronization_violations={report.synchronization_violations}")

    if report.violations:
        print("Violation details:")
        for violation in report.violations:
            route = "-" if violation.route_index is None else violation.route_index
            print(
                f"  route={route} "
                f"constraint={violation.constraint} "
                f"location={violation.location} "
                f"detail={violation.detail}"
            )
