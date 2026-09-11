"""The canonical list of part categories, seeded by `init_categories` on startup.

Add an entry to `PART_CATEGORIES` and the initialisation creates it.
"""

from typing import TypedDict, cast

from typing_extensions import NotRequired


class PartCategoryData(TypedDict):
    """Type definition for part category data."""

    name: str
    display_name: str
    description: NotRequired[str]
    icon: NotRequired[str]
    sort_order: int


PART_CATEGORIES: list[PartCategoryData] = [
    {
        "name": "exhaust",
        "display_name": "Exhaust Systems",
        "description": "Exhaust systems, mufflers, headers, and related components",
        "icon": "🔧",
        "sort_order": 1,
    },
    {
        "name": "suspension",
        "display_name": "Suspension",
        "description": "Coilovers, springs, struts, and suspension components",
        "icon": "📐",
        "sort_order": 2,
    },
    {
        "name": "engine",
        "display_name": "Engine Performance",
        "description": "Turbochargers, superchargers, intakes, and engine mods",
        "icon": "⚙️",
        "sort_order": 3,
    },
    {
        "name": "wheels",
        "display_name": "Wheels & Tires",
        "description": "Wheels, rims, tires, and wheel accessories",
        "icon": "🛞",
        "sort_order": 4,
    },
    {
        "name": "body",
        "display_name": "Body & Aero",
        "description": "Body kits, spoilers, splitters, and aerodynamic components",
        "icon": "🚗",
        "sort_order": 5,
    },
    {
        "name": "interior",
        "display_name": "Interior",
        "description": "Seats, steering wheels, shift knobs, and interior mods",
        "icon": "🪑",
        "sort_order": 6,
    },
    {
        "name": "brakes",
        "display_name": "Brakes",
        "description": "Brake pads, rotors, calipers, and brake systems",
        "icon": "🛑",
        "sort_order": 7,
    },
    {
        "name": "lighting",
        "display_name": "Lighting",
        "description": "Headlights, taillights, fog lights, DRL, LED, and lighting accessories",
        "icon": "💡",
        "sort_order": 8,
    },
    {
        "name": "drivetrain",
        "display_name": "Drivetrain",
        "description": "Differential, driveshaft, axles, clutch, transmission, and driveline",
        "icon": "⚙",
        "sort_order": 9,
    },
    {
        "name": "accessories",
        "display_name": "Accessories & Apparel",
        "description": "Apparel, badges, decals, license plate frames, keychains, detailing supplies",
        "icon": "🎽",
        "sort_order": 10,
    },
    {
        "name": "other",
        "display_name": "Other",
        "description": "Parts that don't fit other categories",
        "icon": "📦",
        "sort_order": 11,
    },
]


def get_all_part_categories() -> list[PartCategoryData]:
    """Every part category definition, as fresh dicts for seeding the database."""
    return cast(list[PartCategoryData], [dict(cat) for cat in PART_CATEGORIES])
