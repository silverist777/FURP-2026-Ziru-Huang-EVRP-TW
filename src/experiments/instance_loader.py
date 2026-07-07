from __future__ import annotations

from dataclasses import dataclass
import json
from math import hypot
from pathlib import Path

from feasibility_checker import (
    CheckerConfig,
    ChargingStationSpec,
    CustomerSpec,
    DepotSpec,
)


DEFAULT_DISTANCE_SCALE = 1
DEFAULT_DURATION_SCALE = 1
DEFAULT_TW_EARLY = 0
DEFAULT_TW_LATE = 1_000_000
DEFAULT_NUM_VEHICLES = 1
DEFAULT_VEHICLE_CAPACITY = 1_000_000
DEFAULT_SERVICE_DURATION = 0
DEFAULT_DEMAND = 0
DEFAULT_SOLVER_RUNTIME_SECONDS = 10
DEFAULT_SOLVER_SEED = 1
DEFAULT_SOLVER_DISPLAY = True


@dataclass(frozen=True)
class LocationData:
    name: str
    x: float
    y: float
    tw_early: int
    tw_late: int


@dataclass(frozen=True)
class ClientData(LocationData):
    demand: int
    service_duration: int


@dataclass(frozen=True)
class ChargingStationData(LocationData):
    service_duration: int
    charging_rate: float | None = None


@dataclass(frozen=True)
class VehicleData:
    num_available: int
    capacity: int
    start_depot: str
    end_depot: str
    tw_early: int
    tw_late: int
    battery_capacity: int | None = None
    initial_battery: int | None = None


@dataclass(frozen=True)
class EnergyData:
    consumption_per_distance: float | None = None
    minimum_battery: int | None = None


@dataclass(frozen=True)
class ChargingData:
    policy: str
    allow_partial_recharge: bool
    charging_rate: float | None = None
    fixed_service_duration: int = 0


@dataclass(frozen=True)
class SolverData:
    runtime_seconds: int
    seed: int
    display: bool


@dataclass(frozen=True)
class InstanceData:
    name: str
    problem_type: str
    objective: dict[str, str]
    distance_metric: str
    distance_scale: int
    duration_metric: str
    duration_scale: int
    vehicle: VehicleData
    energy: EnergyData
    charging: ChargingData
    solver: SolverData
    depot: LocationData
    clients: list[ClientData]
    charging_stations: list[ChargingStationData]

    @property
    def total_demand(self):
        return sum(client.demand for client in self.clients)

    @property
    def num_vehicles(self):
        return self.vehicle.num_available

    @property
    def vehicle_capacity(self):
        return self.vehicle.capacity

    def distance(self, a, b):
        return round(self.distance_scale * hypot(a.x - b.x, a.y - b.y))

    def travel_duration(self, a, b):
        return round(self.duration_scale * hypot(a.x - b.x, a.y - b.y))

    def checker_depot_spec(self):
        return DepotSpec(
            name=self.depot.name,
            x=self.depot.x,
            y=self.depot.y,
            tw_early=self.depot.tw_early,
            tw_late=self.depot.tw_late,
        )

    def checker_customer_specs(self):
        return [
            CustomerSpec(
                name=client.name,
                x=client.x,
                y=client.y,
                demand=client.demand,
                service_duration=client.service_duration,
                tw_early=client.tw_early,
                tw_late=client.tw_late,
            )
            for client in self.clients
        ]

    def checker_charging_station_specs(self):
        return [
            ChargingStationSpec(
                name=station.name,
                x=station.x,
                y=station.y,
                service_duration=station.service_duration,
                tw_early=station.tw_early,
                tw_late=station.tw_late,
                charging_rate=station.charging_rate,
            )
            for station in self.charging_stations
        ]

    def checker_config(self):
        return CheckerConfig(
            vehicle_capacity=self.vehicle.capacity,
            distance_scale=self.distance_scale,
            duration_scale=self.duration_scale,
            battery_capacity=self.vehicle.battery_capacity,
            initial_battery=self.vehicle.initial_battery,
            energy_per_distance=self.energy.consumption_per_distance,
            minimum_battery=self.energy.minimum_battery,
            charging_rate=self.charging.charging_rate,
            allow_partial_recharge=self.charging.allow_partial_recharge,
        )


def first_present(*values):
    for value in values:
        if value is not None:
            return value
    return None


def get_or_default(mapping, key, default):
    return first_present(mapping.get(key), default)


def as_mapping(value):
    return value if isinstance(value, dict) else {}


def as_list(value):
    return value if isinstance(value, list) else []


def load_instance(path):
    instance_path = Path(path)
    with instance_path.open(encoding="utf-8") as file:
        data = json.load(file)

    return load_instance_data(data, default_name=instance_path.stem)


