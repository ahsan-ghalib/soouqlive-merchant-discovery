"""City-wide Places coverage plans (multi-query + geo grid).

Google Text Search soft-caps ~60 unique results per single query.
To cover a whole city we fan out: districts/areas × keywords × geo cells,
then dedupe by place_id in the provider/CRM layer.

This is paid Places API coverage — not Maps HTML scraping.
"""

from __future__ import annotations

from typing import Any, Optional

# Known district lists (expand over time)
CITY_DISTRICTS: dict[str, list[str]] = {
    "riyadh": [
        # Central / north core
        "Olaya",
        "Al Malaz",
        "Al Sulimaniyah",
        "Al Murabba",
        "Al Wurud",
        "Al Olaya",
        "King Fahd District",
        "King Abdullah Financial District",
        "Diplomatic Quarter",
        "Al Mohammadiyah",
        "Al Muhammadiyah",
        "Al Nakheel",
        "Al Yasmin",
        "Al Sahafa",
        "Al Rawdah",
        "Al Hamra",
        "Al Narjis",
        "Al Aqiq",
        "Al Rabwah",
        "Hittin",
        "Al Izdihar",
        "Al Qirawan",
        "Al Arid",
        "Al Nada",
        "Al Majd",
        "Al Wadi",
        "Al Ghadir",
        "Al Nafel",
        "Al Malqa",
        "Al Qadsiah",
        "Al Raed",
        "Al Safarat",
        "Al Taawun",
        "Al Mughrizat",
        "Al Falah",
        "Al Manar",
        "Al Nuzha",
        "Al Mursalat",
        "Al Andalus",
        "Al Khaleej",
        "Al Nadheem",
        "Al Yarmuk",
        "Al Munsiyah",
        "Al Qadisiyah",
        "Al Hamra",
        "Al Maather",
        "Al Nasim",
        "Al Naseem",
        "Al Rayyan",
        "Al Shifa",
        "Al Aziziyah",
        "Al Batha",
        "Diriyah",
        "Al Uraija",
        "Al Suwaidi",
        "Al Shifa",
        "Exit 5",
        "Exit 9",
        "Exit 10",
        "Exit 14",
        "Granada",
        "Al Munsiyah",
        "Tuwaiq",
        "Irqah",
        "Laban",
        "Dhahrat Laban",
        "Al Hazm",
        "Al Marwah",
        "Al Masif",
        "Al Nahda",
        "Al Fayha",
        "Al Jabrah",
        "Al Salam",
        "Al Jaradiyah",
        "Al Wisham",
        "Siyah",
        "Al Haer",
        "Al Mansourah",
        "Badr",
        "Okaz",
        "Al Shimaisi",
        "Al Shemaysi",
        "Al Amal",
        "Al Thumama",
        "Al Manakh",
        "Sultanah",
        "Al Dar Al Baida",
        "Al Khalidiyah",
        "Al Marqab",
        "Al Futah",
        "Al Deghairah",
    ],
    "jeddah": [
        "Al Balad",
        "Al Hamra",
        "Al Rawdah",
        "Al Zahra",
        "Al Salamah",
        "Obhur",
        "Al Corniche",
        "Al Andalus",
        "Al Naeem",
        "Al Khalidiyah",
        "Al Shati",
        "Al Marwah",
        "Al Basateen",
        "Al Safa",
        "Al Rehab",
        "Al Petromin",
        "Al Muhammadiyah",
        "Al Tilal",
        "Al Fayhaa",
        "Al Aziziyah",
    ],
    "dammam": [
        "Al Faisaliyah",
        "Al Shati",
        "Al Jalawiyah",
        "Al Adamah",
        "Al Anoud",
        "Corniche",
        "Al Jalawiyah",
        "Al Tubayshi",
        "Gharb Al Dammam",
    ],
    "khobar": [
        "Corniche",
        "Al Thuqbah",
        "Al Ulaya",
        "Al Rakah",
        "Al Bandariyah",
        "Al Aqrabiyah",
        "Al Khobar North",
    ],
}

