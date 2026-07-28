"""Normalize bounded Agent network inventory and resolve its primary host address."""

from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass
from typing import Any

MAX_INTERFACES = 16
MAX_ADDRESSES_PER_INTERFACE = 8
MAX_ADDRESSES_PER_HOST = 32
MAX_RAW_INVENTORY_BYTES = 64 * 1024
NETWORK_INVENTORY_SCHEMA_VERSION = 1

_MAC_RE = re.compile(r"^(?:[0-9a-f]{2}:){5}[0-9a-f]{2}$")
_INTERFACE_TYPES = frozenset({"ethernet", "wifi", "vpn", "virtual", "unknown"})
_SELECTION_SOURCES = frozenset(
    {"route_to_control_plane", "default_route", "interface_fallback"}
)


@dataclass(frozen=True)
class NormalizedNetworkState:
    primary_ip_address: str | None
    primary_mac_address: str
    inventory: dict[str, Any] | None
    metadata_inventory: dict[str, Any]


def split_network_from_metadata(
    raw_metadata: object,
) -> tuple[dict[str, Any], NormalizedNetworkState]:
    """Return registration metadata without duplicating the dedicated network snapshot."""
    metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
    state = normalize_agent_network_state(metadata.get("inventory"))
    if isinstance(metadata.get("inventory"), dict):
        metadata["inventory"] = state.metadata_inventory
    return metadata, state


def normalize_agent_network_state(raw_inventory: object) -> NormalizedNetworkState:
    """Split compact network state from general Agent inventory and validate the primary IP."""
    inventory = dict(raw_inventory) if isinstance(raw_inventory, dict) else {}
    raw_network = inventory.pop("network_inventory", None)
    normalized_network = normalize_network_inventory(raw_network)

    primary = _normalize_usable_ip(inventory.get("primary_ip_address"))
    primary_mac = _normalize_mac(
        inventory.get("primary_mac_address") or inventory.get("mac_address")
    )
    announced = _normalize_legacy_addresses(inventory.get("ip_addresses"))
    if isinstance(inventory.get("ip_addresses"), list):
        inventory["ip_addresses"] = announced

    if normalized_network:
        selection = normalized_network["selection"]
        selected = str(selection.get("address") or "")
        if selected:
            primary = selected
        selected_interface = next(
            (
                item
                for item in normalized_network["interfaces"]
                if item["id"] == selection.get("interface_id")
            ),
            None,
        )
        if selected_interface is not None:
            primary_mac = str(selected_interface.get("mac_address") or "")
    if not normalized_network and primary:
        if announced and primary not in announced:
            primary = None

    if primary:
        inventory["primary_ip_address"] = primary
    else:
        inventory.pop("primary_ip_address", None)
    if primary_mac:
        inventory["mac_address"] = primary_mac
        inventory["primary_mac_address"] = primary_mac
    if normalized_network:
        inventory["primary_ip_source"] = normalized_network["selection"]["source"]
    return NormalizedNetworkState(
        primary_ip_address=primary,
        primary_mac_address=primary_mac,
        inventory=normalized_network,
        metadata_inventory=inventory,
    )


