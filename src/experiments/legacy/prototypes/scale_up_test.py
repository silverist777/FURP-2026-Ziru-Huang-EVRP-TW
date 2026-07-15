from importlib.metadata import version
from pathlib import Path

from pyvrp import Model
from pyvrp.stop import MaxRuntime

from checkers.feasibility_checker import check_solution, print_benchmark_report
from core.instance_loader import load_instance


INSTANCE_PATH = Path(__file__).resolve().parents[4] / "src" / "data" / "scale_up_instance.json"


def add_clients(model, instance):
    return [
        model.add_client(
            x=spec.x,
            y=spec.y,
            delivery=spec.demand,
            service_duration=spec.service_duration,
            tw_early=spec.tw_early,
            tw_late=spec.tw_late,
            name=spec.name,
        )
        for spec in instance.clients
    ]


def add_complete_graph(model, locations, instance):
    for frm in locations:
        for to in locations:
            if frm is not to:
                model.add_edge(
                    frm,
                    to,
                    distance=instance.distance(frm, to),
                    duration=instance.travel_duration(frm, to),
                )


def print_instance_summary(instance):
    print("Scaled VRPTW heuristic test")
    print(f"  instance={instance.name}")
    print(f"  clients={len(instance.clients)}")
    print(f"  vehicles={instance.num_vehicles}")
    print(f"  vehicle_capacity={instance.vehicle_capacity}")
    print(f"  total_demand={instance.total_demand}")
    print(f"  depot_tw=[{instance.depot.tw_early}, {instance.depot.tw_late}]")
    print(f"  battery_capacity={instance.vehicle.battery_capacity}")
    print(f"  energy_per_distance={instance.energy.consumption_per_distance}")
    print(f"  charging_stations={len(instance.charging_stations)}")


def print_route_schedules(solution, locations):
    print("Route schedules:")

    for route_idx, route in enumerate(solution.routes(), start=1):
        print(f"Route #{route_idx}:")
        print(
            f"  load={route.delivery()} "
            f"distance={route.distance()} "
            f"duration={route.duration()} "
            f"wait={route.wait_duration()} "
            f"time_warp={route.time_warp()}"
        )

        for scheduled_visit in route.schedule():
            location = locations[scheduled_visit.location]
            print(
                f"  {location.name:>5} "
                f"tw=[{location.tw_early:>3}, {location.tw_late:>3}] "
                f"start={scheduled_visit.start_service:>3} "
                f"end={scheduled_visit.end_service:>3} "
                f"wait={scheduled_visit.wait_duration:>3} "
                f"warp={scheduled_visit.time_warp:>3}"
            )


def build_model(instance):
    model = Model()
    depot = model.add_depot(
        x=instance.depot.x,
        y=instance.depot.y,
        tw_early=instance.depot.tw_early,
        tw_late=instance.depot.tw_late,
        name=instance.depot.name,
    )
    clients = add_clients(model, instance)

    model.add_vehicle_type(
        num_available=instance.num_vehicles,
        capacity=instance.vehicle_capacity,
        start_depot=depot,
        end_depot=depot,
        tw_early=instance.vehicle.tw_early,
        tw_late=instance.vehicle.tw_late,
    )

    locations = [depot, *clients]
    add_complete_graph(model, locations, instance)

    return model, locations


def main():
    instance = load_instance(INSTANCE_PATH)
    model, locations = build_model(instance)

    print_instance_summary(instance)
    result = model.solve(
        MaxRuntime(instance.solver.runtime_seconds),
        seed=instance.solver.seed,
        display=instance.solver.display,
    )
    solution = result.best
    report = check_solution(
        solution=solution,
        depot=instance.checker_depot_spec(),
        customers=instance.checker_customer_specs(),
        config=instance.checker_config(),
    )

    if not solution.is_feasible() or solution.time_warp() != 0 or not report.feasible:
        raise AssertionError("Scale-up test failed: solution violates constraints.")

    print(f"PyVRP version: {version('pyvrp')}")
    print(result)
    print("Best solution:")
    print(solution)
    print_route_schedules(solution, locations)
    print_benchmark_report(
        report,
        runtime_seconds=instance.solver.runtime_seconds,
        seed=instance.solver.seed,
    )


if __name__ == "__main__":
    main()