# City centers for geo-grid (slug → lat, lng, default radius km)
CITY_CENTERS: dict[str, dict[str, float]] = {
    "riyadh": {"lat": 24.7136, "lng": 46.6753, "radius_km": 35},
    "jeddah": {"lat": 21.4858, "lng": 39.1925, "radius_km": 22},
    "dammam": {"lat": 26.4207, "lng": 50.0888, "radius_km": 18},
    "mecca": {"lat": 21.3891, "lng": 39.8579, "radius_km": 12},
    "medina": {"lat": 24.5247, "lng": 39.5692, "radius_km": 14},
    "khobar": {"lat": 26.2172, "lng": 50.1971, "radius_km": 12},
    "taif": {"lat": 21.2703, "lng": 40.4158, "radius_km": 12},
    "tabuk": {"lat": 28.3998, "lng": 36.5700, "radius_km": 12},
    "abha": {"lat": 18.2164, "lng": 42.5053, "radius_km": 10},
    "buraydah": {"lat": 26.3260, "lng": 43.9750, "radius_km": 12},
    "dubai": {"lat": 25.2048, "lng": 55.2708, "radius_km": 30},
    "abu dhabi": {"lat": 24.4539, "lng": 54.3773, "radius_km": 22},
    "doha": {"lat": 25.2854, "lng": 51.5310, "radius_km": 18},
    "kuwait city": {"lat": 29.3759, "lng": 47.9774, "radius_km": 16},
    "manama": {"lat": 26.2235, "lng": 50.5876, "radius_km": 10},
    "muscat": {"lat": 23.5880, "lng": 58.3829, "radius_km": 18},
    "amman": {"lat": 31.9539, "lng": 35.9106, "radius_km": 16},
    "cairo": {"lat": 30.0444, "lng": 31.2357, "radius_km": 25},
    "london": {"lat": 51.5074, "lng": -0.1278, "radius_km": 20},
}

# Broad food keywords for SA / GCC Places Text Search
RESTAURANT_KEYWORDS: list[str] = [
    "restaurant",
    "مطعم",
    "مطاعم",
    "cafe",
    "كافيه",
    "coffee shop",
    "bakery",
    "مخبز",
    "fast food",
    "وجبات سريعة",
    "shawarma",
    "شاورما",
    "mandi",
    "مندي",
    "kabsa",
    "كبسة",
    "bukhari",
    "بخاري",
    "grill",
    "مشويات",
    "burger",
    "برجر",
    "pizza",
    "بيتزا",
    "seafood restaurant",
    "مأكولات بحرية",
    "indian restaurant",
    "مطعم هندي",
    "chinese restaurant",
    "مطعم صيني",
    "italian restaurant",
    "مطعم ايطالي",
    "lebanese restaurant",
    "مطعم لبناني",
    "syrian restaurant",
    "مطعم سوري",
    "turkish restaurant",
    "مطعم تركي",
    "japanese restaurant",
    "sushi",
    "steakhouse",
    "steak house",
    "fried chicken",
    "دجاج",
    "broasted",
    "falafel",
    "فلافل",
    "hummus",
    "kitchen",
    "dining",
    "food court",
    "مطعم شعبي",
    "traditional restaurant",
    "family restaurant",
    "مطعم عائلي",
    "breakfast restaurant",
    "فطور",
    "dessert shop",
    "حلويات",
    "juice bar",
    "عصيرات",
    "ice cream",
    "آيس كريم",
]

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "restaurants": RESTAURANT_KEYWORDS,
    "cafes": [
        "cafe",
        "كافيه",
        "coffee shop",
        "قهوة",
        "specialty coffee",
        "roastery",
        "bakery",
        "مخبز",
        "dessert cafe",
        "juice bar",
        "عصيرات",
        "tea house",
        "شاي",
    ],
    "all": [
        "restaurant",
        "مطعم",
        "cafe",
        "store",
        "shop",
        "supermarket",
        "pharmacy",
        "clinic",
        "hospital",
        "hotel",
        "gym",
        "salon",
        "barber",
        "bakery",
        "real estate agency",
        "car repair",
        "electronics store",
        "clothing store",
        "school",
        "bank",
        "gas station",
        "laundry",
        "florist",
    ],
    "real-estate": ["real estate agency", "property office", "مكتب عقاري"],
    "pharmacies": ["pharmacy", "drugstore", "صيدلية"],
}

