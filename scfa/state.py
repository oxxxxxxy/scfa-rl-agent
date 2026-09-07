"""
Rich game state representations and Unit abstractions for Supreme Commander: Forged Alliance.
"""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union


@dataclass
class ResourceRate:
    stored: float = 0.0
    capacity: float = 0.0
    income: float = 0.0
    usage: float = 0.0
    requested: float = 0.0
    trend: float = 0.0

    @property
    def ratio(self) -> float:
        return self.stored / max(self.capacity, 1.0)


@dataclass
class EconomyState:
    mass: ResourceRate = field(default_factory=ResourceRate)
    energy: ResourceRate = field(default_factory=ResourceRate)


@dataclass
class MassSpot:
    x: float
    z: float
    status: str = "free"  # "free", "ally", "enemy"

    @property
    def position(self) -> Tuple[float, float, float]:
        return (self.x, 0.0, self.z)

    @property
    def is_free(self) -> bool:
        return self.status == "free"

    @property
    def is_ally(self) -> bool:
        return self.status == "ally"

    @property
    def is_enemy(self) -> bool:
        return self.status == "enemy"


@dataclass
class Unit:
    id: int
    blueprint_id: str
    position: Tuple[float, float, float]
    health: float
    max_health: float
    fraction_complete: float = 1.0
    tags: List[str] = field(default_factory=list)
    mass_in: float = 0.0
    mass_out: float = 0.0
    energy_in: float = 0.0
    energy_out: float = 0.0
    build_rate: float = 0.0
    fuel: float = 1.0
    _client: Optional[Any] = field(default=None, repr=False)

    @property
    def is_alive(self) -> bool:
        return self.health > 0.0

    @property
    def is_complete(self) -> bool:
        return self.fraction_complete >= 0.99

    @property
    def health_ratio(self) -> float:
        return self.health / max(self.max_health, 1.0)

    @property
    def is_commander(self) -> bool:
        return "COMMANDER" in self.tags

    @property
    def is_subcommander(self) -> bool:
        return "SUBCOMMANDER" in self.tags

    @property
    def is_engineer(self) -> bool:
        return "ENGINEER" in self.tags

    @property
    def is_factory(self) -> bool:
        return "FACTORY" in self.tags

    @property
    def is_land(self) -> bool:
        return "LAND" in self.tags

    @property
    def is_air(self) -> bool:
        return "AIR" in self.tags

    @property
    def is_naval(self) -> bool:
        return "NAVAL" in self.tags

    @property
    def is_structure(self) -> bool:
        return "STRUCTURE" in self.tags

    @property
    def is_shield(self) -> bool:
        return "SHIELD" in self.tags

    @property
    def is_radar(self) -> bool:
        return "RADAR" in self.tags or "OMNI" in self.tags

    @property
    def is_experimental(self) -> bool:
        return "EXPERIMENTAL" in self.tags

    @property
    def is_combat(self) -> bool:
        return (
            ("DIRECTFIRE" in self.tags or "ANTIAIR" in self.tags)
            and not self.is_structure
            and not self.is_commander
            and not self.is_subcommander
        )

    # Unit Fluent Actions
    def move(self, target: Tuple[float, float, float]) -> None:
        if self._client:
            self._client.move([self.id], target)

    def attack_move(self, target: Tuple[float, float, float]) -> None:
        if self._client:
            self._client.attack_move([self.id], target)

    def attack(self, target: Union[int, 'Unit']) -> None:
        if self._client:
            target_id = target.id if isinstance(target, Unit) else target
            self._client.attack([self.id], target_id)

    def guard(self, target: Union[int, 'Unit']) -> None:
        if self._client:
            target_id = target.id if isinstance(target, Unit) else target
            self._client.guard([self.id], target_id)

    def patrol(self, target: Tuple[float, float, float]) -> None:
        if self._client:
            self._client.patrol([self.id], target)

    def stop(self) -> None:
        if self._client:
            self._client.stop([self.id])

    def build(self, blueprint_id: str, target: Tuple[float, float, float]) -> None:
        if self._client:
            self._client.build(self.id, blueprint_id, target)

    def queue(self, blueprint_id: str, count: int = 1) -> None:
        if self._client:
            self._client.produce(self.id, blueprint_id, count)

    def upgrade(self, blueprint_id: str) -> None:
        if self._client:
            self._client.upgrade(self.id, blueprint_id)

    def enhance(self, enhancement_name: str) -> None:
        if self._client:
            self._client.enhance(self.id, enhancement_name)

    def reclaim(self, target: Optional[Tuple[float, float, float]] = None, target_id: Optional[int] = None) -> None:
        if self._client:
            self._client.reclaim(self.id, target=target, target_id=target_id)

    def overcharge(self, target: Tuple[float, float, float]) -> None:
        if self._client:
            self._client.overcharge(self.id, target)