def load_instance_data(data, default_name="instance"):
    depot = as_mapping(data.get("depot"))
    depot_name = get_or_default(depot, "name", "depot")
    depot_tw_early = get_or_default(depot, "tw_early", DEFAULT_TW_EARLY)
    depot_tw_late = get_or_default(depot, "tw_late", DEFAULT_TW_LATE)

    vehicles = as_mapping(data.get("vehicles"))
    distance = as_mapping(data.get("distance"))
    duration = as_mapping(data.get("duration"))
    energy = as_mapping(data.get("energy"))
    charging = as_mapping(data.get("charging"))
    solver = as_mapping(data.get("solver"))
    clients = [
        ClientData(
            name=get_or_default(client, "name", f"c{idx:02d}"),
            x=get_or_default(client, "x", 0),
            y=get_or_default(client, "y", 0),
            demand=get_or_default(client, "demand", DEFAULT_DEMAND),
            service_duration=get_or_default(
                client,
                "service_duration",
                DEFAULT_SERVICE_DURATION,
            ),
            tw_early=get_or_default(client, "tw_early", depot_tw_early),
            tw_late=get_or_default(client, "tw_late", depot_tw_late),
        )
        for idx, client in enumerate(
            (as_mapping(item) for item in as_list(data.get("clients"))),
            start=1,
        )
    ]
    charging_stations = [
        ChargingStationData(
            name=get_or_default(station, "name", f"s{idx:02d}"),
            x=get_or_default(station, "x", 0),
            y=get_or_default(station, "y", 0),
            service_duration=get_or_default(
                station,
                "service_duration",
                get_or_default(charging, "fixed_service_duration", 0),
            ),
            tw_early=get_or_default(station, "tw_early", depot_tw_early),
            tw_late=get_or_default(station, "tw_late", depot_tw_late),
            charging_rate=first_present(
                station.get("charging_rate"),
                charging.get("charging_rate"),
            ),
        )
        for idx, station in enumerate(
            (as_mapping(item) for item in as_list(data.get("charging_stations"))),
            start=1,
        )
    ]

    return InstanceData(
        name=get_or_default(data, "name", default_name),
        problem_type=get_or_default(data, "problem_type", "VRPTW"),
        objective=first_present(
            data.get("objective"),
            {
                "primary": "minimize_total_distance",
                "secondary": "none",
            },
        ),
        distance_metric=get_or_default(distance, "metric", "euclidean"),
        distance_scale=first_present(
            distance.get("scale"),
            data.get("distance_scale"),
            DEFAULT_DISTANCE_SCALE,
        ),
        duration_metric=get_or_default(duration, "metric", "euclidean"),
        duration_scale=first_present(
            duration.get("scale"),
            data.get("duration_scale"),
            DEFAULT_DURATION_SCALE,
        ),
        vehicle=VehicleData(
            num_available=get_or_default(
                vehicles,
                "num_available",
                DEFAULT_NUM_VEHICLES,
            ),
            capacity=get_or_default(
                vehicles,
                "capacity",
                DEFAULT_VEHICLE_CAPACITY,
            ),
            start_depot=get_or_default(vehicles, "start_depot", depot_name),
            end_depot=get_or_default(vehicles, "end_depot", depot_name),
            tw_early=get_or_default(vehicles, "tw_early", depot_tw_early),
            tw_late=get_or_default(vehicles, "tw_late", depot_tw_late),
            battery_capacity=vehicles.get("battery_capacity"),
            initial_battery=vehicles.get("initial_battery"),
        ),
        energy=EnergyData(
            consumption_per_distance=energy.get("consumption_per_distance"),
            minimum_battery=energy.get("minimum_battery"),
        ),
        charging=ChargingData(
            policy=get_or_default(charging, "policy", "none"),
            allow_partial_recharge=get_or_default(
                charging,
                "allow_partial_recharge",
                False,
            ),
            charging_rate=charging.get("charging_rate"),
            fixed_service_duration=get_or_default(
                charging,
                "fixed_service_duration",
                0,
            ),
        ),
        solver=SolverData(
            runtime_seconds=get_or_default(
                solver,
                "runtime_seconds",
                DEFAULT_SOLVER_RUNTIME_SECONDS,
            ),
            seed=get_or_default(solver, "seed", DEFAULT_SOLVER_SEED),
            display=get_or_default(solver, "display", DEFAULT_SOLVER_DISPLAY),
        ),
        depot=LocationData(
            name=depot_name,
            x=get_or_default(depot, "x", 0),
            y=get_or_default(depot, "y", 0),
            tw_early=depot_tw_early,
            tw_late=depot_tw_late,
        ),
        clients=clients,
        charging_stations=charging_stations,
    )