# Legacy aliases used by older sweep UI
RIYADH_DISTRICTS = CITY_DISTRICTS["riyadh"]
RESTAURANT_CUISINES = CATEGORY_KEYWORDS["restaurants"]


def _slug(name: str) -> str:
    return (name or "").strip().lower()


def _dedupe_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = (item or "").strip()
        if not key:
            continue
        low = key.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(key)
    return out


def resolve_city_center(
    city: str,
    *,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    radius_km: Optional[float] = None,
) -> dict[str, float]:
    if latitude is not None and longitude is not None:
        return {
            "lat": float(latitude),
            "lng": float(longitude),
            "radius_km": float(radius_km or 20),
        }
    known = CITY_CENTERS.get(_slug(city))
    if known:
        return dict(known)
    # Unknown city — caller should pass lat/lng from DB; fallback mild default
    return {"lat": 24.7136, "lng": 46.6753, "radius_km": float(radius_km or 20)}


def _grid_cells(center: dict[str, float], grid: int = 5) -> list[dict[str, float]]:
    """Build overlapping circle centers around the city (approx degrees)."""
    import math

    lat0 = center["lat"]
    lng0 = center["lng"]
    radius_km = center.get("radius_km", 20)
    # span the city diameter with grid×grid cells
    step_km = (radius_km * 2) / max(grid, 1)
    cell_radius_m = max(2000.0, (step_km * 1000) * 0.7)
    dlat = step_km / 111.0
    cos_lat = max(math.cos(math.radians(lat0)), 0.2)
    dlng = step_km / (111.0 * cos_lat)

    half = (grid - 1) / 2
    cells: list[dict[str, float]] = []
    for i in range(grid):
        for j in range(grid):
            cells.append(
                {
                    "lat": lat0 + (i - half) * dlat,
                    "lng": lng0 + (j - half) * dlng,
                    "radius_m": min(cell_radius_m, 50000.0),
                }
            )
    return cells


def _append_plan(
    plan: list[dict[str, Any]],
    *,
    text: str,
    keyword: str,
    area: str,
    limit: int,
    location_bias: Optional[dict[str, float]],
) -> None:
    plan.append(
        {
            "text": text,
            "keyword": keyword,
            "area": area,
            "limit": limit,
            "location_bias": location_bias,
        }
    )


def build_coverage_queries(
    *,
    city: str = "Riyadh",
    category: str = "restaurants",
    mode: str = "districts",
    custom_areas: list[str] | None = None,
    custom_keywords: list[str] | None = None,
) -> list[dict[str, str]]:
    """Legacy multi-job sweep helper (district / cuisine text queries)."""
    areas = custom_areas or CITY_DISTRICTS.get(_slug(city), [city])
    keywords = custom_keywords or CATEGORY_KEYWORDS.get(
        category if category in CATEGORY_KEYWORDS else "restaurants",
        [category or "business"],
    )

    queries: list[dict[str, str]] = []
    if mode in {"districts", "full", "city_full"}:
        base_kw = keywords[0] if keywords else "business"
        for area in areas:
            queries.append(
                {
                    "name": f"{city} {area} {base_kw}",
                    "keyword": base_kw,
                    "area": area,
                    "text": f"{base_kw} in {area} {city}",
                }
            )
    if mode in {"cuisines", "full", "city_full"}:
        for kw in keywords:
            queries.append(
                {
                    "name": f"{city} {kw}",
                    "keyword": kw,
                    "area": city,
                    "text": f"{kw} in {city}",
                }
            )

    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for q in queries:
        key = q["text"].lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(q)
    return unique


