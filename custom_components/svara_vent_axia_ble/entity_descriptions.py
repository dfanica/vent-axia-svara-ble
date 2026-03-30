"""Typed entity description models for the Vent-Axia Svara integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.helpers.entity import EntityCategory


@dataclass(frozen=True, slots=True)
class BaseSvaraEntityDescription:
    """Common entity description fields."""

    key: str
    entity_name: str
    translation_key: str | None = None
    category: EntityCategory | None = None
    icon: str | None = None


@dataclass(frozen=True, slots=True)
class SensorDescription(BaseSvaraEntityDescription):
    """Sensor entity description."""

    units: str | None = None
    device_class: str | None = None


@dataclass(frozen=True, slots=True)
class AttributeDescription:
    """Description for an extra state attribute."""

    key: str
    descriptor: str
    unit: str


@dataclass(frozen=True, slots=True)
class SwitchDescription(BaseSvaraEntityDescription):
    """Switch entity description."""

    attributes: AttributeDescription | None = None


@dataclass(frozen=True, slots=True)
class NumberRange:
    """Number range options."""

    min_value: float
    max_value: float
    step: float


@dataclass(frozen=True, slots=True)
class NumberDescription(BaseSvaraEntityDescription):
    """Number entity description."""

    units: str | None = None
    device_class: str | None = None
    options: NumberRange | None = None


@dataclass(frozen=True, slots=True)
class SelectDescription(BaseSvaraEntityDescription):
    """Select entity description."""

    options: dict[str, str] | None = None


@dataclass(frozen=True, slots=True)
class ButtonDescription(BaseSvaraEntityDescription):
    """Button entity description."""

    action: str = ""