def normalize_network_inventory(raw: object) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    try:
        if (
            len(json.dumps(raw, separators=(",", ":"), default=str).encode("utf-8"))
            > MAX_RAW_INVENTORY_BYTES
        ):
            return None
    except (TypeError, ValueError):
        return None
    if _as_int(raw.get("schema_version")) != NETWORK_INVENTORY_SCHEMA_VERSION:
        return None

    interfaces: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    total_addresses = 0
    raw_interfaces = raw.get("interfaces")
    if not isinstance(raw_interfaces, list):
        return None
    for raw_interface in raw_interfaces:
        if (
            len(interfaces) >= MAX_INTERFACES
            or total_addresses >= MAX_ADDRESSES_PER_HOST
        ):
            break
        if not isinstance(raw_interface, dict):
            continue
        interface_id = _bounded_text(raw_interface.get("id"), 128)
        name = _bounded_text(raw_interface.get("name"), 200)
        if not interface_id or not name or interface_id in seen_ids:
            continue
        addresses: list[dict[str, Any]] = []
        seen_addresses: set[str] = set()
        raw_addresses = raw_interface.get("addresses")
        if not isinstance(raw_addresses, list):
            raw_addresses = []
        address_limit = min(
            MAX_ADDRESSES_PER_INTERFACE,
            MAX_ADDRESSES_PER_HOST - total_addresses,
        )
        for raw_address in raw_addresses:
            if len(addresses) >= address_limit:
                break
            if not isinstance(raw_address, dict):
                continue
            address = _normalize_usable_ip(raw_address.get("address"))
            if not address or address in seen_addresses:
                continue
            parsed = ipaddress.ip_address(address)
            prefix = _as_int(raw_address.get("prefix_length"))
            max_prefix = 32 if parsed.version == 4 else 128
            if prefix < 0 or prefix > max_prefix:
                prefix = 0
            seen_addresses.add(address)
            addresses.append(
                {
                    "address": address,
                    "family": "ipv4" if parsed.version == 4 else "ipv6",
                    "prefix_length": prefix,
                }
            )
        if not addresses:
            continue
        interface_type = _bounded_text(raw_interface.get("type"), 16).lower()
        if interface_type not in _INTERFACE_TYPES:
            interface_type = "unknown"
        seen_ids.add(interface_id)
        total_addresses += len(addresses)
        interfaces.append(
            {
                "id": interface_id,
                "name": name,
                "mac_address": _normalize_mac(raw_interface.get("mac_address")),
                "type": interface_type,
                "virtual": bool(raw_interface.get("virtual")),
                "default_route": bool(raw_interface.get("default_route")),
                "addresses": addresses,
            }
        )

    selection_raw = raw.get("selection")
    selection_raw = selection_raw if isinstance(selection_raw, dict) else {}
    selected_address = _normalize_usable_ip(selection_raw.get("address"))
    selected_interface_id = _bounded_text(selection_raw.get("interface_id"), 128)
    source = _bounded_text(selection_raw.get("source"), 32)
    if source not in _SELECTION_SOURCES:
        source = "interface_fallback"
    selected_interface = next(
        (item for item in interfaces if item["id"] == selected_interface_id),
        None,
    )
    if selected_interface is None or selected_address not in {
        item["address"] for item in selected_interface["addresses"]
    }:
        selected_address = ""
        selected_interface_id = ""
    if not selected_address and interfaces:
        selected_interface = interfaces[0]
        selected_address = selected_interface["addresses"][0]["address"]
        selected_interface_id = selected_interface["id"]
        source = "interface_fallback"

    family = ""
    if selected_address:
        family = (
            "ipv4" if ipaddress.ip_address(selected_address).version == 4 else "ipv6"
        )
    collected_at = _bounded_text(raw.get("collected_at"), 40)
    return {
        "schema_version": NETWORK_INVENTORY_SCHEMA_VERSION,
        "collected_at": collected_at,
        "selection": {
            "address": selected_address,
            "family": family,
            "interface_id": selected_interface_id,
            "source": source,
        },
        "interfaces": interfaces,
    }


def same_network_inventory(left: object, right: object) -> bool:
    """Compare topology while ignoring the collection timestamp."""
    if not isinstance(left, dict) or not isinstance(right, dict):
        return left == right
    left_value = {key: value for key, value in left.items() if key != "collected_at"}
    right_value = {key: value for key, value in right.items() if key != "collected_at"}
    return left_value == right_value


def _normalize_legacy_addresses(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for value in raw[:MAX_ADDRESSES_PER_HOST]:
        address = _normalize_usable_ip(value)
        if address and address not in seen:
            seen.add(address)
            result.append(address)
    return result


def _normalize_usable_ip(raw: object) -> str | None:
    try:
        address = ipaddress.ip_address(str(raw or "").strip())
    except ValueError:
        return None
    if (
        address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
    ):
        return None
    return address.compressed


def _normalize_mac(raw: object) -> str:
    value = str(raw or "").strip().lower().replace("-", ":")
    return value if _MAC_RE.fullmatch(value) and value != "00:00:00:00:00:00" else ""


def _bounded_text(raw: object, length: int) -> str:
    return str(raw or "").strip()[:length]


def _as_int(raw: object) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0