def build_city_coverage_plan(
    *,
    city: str,
    country_code: str = "SA",
    category: str = "all",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    radius_km: Optional[float] = None,
    max_queries: int = 180,
    limit_per_query: int = 60,
    grid: int = 7,
    keywords: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Single-job full-city plan: districts × keywords + geo-grid.

    Each item:
      text, keyword, area, location_bias{lat,lng,radius_m}, limit
    """
    cat_key = category if category in CATEGORY_KEYWORDS else (
        "restaurants" if "restaurant" in (category or "").lower() else "all"
    )
    kws = _dedupe_preserve(
        keywords or CATEGORY_KEYWORDS.get(cat_key, CATEGORY_KEYWORDS["all"])
    )
    if not kws:
        kws = ["restaurant"]

    center = resolve_city_center(
        city, latitude=latitude, longitude=longitude, radius_km=radius_km
    )
    districts = _dedupe_preserve(CITY_DISTRICTS.get(_slug(city), []))
    is_food = cat_key in {"restaurants", "cafes"}
    primary = kws[0]
    # Prefer English "restaurant"/"cafe" as district primary when available
    for preferred in ("restaurant", "مطعم", "cafe", "كافيه"):
        if preferred in kws:
            primary = preferred
            break

    city_bias = {
        "lat": center["lat"],
        "lng": center["lng"],
        "radius_m": min(center["radius_km"] * 1000, 50000),
    }

    def _ar_text(kw: str, *, area: str, near: bool = False) -> str:
        arabicish = any("\u0600" <= ch <= "\u06FF" for ch in kw)
        if arabicish:
            if near:
                return f"{kw} قرب {area}"
            return f"{kw} في {area}"
        if near:
            return f"{kw} near {area}"
        return f"{kw} in {area} {city}" if area != city else f"{kw} in {city}"

    # Build layers separately, then interleave so a max_queries cap
    # never drops whole layers (old bug: districts alone ate the budget).
    layer_district_primary: list[dict[str, Any]] = []
    layer_city_keywords: list[dict[str, Any]] = []
    layer_grid: list[dict[str, Any]] = []
    layer_district_cuisine: list[dict[str, Any]] = []

    for area in districts:
        _append_plan(
            layer_district_primary,
            text=_ar_text(primary, area=area),
            keyword=primary,
            area=area,
            limit=limit_per_query,
            location_bias=None,
        )

    for kw in kws:
        _append_plan(
            layer_city_keywords,
            text=_ar_text(kw, area=city),
            keyword=kw,
            area=city,
            limit=limit_per_query,
            location_bias=city_bias,
        )

    cells = _grid_cells(center, grid=grid)
    strong = [primary] + [k for k in kws[1:12] if k != primary] if is_food else kws
    for idx, cell in enumerate(cells):
        kw = strong[idx % len(strong)]
        _append_plan(
            layer_grid,
            text=_ar_text(kw, area=city, near=True),
            keyword=kw,
            area=f"grid-{idx}",
            limit=limit_per_query,
            location_bias=cell,
        )

    if is_food and len(kws) > 1:
        secondary = [k for k in kws if k != primary]
        for idx, area in enumerate(districts):
            kw = secondary[idx % len(secondary)]
            _append_plan(
                layer_district_cuisine,
                text=_ar_text(kw, area=area),
                keyword=kw,
                area=area,
                limit=limit_per_query,
                location_bias=None,
            )

    # Round-robin merge: district → cuisine city → grid → district cuisine
    layers = [
        layer_district_primary,
        layer_city_keywords,
        layer_grid,
        layer_district_cuisine,
    ]
    pointers = [0] * len(layers)
    plan: list[dict[str, Any]] = []
    seen: set[str] = set()

    while len(plan) < max_queries and any(
        pointers[i] < len(layers[i]) for i in range(len(layers))
    ):
        progressed = False
        for i, layer in enumerate(layers):
            if len(plan) >= max_queries:
                break
            while pointers[i] < len(layer):
                item = layer[pointers[i]]
                pointers[i] += 1
                bias = item.get("location_bias") or {}
                key = (
                    f"{item['text']}|"
                    f"{round(bias.get('lat', 0), 3)}|"
                    f"{round(bias.get('lng', 0), 3)}"
                )
                if key in seen:
                    continue
                seen.add(key)
                item["country_code"] = country_code
                plan.append(item)
                progressed = True
                break
        if not progressed:
            break

    return plan