@dataclass
class GameState:
    step: int
    army_index: int
    time: float
    tick: int
    speed: float
    is_over: bool
    map_width: float
    map_height: float
    economy: EconomyState
    units: Dict[int, Unit] = field(default_factory=dict)
    enemies: Dict[int, Unit] = field(default_factory=dict)
    mass_spots: List[MassSpot] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], client: Optional[Any] = None) -> 'GameState':
        econ_data = data.get("economy", {})
        mass_data = econ_data.get("mass", {})
        energy_data = econ_data.get("energy", {})

        econ = EconomyState(
            mass=ResourceRate(
                stored=float(mass_data.get("stored", 0.0)),
                capacity=float(mass_data.get("capacity", 0.0)),
                income=float(mass_data.get("income", 0.0)),
                usage=float(mass_data.get("usage", 0.0)),
                requested=float(mass_data.get("requested", 0.0)),
                trend=float(mass_data.get("trend", 0.0))
            ),
            energy=ResourceRate(
                stored=float(energy_data.get("stored", 0.0)),
                capacity=float(energy_data.get("capacity", 0.0)),
                income=float(energy_data.get("income", 0.0)),
                usage=float(energy_data.get("usage", 0.0)),
                requested=float(energy_data.get("requested", 0.0)),
                trend=float(energy_data.get("trend", 0.0))
            )
        )

        units = {}
        for u in data.get("units", []):
            uid = int(u["id"])
            pos = tuple(float(x) for x in u.get("pos", [0, 0, 0]))
            units[uid] = Unit(
                id=uid,
                blueprint_id=u.get("bp", ""),
                position=(pos[0], pos[1] if len(pos) > 1 else 0.0, pos[2] if len(pos) > 2 else 0.0),
                health=float(u.get("hp", 0.0)),
                max_health=float(u.get("max_hp", 1.0)),
                fraction_complete=float(u.get("fraction", 1.0)),
                tags=u.get("tags", []),
                mass_in=float(u.get("mass_in", 0.0)),
                mass_out=float(u.get("mass_out", 0.0)),
                energy_in=float(u.get("energy_in", 0.0)),
                energy_out=float(u.get("energy_out", 0.0)),
                build_rate=float(u.get("build_rate", 0.0)),
                fuel=float(u.get("fuel", 1.0)),
                _client=client
            )

        enemies = {}
        for e in data.get("enemies", []):
            eid = int(e["id"])
            pos = tuple(float(x) for x in e.get("pos", [0, 0, 0]))
            enemies[eid] = Unit(
                id=eid,
                blueprint_id=e.get("bp", ""),
                position=(pos[0], pos[1] if len(pos) > 1 else 0.0, pos[2] if len(pos) > 2 else 0.0),
                health=float(e.get("hp", 0.0)),
                max_health=float(e.get("max_hp", 1.0)),
                fraction_complete=1.0,
                tags=e.get("tags", []),
                _client=client
            )

        mass_spots = []
        for ms in data.get("mass_spots", []):
            mass_spots.append(MassSpot(
                x=float(ms.get("x", 0.0)),
                z=float(ms.get("z", 0.0)),
                status=ms.get("status", "free")
            ))

        map_info = data.get("map", {})
        return cls(
            step=int(data.get("step", 0)),
            army_index=int(data.get("army_index", 1)),
            time=float(data.get("game_time", 0.0)),
            tick=int(data.get("game_tick", 0)),
            speed=float(data.get("game_speed", 1.0)),
            is_over=bool(data.get("is_over", False)),
            map_width=float(map_info.get("width", 512.0)),
            map_height=float(map_info.get("height", 512.0)),
            economy=econ,
            units=units,
            enemies=enemies,
            mass_spots=mass_spots
        )

    # Convenience Query Helpers
    def get_commander(self) -> Optional[Unit]:
        """Finds the Armored Command Unit (ACU)."""
        for u in self.units.values():
            if u.is_commander and u.is_alive:
                return u
        return None

    def get_subcommanders(self) -> List[Unit]:
        """Returns all Support Commander (SACU) units."""
        return [u for u in self.units.values() if u.is_subcommander and u.is_alive]

    def get_engineers(self) -> List[Unit]:
        """Returns all friendly engineer units."""
        return [u for u in self.units.values() if u.is_engineer and u.is_alive]

    def get_factories(self, category: Optional[str] = None) -> List[Unit]:
        """Returns all friendly factories, optionally filtered by 'LAND', 'AIR', 'NAVAL'."""
        factories = [u for u in self.units.values() if u.is_factory and u.is_alive]
        if category:
            factories = [u for u in factories if category.upper() in u.tags]
        return factories

    def get_combat_units(self, category: Optional[str] = None) -> List[Unit]:
        """Returns all mobile combat units, optionally filtered by 'LAND', 'AIR', 'NAVAL'."""
        units = [u for u in self.units.values() if u.is_combat and u.is_alive]
        if category:
            units = [u for u in units if category.upper() in u.tags]
        return units

    def get_experimentals(self) -> List[Unit]:
        """Returns all experimental units and structures."""
        return [u for u in self.units.values() if u.is_experimental and u.is_alive]

    def get_radars(self) -> List[Unit]:
        """Returns all radar, sonar, and omni sensory structures."""
        return [u for u in self.units.values() if u.is_radar and u.is_alive]

    def get_nearest_free_mex(self, from_pos: Tuple[float, float, float]) -> Optional[MassSpot]:
        """Finds the closest unoccupied mass deposit to a given coordinate."""
        free_spots = [s for s in self.mass_spots if s.is_free]
        if not free_spots:
            return None
        return min(free_spots, key=lambda s: math.hypot(s.x - from_pos[0], s.z - from_pos[2]))

    def get_enemy_units(self) -> List[Unit]:
        """Returns all spotted enemy units."""
        return list(self.enemies.values())

    def get_threat_center(self) -> Optional[Tuple[float, float, float]]:
        """Calculates center of mass of visible enemy units."""
        if not self.enemies:
            return None
        avg_x = sum(e.position[0] for e in self.enemies.values()) / len(self.enemies)
        avg_z = sum(e.position[2] for e in self.enemies.values()) / len(self.enemies)
        return (avg_x, 0.0, avg_z)
