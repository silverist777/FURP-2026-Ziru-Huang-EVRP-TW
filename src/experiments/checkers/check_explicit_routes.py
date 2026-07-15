import argparse
import json
from pathlib import Path

from checkers.feasibility_checker import check_explicit_routes, print_benchmark_report
from core.instance_loader import load_instance


def load_routes(path):
    route_path = Path(path)
    with route_path.open(encoding="utf-8") as file:
        data = json.load(file)

    routes = data.get("routes") if isinstance(data, dict) else data
    if not isinstance(routes, list):
        raise ValueError("Routes file must be a list or an object with a 'routes' list.")
    for route in routes:
        if not isinstance(route, list) or not all(isinstance(name, str) for name in route):
            raise ValueError("Each route must be a list of location names.")
    return routes


def main():
    parser = argparse.ArgumentParser(
        description="Check explicit EVRP-TW routes with customers and charging stations."
    )
    parser.add_argument("--instance", required=True)
    parser.add_argument("--routes", required=True)
    args = parser.parse_args()

    instance = load_instance(args.instance)
    routes = load_routes(args.routes)
    report = check_explicit_routes(
        routes=routes,
        depot=instance.checker_depot_spec(),
        customers=instance.checker_customer_specs(),
        charging_stations=instance.checker_charging_station_specs(),
        config=instance.checker_config(),
    )
    print_benchmark_report(report, solver="ExplicitRouteChecker")
    return 0 if report.feasible else 1


if __name__ == "__main__":
    raise SystemExit(main())
