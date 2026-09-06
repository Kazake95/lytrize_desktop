"""modules/analysis/map_plot.py -- Geographic scatter / choropleth runner."""
from __future__ import annotations


import logging
import re
import unicodedata
from functools import lru_cache
from typing import Optional


import numpy as np
import pandas as pd
import plotly.express as px


from modules.charts import chart_layout, COLORS

log = logging.getLogger(__name__)


_MAP_SAMPLE = 5_000
_DENSITY_CELLS = 2_000


_CHOROPLETH_SCALES = [
    "Blues", "Viridis", "Plasma", "YlOrRd", "RdBu", "RdYlGn",
    "Cividis", "Magma", "Oranges", "Greens", "PuBu", "BuPu",
]


_PROJECTIONS = [
    "natural earth", "mercator", "equirectangular",
    "orthographic", "kavrayskiy7", "robinson",
]


_SCOPES = ["world", "usa", "europe", "asia", "africa", "north america", "south america"]


# The three user-facing base maps.  ALL of them render the same proven way:
# scatter_mapbox "white-bg" + a custom RASTER tile layer.  We deliberately do
# NOT use plotly's named vector styles (carto-positron etc.) -- the plotly.js
# bundled by the installed Streamlit (2.28.x, mapbox-gl fork) cannot load the
# vector GL style JSON they now serve, which produced the "API key needed"
# watermark.  Plain raster tiles have no keys, no watermarks and always work.
MAP_STYLES = ["OpenStreetMap (Light)", "OpenStreetMap (Dark)", "Satellite (Earth)"]

_MAP_DEFAULT = "OpenStreetMap (Light)"

# Raster tile templates per style.  All free, no API key.
_MAP_TILE_TEMPLATES = {
    "OpenStreetMap (Light)": [
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    ],
    "OpenStreetMap (Dark)": [  # Esri Dark Gray Canvas -- free, no key
        "https://server.arcgisonline.com/ArcGIS/rest/services/"
        "Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    ],
    "Satellite (Earth)": [  # Esri World Imagery -- free, no key
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
        "MapServer/tile/{z}/{y}/{x}",
    ],
}

# Free, key-less Esri reference layer that draws translucent country borders +
# place labels on top of any raster basemap.  Used to honour the "Borders" checkbox
# on the tile (scatter_mapbox) path, where the borders toggle is otherwise
# meaningless because they are baked into the base raster imagery.
_MAP_BORDERS_OVERLAY = [
    "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/"
    "World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
]


def _normalize_map_style(map_style) -> str:
    """Map any stored/legacy style value onto one of the three MAP_STYLES.

    Keeps older saved charts working: anything dark-ish -> Dark OSM,
    satellite/earth/terrain-ish -> Satellite, everything else -> Light OSM.
    """
    s = str(map_style or "").lower()
    if any(k in s for k in ("dark", "matter", "night", "moon")):
        return "OpenStreetMap (Dark)"
    if any(k in s for k in ("satellite", "earth", "terrain", "imagery", "esri")):
        return "Satellite (Earth)"
    return "OpenStreetMap (Light)"


_TILE_PROBE_HOSTS = (
    ("server.arcgisonline.com", 443),  # dark canvas + satellite tiles
    ("tile.openstreetmap.org", 443),   # light OSM raster tiles
)
_TILE_PROBE_TIMEOUT = 1.5
_tiles_online_cache: Optional[bool] = None


def _tiles_online() -> bool:
    """One-shot (cached) probe: are raster tile servers reachable?

    Tile basemaps are rendered client-side by plotly.js, so Python cannot know
    whether the browser can load them -- but if this machine can open a TCP
    connection to a tile host, the tiles will resolve too.  Falls back to the
    offline scatter_geo renderer when every host is unreachable.
    """
    global _tiles_online_cache
    if _tiles_online_cache is not None:
        return _tiles_online_cache
    import socket
    _online = False
    for host, port in _TILE_PROBE_HOSTS:
        try:
            with socket.create_connection((host, port), timeout=_TILE_PROBE_TIMEOUT):
                _online = True
                break
        except OSError:
            continue
    _tiles_online_cache = _online
    log.info("Tile basemap probe: online=%s", _online)
    return _online




def _norm(s: str) -> str:
    """Lowercase + strip accents + collapse whitespace."""
    nfkd = unicodedata.normalize("NFKD", s)
    ascii_s = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_s).strip().lower()




def _density_aggregate(
    df: pd.DataFrame,
    lat: str,
    lon: str,
    n_cells: int = _DENSITY_CELLS,
    extra_cols: Optional[list] = None,
    agg_overrides: Optional[dict] = None,
) -> pd.DataFrame:
    """Bin ALL points into a spatial grid and aggregate counts per cell.

    Uses the full dataset (no random sampling) so the spatial density
    pattern is accurate. Returns a small DataFrame (~n_cells rows) with
    mean lat/lon per cell and a '_count' column for colouring/sizing.
    ``extra_cols`` (e.g. the location / colour columns) are carried per
    cell using their most frequent value so hover tooltips keep showing
    meaningful labels instead of an empty box.  ``agg_overrides`` maps a
    column name to a pandas aggregation (e.g. {"is_fraud": "max"}) to
    replace the modal default — used so binary colour columns surface
    minority classes (any cell containing a 1 shows as 1).
    """
    lat_min, lat_max = float(df[lat].min()), float(df[lat].max())
    lon_min, lon_max = float(df[lon].min()), float(df[lon].max())

    # Guard against degenerate (single-point) bounds.
    if lat_max == lat_min:
        lat_max = lat_min + 1e-6
    if lon_max == lon_min:
        lon_max = lon_min + 1e-6

    # Aim for a roughly square grid: n_cells total, sqrt per axis.
    side = max(int(round(n_cells ** 0.5)), 1)
    lat_edges = np.linspace(lat_min, lat_max, side + 1)
    lon_edges = np.linspace(lon_min, lon_max, side + 1)

    lat_bin = np.clip(np.digitize(df[lat].values, lat_edges) - 1, 0, side - 1)
    lon_bin = np.clip(np.digitize(df[lon].values, lon_edges) - 1, 0, side - 1)
    cell_id = lat_bin * side + lon_bin

    def _modal(s: pd.Series):
        """Most frequent value in the cell (falls back to first)."""
        if s.empty:
            return None
        m = s.mode()
        return m.iat[0] if not m.empty else s.iloc[0]

    data = {"cell": cell_id, lat: df[lat].values, lon: df[lon].values}
    for c in (extra_cols or []):
        if c and c in df.columns and c not in data and c != "cell":
            data[c] = df[c].values
    agg = pd.DataFrame(data)
    agg_dict = {lat: (lat, "mean"), lon: (lon, "mean"), "_count": (lat, "size")}
    for c in (extra_cols or []):
        if c and c in df.columns and c not in agg_dict and c != "cell":
            agg_dict[c] = (c, _modal)
    for c, how in (agg_overrides or {}).items():
        if c in agg_dict:
            agg_dict[c] = (c, how)
    agg = agg.groupby("cell", as_index=False).agg(**agg_dict)
    return agg




@lru_cache(maxsize=1)
def _build_country_map() -> dict[str, str]:
    """Return {normalised_name_or_code: ISO-3166-1 alpha-3}."""
    try:
        import pycountry
    except ImportError:
        return {}
    mapping: dict[str, str] = {}
    for c in pycountry.countries:
        a3 = c.alpha_3
        mapping[_norm(c.name)]        = a3
        mapping[_norm(c.alpha_2)]     = a3
        mapping[_norm(c.alpha_3)]     = a3
        mapping[_norm(c.numeric)]     = a3
        if hasattr(c, "official_name"):
            mapping[_norm(c.official_name)] = a3
        if hasattr(c, "common_name"):
            mapping[_norm(c.common_name)]   = a3
    _ALIASES = {
        "usa": "USA", "us": "USA", "united states": "USA", "america": "USA",
        "uk": "GBR", "great britain": "GBR", "england": "GBR",
        "south korea": "KOR", "north korea": "PRK",
        "russia": "RUS", "iran": "IRN", "syria": "SYR",
        "taiwan": "TWN", "hong kong": "HKG", "macau": "MAC",
        "bolivia": "BOL", "venezuela": "VEN", "tanzania": "TZA",
        "vietnam": "VNM", "laos": "LAO",
        "czechia": "CZE", "czech republic": "CZE",
        "cape verde": "CPV", "ivory coast": "CIV", "cote d ivoire": "CIV",
        "congo": "COG", "dr congo": "COD", "democratic republic of the congo": "COD",
        "south africa": "ZAF", "new zealand": "NZL",
    }
    for alias, a3 in _ALIASES.items():
        mapping[alias] = a3
    return mapping




_US_STATES: dict[str, str] = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT",
    "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
    "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN",
    "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI",
    "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT",
    "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH",
    "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH",
    "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
    "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
    "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
    "District of Columbia": "DC", "Washington DC": "DC",
    "Puerto Rico": "PR",
}


def _build_us_state_map() -> dict[str, str]:
    """Return {normalised_name_or_abbr: US state ISO 3166-2 code e.g. 'US-CA'}."""
    mapping: dict[str, str] = {}
    for name, abbr in _US_STATES.items():
        mapping[_norm(name)] = f"US-{abbr}"
        mapping[_norm(abbr)] = f"US-{abbr}"
    return mapping


@lru_cache(maxsize=1)
def known_geo_display_names() -> list[str]:
    """Return a sorted list of canonical country + US state names.

    Used by UIs (e.g. the geo remap tool) to offer a validated,
    searchable set of names guaranteed to resolve via
    :func:`resolve_geo_names`, instead of free-text entry that may
    still fail to match.
    """
    names: list[str] = []
    try:
        import pycountry
        names.extend(c.name for c in pycountry.countries)
    except ImportError:
        pass
    names.extend(_US_STATES.keys())
    return sorted(set(names))




@lru_cache(maxsize=1)
def _build_world_regions_map() -> dict[str, tuple[float, float, str]]:
    """Return {normalised_region_name: (lat, lon, display_name)} for major world"""
    _REGIONS: dict[str, tuple[float, float]] = {
        "andhra pradesh": (15.9129, 79.7400), "arunachal pradesh": (28.2180, 94.7278),
        "assam": (26.2006, 92.9376), "bihar": (25.0961, 85.3131),
        "chhattisgarh": (21.2787, 81.8661), "goa": (15.2993, 74.1240),
        "gujarat": (22.2587, 71.1924), "haryana": (29.0588, 76.0856),
        "himachal pradesh": (31.1048, 77.1734), "jharkhand": (23.6102, 85.2799),
        "karnataka": (15.3173, 75.7139), "kerala": (10.8505, 76.2711),
        "madhya pradesh": (22.9734, 78.6569), "maharashtra": (19.7515, 75.7139),
        "manipur": (24.6637, 93.9063), "meghalaya": (25.4670, 91.3662),
        "mizoram": (23.1645, 92.9376), "nagaland": (26.1584, 94.5624),
        "odisha": (20.9517, 85.0985), "punjab": (31.1471, 75.3412),
        "rajasthan": (27.0238, 74.2179), "sikkim": (27.5330, 88.5122),
        "tamil nadu": (11.1271, 78.6569), "telangana": (18.1124, 79.0193),
        "tripura": (23.9408, 91.9882), "uttar pradesh": (26.8467, 80.9462),
        "uttarakhand": (30.0668, 79.0193), "west bengal": (22.9868, 87.8550),
        "delhi": (28.7041, 77.1025), "jammu and kashmir": (33.7782, 76.5762),
        "ladakh": (34.2268, 77.5619), "puducherry": (11.9416, 79.8083),
        "ontario": (51.2538, -85.3232), "quebec": (53.0000, -70.0000),
        "british columbia": (53.7267, -127.6476), "alberta": (53.9333, -116.5765),
        "manitoba": (53.7609, -98.8139), "saskatchewan": (52.9399, -106.4509),
        "nova scotia": (44.6820, -63.7443), "new brunswick": (46.5653, -66.4619),
        "newfoundland and labrador": (53.1355, -57.6604),
        "prince edward island": (46.5107, -63.4168),
        "northwest territories": (64.8255, -124.8457),
        "nunavut": (70.2998, -83.1076), "yukon": (64.2823, -135.0000),
        "new south wales": (-31.2532, 146.9211), "victoria": (-36.9848, 143.3906),
        "queensland": (-22.5750, 144.0848), "western australia": (-25.0000, 122.0000),
        "south australia": (-30.0002, 136.2092), "tasmania": (-42.0409, 146.8087),
        "northern territory": (-19.4914, 132.5510),
        "australian capital territory": (-35.4735, 149.0124),
        "bavaria": (48.7904, 11.4979), "north rhine-westphalia": (51.4332, 7.6616),
        "baden-wurttemberg": (48.6616, 9.3501), "lower saxony": (52.6367, 9.8451),
        "hesse": (50.6521, 9.1624), "saxony": (51.1045, 13.2017),
        "rhineland-palatinate": (50.1183, 7.3085), "saxony-anhalt": (51.8965, 11.6903),
        "thuringia": (51.0099, 10.8454), "berlin": (52.5200, 13.4050),
        "hamburg": (53.5753, 10.0153), "schleswig-holstein": (54.2194, 9.6961),
        "mecklenburg-vorpommern": (53.6127, 12.4295),
        "brandenburg": (52.4125, 12.5316), "bremen": (53.0793, 8.8017),
        "saarland": (49.3964, 7.0228),
        "guangdong": (23.3790, 113.7633), "shandong": (36.6683, 117.0206),
        "henan": (33.8820, 113.6145), "sichuan": (30.6171, 102.7103),
        "jiangsu": (32.9711, 119.4550), "hebei": (38.0428, 114.5149),
        "hunan": (27.6104, 111.7088), "anhui": (30.6006, 117.9253),
        "hubei": (30.9756, 112.2707), "zhejiang": (29.1832, 120.0934),
        "fujian": (26.0789, 117.9874), "yunnan": (24.4753, 101.3431),
        "shanxi": (37.5777, 112.2922), "liaoning": (41.2956, 122.6085),
        "shaanxi": (35.1917, 108.8701), "jiangxi": (27.0961, 114.9042),
        "guangxi": (23.7248, 108.6682), "inner mongolia": (43.3756, 115.9772),
        "guizhou": (26.8154, 106.8748), "chongqing": (29.5630, 106.5516),
        "xinjiang": (41.1129, 85.2401), "gansu": (35.7521, 104.9860),
        "heilongjiang": (47.3014, 128.7346), "jilin": (43.8378, 126.5497),
        "beijing": (39.9042, 116.4074), "shanghai": (31.2304, 121.4737),
        "tianjin": (39.3434, 117.3616), "tibet": (29.6465, 91.1171),
        "hainan": (19.5697, 109.9497), "qinghai": (35.7452, 95.9956),
        "ningxia": (37.1987, 106.1582),
        "sao paulo": (-23.5505, -46.6333), "minas gerais": (-18.5122, -44.5550),
        "rio de janeiro": (-22.9068, -43.1729), "bahia": (-12.9714, -38.5014),
        "parana": (-25.4195, -49.2646), "rio grande do sul": (-30.0346, -51.2177),
        "pernambuco": (-8.0578, -34.8829), "ceara": (-3.7172, -38.5434),
        "para": (-1.4558, -48.4902), "maranhao": (-2.5297, -44.3028),
        "amazonas": (-3.1190, -60.0217), "goias": (-16.6864, -49.2643),
        "espirito santo": (-20.3155, -40.3128), "mato grosso": (-12.6819, -56.9211),
        "jalisco": (20.6595, -103.3494), "nuevo leon": (25.5922, -99.9962),
        "estado de mexico": (19.2965, -99.6547), "chihuahua": (28.6353, -106.0889),
        "veracruz": (19.1738, -96.1342), "puebla": (19.0414, -98.2063),
        "guerrero": (17.4392, -100.0000), "oaxaca": (17.0732, -96.7266),
        "sonora": (29.2972, -110.3309), "baja california": (30.8406, -115.2838),
        "tamaulipas": (24.2669, -98.8363), "sinaloa": (25.1721, -107.4795),
        "coahuila": (27.0587, -101.7068), "michoacan": (19.5665, -101.7068),
        "guanajuato": (21.0190, -101.2574),
        "england": (52.3555, -1.1743), "scotland": (56.4907, -4.2026),
        "wales": (52.1307, -3.7837), "northern ireland": (54.7877, -6.4923),
        "london": (51.5074, -0.1278), "yorkshire": (53.9591, -1.0815),
        "lancashire": (53.7632, -2.7044), "midlands": (52.4862, -1.8904),
    }
    result: dict[str, tuple[float, float, str]] = {}
    for name, (lat, lon) in _REGIONS.items():
        display = name.title()
        result[_norm(name)] = (lat, lon, display)
        for suffix in (" state", " province", " territory", " region"):
            if name.endswith(suffix):
                result[_norm(name[: -len(suffix)])] = (lat, lon, display)
    return result




_CITY_COORDS: dict[str, tuple[float, float]] = {
    "tokyo": (35.6762, 139.6503), "delhi": (28.7041, 77.1025),
    "new delhi": (28.6139, 77.2090), "shanghai": (31.2304, 121.4737),
    "beijing": (39.9042, 116.4074), "mumbai": (19.0760, 72.8777),
    "dhaka": (23.8103, 90.4125), "osaka": (34.6937, 135.5023),
    "karachi": (24.8607, 67.0011), "chongqing": (29.5630, 106.5516),
    "istanbul": (41.0082, 28.9784), "kolkata": (22.5726, 88.3639),
    "manila": (14.5995, 120.9842), "tianjin": (39.1422, 117.1767),
    "guangzhou": (23.1291, 113.2644), "lahore": (31.5497, 74.3436),
    "bangalore": (12.9716, 77.5946), "shenzhen": (22.5431, 114.0579),
    "seoul": (37.5665, 126.9780), "jakarta": (6.2088, 106.8456),
    "chennai": (13.0827, 80.2707), "bangkok": (13.7563, 100.5018),
    "hyderabad": (17.3850, 78.4867), "kuala lumpur": (3.1390, 101.6869),
    "singapore": (1.3521, 103.8198), "ho chi minh city": (10.8231, 106.6297),
    "hong kong": (22.3193, 114.1694), "taipei": (25.0330, 121.5654),
    "yangon": (16.8661, 96.1951), "tehran": (35.6892, 51.3890),
    "riyadh": (24.7136, 46.6753), "baghdad": (33.3152, 44.3661),
    "dubai": (25.2048, 55.2708), "abu dhabi": (24.4539, 54.3773),
    "kabul": (34.5553, 69.2075), "kathmandu": (27.7172, 85.3240),
    "colombo": (6.9271, 79.8612), "tashkent": (41.2995, 69.2401),
    "almaty": (43.2220, 76.8512), "baku": (40.4093, 49.8671),
    "tbilisi": (41.6938, 44.8015), "yerevan": (40.1872, 44.5152),
    "pune": (18.5204, 73.8567), "ahmedabad": (23.0225, 72.5714),
    "surat": (21.1702, 72.8311), "jaipur": (26.9124, 75.7873),
    "lucknow": (26.8467, 80.9462), "kanpur": (26.4499, 80.3319),
    "nagpur": (21.1458, 79.0882), "patna": (25.5941, 85.1376),
    "bhopal": (23.2599, 77.4126), "agra": (27.1767, 78.0081),
    "visakhapatnam": (17.6868, 83.2185), "kochi": (9.9312, 76.2673),
    "wuhan": (30.5928, 114.3055), "hangzhou": (30.2741, 120.1551),
    "chengdu": (30.5723, 104.0665), "nanjing": (32.0603, 118.7969),
    "xi'an": (34.3416, 108.9398), "harbin": (45.8038, 126.5340),
    "zhengzhou": (34.7466, 113.6253), "shenyang": (41.8057, 123.4315),
    "qingdao": (36.0671, 120.3826), "foshan": (23.0219, 113.1216),
    "hanoi": (21.0285, 105.8542), "phnom penh": (11.5564, 104.9282),
    "vientiane": (17.9757, 102.6331), "kuching": (1.5497, 110.3630),
    "cebu": (10.3157, 123.8854), "davao": (7.0707, 125.6087),
    "surabaya": (7.2575, 112.7521), "medan": (3.5952, 98.6722),
    "bandung": (6.9175, 107.6191), "palembang": (2.9761, 104.7754),
    "makassar": (5.1477, 119.4327), "yangon": (16.8661, 96.1951),
    "naypyidaw": (19.7633, 96.0785),
    "london": (51.5074, -0.1278), "paris": (48.8566, 2.3522),
    "berlin": (52.5200, 13.4050), "madrid": (40.4168, -3.7038),
    "rome": (41.9028, 12.4964), "amsterdam": (52.3676, 4.9041),
    "brussels": (50.8503, 4.3517), "vienna": (48.2082, 16.3738),
    "warsaw": (52.2297, 21.0122), "budapest": (47.4979, 19.0402),
    "prague": (50.0755, 14.4378), "stockholm": (59.3293, 18.0686),
    "oslo": (59.9139, 10.7522), "copenhagen": (55.6761, 12.5683),
    "helsinki": (60.1699, 24.9384), "zurich": (47.3769, 8.5417),
    "geneva": (46.2044, 6.1432), "milan": (45.4654, 9.1859),
    "barcelona": (41.3851, 2.1734), "munich": (48.1351, 11.5820),
    "frankfurt": (50.1109, 8.6821), "hamburg": (53.5753, 10.0153),
    "cologne": (50.9333, 6.9500), "athens": (37.9838, 23.7275),
    "bucharest": (44.4268, 26.1025), "sofia": (42.6977, 23.3219),
    "zagreb": (45.8150, 15.9819), "belgrade": (44.7866, 20.4489),
    "kyiv": (50.4501, 30.5234), "moscow": (55.7558, 37.6173),
    "saint petersburg": (59.9311, 30.3609), "minsk": (53.9045, 27.5615),
    "riga": (56.9460, 24.1059), "tallinn": (59.4370, 24.7536),
    "vilnius": (54.6872, 25.2797), "lisbon": (38.7223, -9.1393),
    "porto": (41.1579, -8.6291), "seville": (37.3891, -5.9845),
    "valencia": (39.4699, -0.3763), "dubrovnik": (42.6507, 18.0944),
    "luxembourg": (49.6117, 6.1319), "reykjavik": (64.1466, -21.9426),
    "dublin": (53.3498, -6.2603), "edinburgh": (55.9533, -3.1883),
    "new york": (40.7128, -74.0060), "los angeles": (34.0522, -118.2437),
    "chicago": (41.8781, -87.6298), "houston": (29.7604, -95.3698),
    "phoenix": (33.4484, -112.0740), "philadelphia": (39.9526, -75.1652),
    "san antonio": (29.4241, -98.4936), "san diego": (32.7157, -117.1611),
    "dallas": (32.7767, -96.7970), "san jose": (37.3382, -121.8863),
    "austin": (30.2672, -97.7431), "jacksonville": (30.3322, -81.6557),
    "san francisco": (37.7749, -122.4194), "columbus": (39.9612, -82.9988),
    "charlotte": (35.2271, -80.8431), "indianapolis": (39.7684, -86.1581),
    "seattle": (47.6062, -122.3321), "denver": (39.7392, -104.9903),
    "washington": (38.9072, -77.0369), "washington dc": (38.9072, -77.0369),
    "boston": (42.3601, -71.0589), "nashville": (36.1627, -86.7816),
    "las vegas": (36.1699, -115.1398), "miami": (25.7617, -80.1918),
    "atlanta": (33.7490, -84.3880), "minneapolis": (44.9778, -93.2650),
    "portland": (45.5051, -122.6750), "detroit": (42.3314, -83.0458),
    "toronto": (43.6532, -79.3832), "montreal": (45.5017, -73.5673),
    "vancouver": (49.2827, -123.1207), "calgary": (51.0447, -114.0719),
    "edmonton": (53.5461, -113.4938), "ottawa": (45.4215, -75.6972),
    "winnipeg": (49.8951, -97.1384), "quebec city": (46.8139, -71.2080),
    "mexico city": (19.4326, -99.1332), "guadalajara": (20.6597, -103.3496),
    "monterrey": (25.6866, -100.3161), "puebla": (19.0414, -98.2063),
    "sao paulo": (-23.5505, -46.6333), "rio de janeiro": (-22.9068, -43.1729),
    "brasilia": (-15.7942, -47.8825), "salvador": (-12.9714, -38.5014),
    "fortaleza": (-3.7172, -38.5434), "belo horizonte": (-19.9167, -43.9333),
    "manaus": (-3.1190, -60.0217), "curitiba": (-25.4278, -49.2731),
    "recife": (-8.0578, -34.8829), "porto alegre": (-30.0346, -51.2177),
    "buenos aires": (-34.6037, -58.3816), "cordoba": (-31.4201, -64.1888),
    "rosario": (-32.9587, -60.6930), "lima": (-12.0464, -77.0428),
    "bogota": (4.7110, -74.0721), "medellin": (6.2442, -75.5812),
    "cali": (3.4516, -76.5320), "santiago": (-33.4489, -70.6693),
    "caracas": (10.4806, -66.9036), "quito": (-0.1807, -78.4678),
    "la paz": (-16.5000, -68.1500), "asuncion": (-25.2637, -57.5759),
    "montevideo": (-34.9011, -56.1645), "havana": (23.1136, -82.3666),
    "kingston": (17.9970, -76.7936), "port-au-prince": (18.5425, -72.3386),
    "cairo": (30.0444, 31.2357), "lagos": (6.5244, 3.3792),
    "kinshasa": (-4.4419, 15.2663), "luanda": (-8.8368, 13.2343),
    "dar es salaam": (-6.7924, 39.2083), "johannesburg": (-26.2041, 28.0473),
    "abidjan": (5.3600, -4.0083), "khartoum": (15.5007, 32.5599),
    "algiers": (36.7372, 3.0865), "casablanca": (33.5731, -7.5898),
    "cape town": (-33.9249, 18.4241), "addis ababa": (9.0320, 38.7469),
    "nairobi": (-1.2921, 36.8219), "accra": (5.6037, -0.1870),
    "antananarivo": (-18.9137, 47.5361), "yaounde": (3.8480, 11.5021),
    "douala": (4.0500, 9.7000), "dakar": (14.7167, -17.4677),
    "bamako": (12.6392, -8.0029), "conakry": (9.5370, -13.6773),
    "maputo": (-25.9692, 32.5732), "lusaka": (-15.4167, 28.2833),
    "harare": (-17.8292, 31.0522), "kampala": (0.3476, 32.5825),
    "kigali": (-1.9441, 30.0619), "tunis": (36.8065, 10.1815),
    "tripoli": (32.9020, 13.1805), "mogadishu": (2.0469, 45.3182),
    "ndjamena": (12.1048, 15.0440), "bangui": (4.3612, 18.5550),
    "brazzaville": (-4.2694, 15.2712), "libreville": (0.3901, 9.4544),
    "malabo": (3.7500, 8.7833), "porto-novo": (6.3659, 2.4183),
    "lome": (6.1228, 1.2255), "niamey": (13.5137, 2.1098),
    "ouagadougou": (12.3647, -1.5339), "freetown": (8.4857, -13.2317),
    "monrovia": (6.2907, -10.7605), "abuja": (9.0579, 7.4951),
    "addis ababa": (9.0320, 38.7469), "asmara": (15.3229, 38.9251),
    "djibouti": (11.8251, 42.5903), "mogadishu": (2.0469, 45.3182),
    "sydney": (-33.8688, 151.2093), "melbourne": (-37.8136, 144.9631),
    "brisbane": (-27.4698, 153.0251), "perth": (-31.9505, 115.8605),
    "adelaide": (-34.9285, 138.6007), "auckland": (-36.8485, 174.7633),
    "wellington": (-41.2866, 174.7756), "christchurch": (-43.5321, 172.6362),
    "suva": (-18.1416, 178.4419), "port moresby": (-9.4438, 147.1803),
    "tel aviv": (32.0853, 34.7818), "jerusalem": (31.7683, 35.2137),
    "amman": (31.9554, 35.9453), "beirut": (33.8938, 35.5018),
    "damascus": (33.5138, 36.2765), "doha": (25.2854, 51.5310),
    "kuwait city": (29.3759, 47.9774), "muscat": (23.5880, 58.3829),
    "sanaa": (15.3694, 44.1910), "manama": (26.2172, 50.5934),
    "nicosia": (35.1856, 33.3823),
}




def _resolve_cities(series: pd.Series) -> Optional[pd.DataFrame]:
    """Try to match a string Series to city coordinates."""
    hits, lats, lons, names = 0, [], [], []
    total = len(series.dropna())
    if total == 0:
        return None
    for v in series:
        if pd.isna(v):
            lats.append(None); lons.append(None); names.append(None)
            continue
        key = _norm(str(v))
        coord = _CITY_COORDS.get(key)
        if coord is None:
            words = key.split()
            for length in (3, 2):
                if len(words) >= length:
                    prefix = " ".join(words[:length])
                    coord = _CITY_COORDS.get(prefix)
                    if coord:
                        break
        if coord:
            lats.append(coord[0]); lons.append(coord[1]); names.append(str(v))
            hits += 1
        else:
            lats.append(None); lons.append(None); names.append(None)
    if hits / max(total, 1) < 0.30:
        return None
    return pd.DataFrame({"_city_lat": lats, "_city_lon": lons, "_city_name": names})




def _resolve_world_regions(series: pd.Series) -> Optional[pd.DataFrame]:
    """Try to match a string Series to world sub-national regions (non-US states)."""
    region_map = _build_world_regions_map()
    hits, lats, lons, names = 0, [], [], []
    total = len(series.dropna())
    if total == 0:
        return None
    for v in series:
        if pd.isna(v):
            lats.append(None); lons.append(None); names.append(None)
            continue
        key = _norm(str(v))
        entry = region_map.get(key)
        if entry:
            lats.append(entry[0]); lons.append(entry[1]); names.append(str(v))
            hits += 1
        else:
            lats.append(None); lons.append(None); names.append(None)
    if hits / max(total, 1) < 0.30:
        return None
    return pd.DataFrame({"_region_lat": lats, "_region_lon": lons, "_region_name": names})




def resolve_geo_names(
    series: pd.Series,
    col_name: str = "",
) -> tuple[pd.Series, str]:
    """Attempt to map a string Series to ISO codes."""
    country_map = _build_country_map()
    state_map   = _build_us_state_map()


    normed = series.dropna().astype(str).map(_norm)
    total  = max(len(normed), 1)


    _cn = _norm(col_name)
    _prefer_state   = any(k in _cn for k in ("state", "province", "region"))
    _prefer_country = any(k in _cn for k in ("country", "nation", "territory", "geo"))


    def _try_country():
        hits = normed.map(country_map).notna().sum()
        return hits / total


    def _try_state():
        hits = normed.map(state_map).notna().sum()
        return hits / total


    def _fuzzy_country_resolve(val: str) -> str | None:
        n = _norm(str(val))
        if n in country_map:
            return country_map[n]
        words = n.split()
        for length in (3, 2):
            if len(words) >= length:
                prefix = " ".join(words[:length])
                if prefix in country_map:
                    return country_map[prefix]
        if words and words[-1] in country_map:
            return country_map[words[-1]]
        return None


    threshold = 0.40


    if _prefer_state:
        sr = _try_state()
        if sr >= threshold:
            return series.astype(str).map(lambda x: state_map.get(_norm(str(x)))), "us_states"
        cr = _try_country()
        if cr >= threshold:
            return series.astype(str).map(_fuzzy_country_resolve), "countries"
    elif _prefer_country:
        cr = _try_country()
        if cr >= threshold:
            return series.astype(str).map(_fuzzy_country_resolve), "countries"
        sr = _try_state()
        if sr >= threshold:
            return series.astype(str).map(lambda x: state_map.get(_norm(str(x)))), "us_states"
    else:
        cr = _try_country()
        if cr >= threshold:
            return series.astype(str).map(_fuzzy_country_resolve), "countries"
        sr = _try_state()
        if sr >= threshold:
            return series.astype(str).map(lambda x: state_map.get(_norm(str(x)))), "us_states"


    return series, "unknown"




def get_unresolved_values(series: pd.Series, col_name: str = "") -> list[str]:
    """Return unique values that failed geo resolution — used by the upload standardiser."""
    country_map = _build_country_map()
    state_map   = _build_us_state_map()
    unresolved = []
    for v in series.dropna().unique():
        n = _norm(str(v))
        if n not in country_map and n not in state_map:
            unresolved.append(str(v))
    return sorted(unresolved)




def detect_geo_column(df: pd.DataFrame) -> Optional[str]:
    """Heuristically find a likely geographic name column (string dtype, ≥ 10"""
    country_map = _build_country_map()
    for col in df.select_dtypes("object").columns:
        unique_vals = df[col].dropna().unique()
        if len(unique_vals) < 2:
            continue
        sample = unique_vals[:50]
        hits = sum(1 for v in sample if _norm(str(v)) in country_map)
        if hits / max(len(sample), 1) >= 0.5:
            return col
    return None




def _auto_zoom(lats, lons) -> tuple:
    try:
        spread = max(float(np.max(lats) - np.min(lats)),
                     float(np.max(lons) - np.min(lons)))
        for threshold, zoom in [
            (120, 1), (60, 2), (30, 3), (15, 4), (7, 5), (3, 6),
            (1.5, 7), (0.7, 8), (0.3, 9), (0.1, 10),
        ]:
            if spread > threshold:
                return float(np.mean(lats)), float(np.mean(lons)), zoom
        return float(np.mean(lats)), float(np.mean(lons)), 11
    except Exception:
        return 20.0, 0.0, 2




def _normalise_size(series: pd.Series, lo: float, hi: float) -> pd.Series:
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series([float(lo + (hi - lo) / 2)] * len(series), index=series.index)
    return lo + (series - mn) / (mx - mn) * (hi - lo)


# Text pairs recognised as "binary text" colour columns (case-insensitive).
_BINARY_TEXT_SETS = (
    {"yes", "no"}, {"true", "false"}, {"y", "n"}, {"0", "1"},
)


def classify_colour_column(series: pd.Series) -> str:
    """Classify a colour column into one of four encoding classes.

    Returns
    -------
    "binary_numeric" : numeric column with <= 2 distinct values (e.g. 0/1)
    "binary_text"    : boolean dtype, or strings forming a yes/no style pair
    "categorical"    : non-numeric string column (discrete legend)
    "continuous"     : numeric column with > 2 distinct values (coloraxis)
    """
    s = series.dropna()
    if s.empty:
        return "categorical"
    if pd.api.types.is_bool_dtype(series):
        return "binary_text"
    if pd.api.types.is_numeric_dtype(series):
        if s.nunique() <= 2:
            return "binary_numeric"
        return "continuous"
    vals = {str(v).strip().lower() for v in pd.unique(s)}
    if len(vals) <= 2 and any(vals == pair for pair in _BINARY_TEXT_SETS):
        return "binary_text"
    return "categorical"


def _canonical_binary_label(v) -> str:
    """Map yes/no / true/false style values onto canonical "Yes"/"No" labels."""
    if pd.isna(v):
        return "(unknown)"
    t = str(v).strip().lower()
    if t in ("yes", "y", "true", "t", "1"):
        return "Yes"
    if t in ("no", "n", "false", "f", "0"):
        return "No"
    return str(v)


def _binary_colour_map(pal, invert=False, colour_class="binary_numeric"):
    """Two flat colours for binary colour columns — no scale, no variation.

    Category "1" (or "Yes") gets the TOP colour of the palette range and
    "0" (or "No") gets the BOTTOM colour, honouring the Invert toggle.
    """
    colors = list(reversed(pal)) if invert else list(pal)
    bottom, top = colors[0], colors[-1]
    if colour_class == "binary_text":
        return {"No": bottom, "Yes": top}
    return {"0": bottom, "1": top}


def _format_colour_labels(plot_df: pd.DataFrame, color: str, colour_class: str) -> str:
    """Convert a colour column in-place to its renderable form.

    Binary (numeric 0/1 or text) and categorical columns become clean string
    categories so plotly always renders a DISCRETE legend with one entry per
    value — this is what guarantees every point is drawn (points can no
    longer fall "off" a continuous colour ramp).  Continuous columns are
    left untouched for the coloraxis path.

    Returns the effective colour class ("continuous" keeps numeric encoding).
    """
    if colour_class == "binary_text":
        _bt = plot_df[color].astype(object)
        # Treat literal nan-like strings ("NaN", "None", ...) as real NaN.
        _bt = _bt.mask(
            _bt.astype(str).str.strip().str.lower().isin({"nan", "none", "null", ""})
        )
        _bt = _bt.where(_bt.notna(), "(unknown)")
        plot_df[color] = _bt.map(_canonical_binary_label).astype(str)
    elif colour_class == "binary_numeric":
        plot_df[color] = plot_df[color].map(
            lambda v: "(unknown)" if pd.isna(v) else (
                str(int(v)) if float(v).is_integer() else str(v))
        ).astype(str)
    elif colour_class == "categorical":
        _s = plot_df[color].astype(object).where(plot_df[color].notna(), "(unknown)")
        _s = _s.astype(str).str.strip()
        # CSVs often carry literal nan-like strings ("NaN", "nan", "None",
        # "") — treat them exactly like real NaN so they never leak into the
        # legend / hover as a bogus "NaN" category.
        _nanlike = {"", "nan", "NaN", "NAN", "Nan", "none", "None", "null", "NULL", "Null", "<NA>"}
        _s = _s.where(~_s.isin(_nanlike), "(unknown)")
        plot_df[color] = _s
    return colour_class




def _pal_to_continuous(colors, invert=False):
    c = list(reversed(colors)) if invert else list(colors)
    n = max(len(c) - 1, 1)
    return [[round(i / n, 4), col] for i, col in enumerate(c)]




def run_map_plot(
    df,
    lat_col=None,
    lon_col=None,
    geo_col=None,
    location_col=None,
    value_col=None,
    size_col=None,
    color_col=None,
    agg_func=None,
    invert_colorscale=False,
    palette=None,
    map_style: str = "OpenStreetMap (Light)",
    marker_opacity: float = 1.00,
    marker_size_min: int = 4,
    marker_size_max: int = 22,
    show_borders: bool = False,
    choropleth_colorscale: str = "Blues",
    choropleth_projection: str = "natural earth",
    choropleth_scope: str = "world",
    choropleth_show_borders: bool = True,
    size_by_value: bool = False,
    **kwargs,
):
    """Unified map runner."""
    pal = palette or COLORS


    if geo_col and geo_col in df.columns and not (lat_col and lon_col):
        return _run_choropleth(
            df, geo_col=geo_col, value_col=value_col,
            color_col=color_col, agg_func=agg_func,
            colorscale=choropleth_colorscale,
            projection=choropleth_projection,
            scope=choropleth_scope,
            show_borders=choropleth_show_borders,
            invert=invert_colorscale,
            pal=pal,
        )


    num_cols = [c for c in df.select_dtypes("number").columns]
    lat = lat_col or next((c for c in df.columns if "lat" in c.lower()), None)
    lon = lon_col or next(
        (c for c in df.columns
         if any(k in c.lower() for k in ("lon", "lng", "long"))), None
    )
    lat = lat or (num_cols[0] if num_cols else None)
    lon = lon or (num_cols[1] if len(num_cols) > 1 else None)


    if (not lat or not lon or
            lat not in df.columns or lon not in df.columns or
            lat not in df.select_dtypes("number").columns):
        detected_geo = geo_col or detect_geo_column(df)
        if detected_geo and detected_geo in df.columns:
            return _run_choropleth(
                df, geo_col=detected_geo, value_col=value_col,
                color_col=color_col, agg_func=agg_func,
                colorscale=choropleth_colorscale,
                projection=choropleth_projection,
                scope=choropleth_scope,
                show_borders=choropleth_show_borders,
                invert=invert_colorscale,
                pal=pal,
            )
        return []


    return _run_scatter_map(
        df, lat=lat, lon=lon,
        location_col=location_col, value_col=value_col,
        size_col=size_col, color_col=color_col,
        agg_func=agg_func, invert_colorscale=invert_colorscale,
        pal=pal, map_style=map_style,
        marker_opacity=marker_opacity,
        marker_size_min=marker_size_min,
        marker_size_max=marker_size_max,
        show_borders=show_borders,
        size_by_value=size_by_value,
    )




def _run_scatter_map(
    df, lat, lon,
    location_col, value_col, size_col, color_col,
    agg_func, invert_colorscale, pal,
    map_style, marker_opacity, marker_size_min, marker_size_max,
    show_borders=True,
    size_by_value=False,
):
    needed = list({lat, lon})
    for c in (size_col, color_col, location_col, value_col):
        if c and c in df.columns:
            needed.append(c)
    clean_df = df[list(set(needed))].dropna(subset=[lat, lon]).copy()
    clean_df = clean_df[~((clean_df[lat] == 0) & (clean_df[lon] == 0))]
    if clean_df.empty:
        return []


    agg_label = ""
    sampled   = False
    density   = False
    _density_color = False
    loc_col   = location_col if location_col and location_col in clean_df.columns else None
    val_col   = value_col    if value_col    and value_col    in clean_df.columns else None


    if loc_col and val_col:
        agg = agg_func or "mean"
        # Classify the colour column on the RAW data BEFORE grouping.  The
        # value column's aggregation (e.g. mean of 0/1 = 0.37) must never
        # re-encode a binary colour column as a continuous scale — the value
        # column only affects the tooltip / (optional) marker size, never the
        # colour encoding.
        _raw_colour_class = (
            classify_colour_column(clean_df[color_col])
            if color_col and color_col in clean_df.columns else None
        )
        agg_dict: dict = {lat: "first", lon: "first", val_col: agg}
        if color_col and color_col in clean_df.columns:
            if _raw_colour_class in ("binary_numeric", "binary_text"):
                # Binary colour: a group containing ANY 1s must render as "1"
                # (max).  A "mean" collapse would produce 0.0-1.0 floats that
                # re-classify as continuous and hide the fraud category.
                agg_dict[color_col] = (
                    "max" if pd.api.types.is_numeric_dtype(clean_df[color_col])
                    else "first"
                )
            elif pd.api.types.is_numeric_dtype(clean_df[color_col]):
                agg_dict[color_col] = agg
            else:
                agg_dict[color_col] = "first"
        if size_col and size_col in clean_df.columns and size_col != val_col:
            agg_dict[size_col] = agg
        plot_df   = clean_df.groupby(loc_col, as_index=False).agg(agg_dict)
        agg_label = f" · {agg.upper()}({val_col})"
        if val_col in plot_df.columns:
            new_val_name = f"{agg}({val_col})"
            plot_df.rename(columns={val_col: new_val_name}, inplace=True)
            val_col = new_val_name
        if size_col and size_col in plot_df.columns and size_col != val_col:
            new_size_name = f"{agg}({size_col})"
            plot_df.rename(columns={size_col: new_size_name}, inplace=True)
            size_col = new_size_name
        # Value column drives marker size ONLY when the user ticks
        # "Size by value" — otherwise it appears in the tooltip only.
        if size_by_value and not size_col and val_col in plot_df.columns:
            size_col = val_col
    else:
        if len(clean_df) > _MAP_SAMPLE:
            # Aggregate ALL points into spatial cells (full data, no random
            # sampling) so the density pattern is accurate and render cost is
            # bounded. Colour/size by cell count. The location / colour
            # columns are carried per cell (modal value) so hover tooltips
            # still show meaningful labels.
            _hover_extra = [
                c for c in (loc_col, color_col) if c and c in clean_df.columns
            ]
            # Classify the colour column so categorical colour columns survive
            # density aggregation (kept as discrete categories with a legend)
            # instead of being replaced by a "Points count" colour scale.
            _density_colour_class = (
                classify_colour_column(clean_df[color_col])
                if color_col and color_col in clean_df.columns else None
            )
            _density_binary_colour = (
                _density_colour_class in ("binary_numeric", "binary_text")
            )
            _density_categorical_colour = (
                _density_colour_class == "categorical"
            )
            plot_df = _density_aggregate(
                clean_df, lat, lon,
                extra_cols=_hover_extra,
                agg_overrides=(
                    # Binary colour: a cell containing ANY 1s must render as
                    # "1" — modal would hide minority fraud cells entirely.
                    {color_col: "max"}
                    if (_density_binary_colour
                        and (pd.api.types.is_numeric_dtype(clean_df[color_col])
                             or pd.api.types.is_bool_dtype(clean_df[color_col])))
                    else None
                ),
            )
            sampled = True
            density = True
            plot_df.rename(columns={"_count": "Points"}, inplace=True)
            if _density_binary_colour or _density_categorical_colour:
                # Binary / categorical colour: the column drives the legend,
                # not the point-count scale.  "Points" is only a hover helper.
                _density_color = False
            else:
                _density_color = True    # colour comes from the cell point count
                color_col = "Points"
            if size_col and size_col in clean_df.columns:
                size_col = None
        else:
            plot_df, sampled = clean_df, False


    if plot_df.empty:
        return []


    size  = size_col  if size_col  and size_col  in plot_df.columns else None
    color = color_col if color_col and color_col in plot_df.columns else None
    hover = loc_col   if loc_col   and loc_col   in plot_df.columns else None

    # "Size by value": the numeric value column drives marker size.
    if size_by_value and val_col and val_col in plot_df.columns:
        size = val_col

    # Classify the colour column BEFORE any encoding decision.
    colour_class = classify_colour_column(plot_df[color]) if color else None

    # Binary colour columns are never dropped.  Very wide categoricals are
    # collapsed (25+ legend entries are unreadable).  Continuous columns
    # keep the colouraxis encoding regardless of unique count — they render
    # a colour scale, not a legend.
    if color and colour_class == "categorical" \
            and plot_df[color].nunique() > 25 and not _density_color:
        color = None

    if color:
        colour_class = _format_colour_labels(plot_df, color, colour_class)

    # Value-driven marker sizes are written to a DERIVED column so the raw
    # value column stays intact for the hover tooltip.
    if size:
        try:
            raw = pd.to_numeric(plot_df[size], errors="coerce")
            if raw.dropna().nunique() > 1:
                plot_df = plot_df.copy()
                plot_df["_lytrize_size"] = _normalise_size(
                    raw.fillna(raw.median()),
                    float(marker_size_min),
                    float(marker_size_max),
                )
                size = "_lytrize_size"
            else:
                size = None
        except Exception:
            size = None

    # Explicit numeric custom-data column so the Chart Settings "Size by
    # value" toggle can (re)build per-point marker sizes from the raw value
    # without re-running the analysis. Hidden from hover tooltips above.
    if val_col and val_col in plot_df.columns:
        plot_df = plot_df.copy()
        plot_df["_lytrize_val"] = pd.to_numeric(plot_df[val_col], errors="coerce")


    hover_data: dict = {}
    for col in (val_col, size_col, color_col):
        if col and col in plot_df.columns and col != hover:
            # Value, size and colour columns are ALWAYS shown in the hover
            # tooltip (requirement: value column appears in the tooltip
            # alongside location and colour-column values).
            hover_data[col] = True
    for col in plot_df.columns:
        if col not in (hover, val_col, size_col, color_col, lat, lon):
            hover_data[col] = False
    hover_data[lat] = False
    hover_data[lon] = False
    # The normalised marker-size helper column must never appear in tooltips.
    if "_lytrize_size" in plot_df.columns:
        hover_data["_lytrize_size"] = False
    if "_lytrize_val" in plot_df.columns:
        hover_data["_lytrize_val"] = False
    # Density cells: only show the point count when the density path itself
    # colours by point count (i.e. NO colour column selected).  When a real
    # colour column drives the colours, "Points" is an internal helper and
    # must NOT appear in the hover tooltip.
    if density and _density_color and "Points" in plot_df.columns:
        hover_data["Points"] = True
    if density:
        # Density maps: show the carried location / colour columns in the
        # hover (otherwise the tooltip is empty). NOTE: must run AFTER the
        # hide-all loop above, which would otherwise reset these entries
        # back to False. The cell point count ("Points") is already included
        # as the colour column.
        for col in _hover_extra:
            if col and col in plot_df.columns and col != hover:
                hover_data[col] = True


    n_pts     = len(plot_df)
    loc_label = hover or "Locations"
    if density:
        sample_str = f" (density of {len(clean_df):,} points)"
    elif sampled:
        sample_str = f" ({n_pts:,} sample of {len(clean_df):,})"
    else:
        sample_str = f" ({n_pts:,} locations)"
    title     = f"Map: {loc_label}{agg_label}{sample_str}"


    # Discrete (legend) vs continuous (coloraxis) colour encoding — decided
    # by the classifier, not raw dtype, so binary 0/1 columns render as two
    # clearly-labelled legend categories instead of a colour ramp.
    color_is_numeric = (
        color is not None
        and color in plot_df.columns
        and colour_class == "continuous"
    )


    # --- Tile basemap path (real raster tiles) -----------------------------
    # scatter_geo is a vector-outline projection with NO tile basemap, so the
    # Style dropdown can never look like a real map on it.  When the tile
    # servers are reachable we render px.scatter_mapbox with "white-bg" plus a
    # custom RASTER tile layer (see _MAP_TILE_TEMPLATES) -- the only mechanism
    # that works on the bundled plotly.js 2.28.x without keys or watermarks.
    # NOTE: we deliberately use scatter_mapbox (NOT scatter_map): the plotly.js
    # bundled by the installed Streamlit (2.28.x) predates the maplibre "map"
    # subplot (plotly.js >= 2.35) and silently drops scattermap traces,
    # leaving a blank canvas with a stray colorbar. scatter_mapbox works on
    # every plotly.js the app can serve.  Offline we fall through to the
    # themed scatter_geo renderer below.
    style = _normalize_map_style(map_style)
    if _tiles_online():
        try:
            lat_med = float(plot_df[lat].median())
            lon_med = float(plot_df[lon].median())
            lat_span = float(plot_df[lat].max() - plot_df[lat].min())
            lon_span = float(plot_df[lon].max() - plot_df[lon].min())
            # Rough cos correction so high-latitude lon spans don't over-zoom.
            _cos = max(abs(np.cos(np.radians(lat_med))), 0.1)
            span = max(lat_span, lon_span / _cos, 0.02)
            zoom = float(min(max(round(np.log2(360.0 / span), 1), 1), 16))
            _tile_urls = _MAP_TILE_TEMPLATES.get(style) or \
                _MAP_TILE_TEMPLATES[_MAP_DEFAULT]
            raster_layer = {
                "sourcetype": "raster",
                "source": list(_tile_urls),
                "below": "traces",
            }
            # Tile basemap + (optional) country-border overlay honouring the
            # "Borders" checkbox.  On the tile path the base raster already
            # carries borders, so we overlay a translucent boundaries layer so
            # the toggle actually draws/removes them instead of being a no-op.
            _layers = [raster_layer]
            if show_borders and _MAP_BORDERS_OVERLAY:
                _layers.append({
                    "sourcetype": "raster",
                    "source": list(_MAP_BORDERS_OVERLAY),
                    "below": "traces",
                })
            map_kwargs = dict(mapbox_style="white-bg")
            map_kwargs.update(
                lat=lat, lon=lon,
                size_max=int(marker_size_max),
                hover_name=hover,
                hover_data=hover_data,
                custom_data=(["_lytrize_val"]
                             if "_lytrize_val" in plot_df.columns else None),
                title=title,
                zoom=zoom,
                center=dict(lat=lat_med, lon=lon_med),
            )
            if color and color in plot_df.columns:
                map_kwargs["color"] = color
                if color_is_numeric:
                    map_kwargs["color_continuous_scale"] = _pal_to_continuous(
                        pal, invert=invert_colorscale)
                elif colour_class in ("binary_numeric", "binary_text"):
                    # Binary: exactly two flat palette endpoint colours —
                    # no colour scale, no variation.
                    map_kwargs["color_discrete_map"] = _binary_colour_map(
                        pal, invert=invert_colorscale, colour_class=colour_class)
                else:
                    map_kwargs["color_discrete_sequence"] = (
                        list(reversed(pal)) if invert_colorscale else pal)
            if size and size in plot_df.columns:
                map_kwargs["size"] = size
            fig = px.scatter_mapbox(plot_df, **map_kwargs)
            # The raster basemap layer (OSM light/dark or satellite tiles) plus
            # optional borders overlay.
            fig.update_layout(mapbox_layers=_layers)
            fig.update_traces(marker=dict(opacity=float(marker_opacity)))
            if color and not color_is_numeric:
                # Binary / categorical maps are pure discrete legends — no
                # colorbar may ever render (guards against stale display
                # options forcing a colour scale onto category colours).
                try:
                    if getattr(fig.layout.coloraxis, "showscale", None):
                        fig.update_coloraxes(showscale=False)
                except Exception as exc:
                    log.debug("map coloraxis suppression error: %s", exc)
                for _tr in fig.data:
                    _m = getattr(_tr, "marker", None)
                    if _m is not None and hasattr(_m, "showscale"):
                        try:
                            _m.showscale = False
                        except Exception:
                            pass
            if color_is_numeric:
                # Continuous color renders through the layout coloraxis; style
                # the rendered colorbar there (theme-neutral: tiles carry the
                # light/dark look, so keep the bar readable on both).
                fig.update_coloraxes(
                    colorbar=dict(
                        title=dict(text=str(color)),
                        thickness=14, len=0.80,
                        bgcolor="rgba(0,0,0,0)",
                        bordercolor="rgba(0,0,0,0)",
                        borderwidth=0, x=1.01,
                    )
                )
            layout = chart_layout(height=520)
            for key in ("plot_bgcolor", "bargap", "bargroupgap", "xaxis", "yaxis"):
                layout.pop(key, None)
            layout["margin"] = dict(l=0, r=0, t=52, b=0)
            fig.update_layout(
                **layout,
                dragmode="pan",
                legend=dict(
                    title=dict(text=str(color) if color else ""),
                    orientation="v",
                    bgcolor="rgba(0,0,0,0)",
                ),
            )
            if density:
                fig.add_annotation(
                    text=f"⚠ Density map — {n_pts:,} cells from {len(clean_df):,} points",
                    xref="paper", yref="paper", x=0.5, y=0.0,
                    showarrow=False, xanchor="center", yanchor="bottom",
                    font=dict(size=10, color="#f59e0b"),
                )
            elif sampled:
                fig.add_annotation(
                    text=f"⚠ {n_pts:,}-point sample — zoom in for detail",
                    xref="paper", yref="paper", x=0.5, y=0.0,
                    showarrow=False, xanchor="center", yanchor="bottom",
                    font=dict(size=10, color="#f59e0b"),
                )
            fig._lytrize_meta = {
                "analysis_type": "map_plot",
                "x_axis": None, "y_axis": None,
                "legend": color,
                "supports_notes": True,
                "supports_axis_editing": False,
                "supports_legend_editing": True,
                # Tells chart_settings which colour encoding this figure uses
                # so the Colorbar/Colorscale controls can never force a colour
                # scale onto a discrete (binary/categorical) legend.
                "colour_encoding": "continuous" if color_is_numeric else "discrete",
                # Value-driven sizes use an array of per-point sizes; the
                # manual "M. size" slider must not override them.
                "value_sized": bool(size_by_value and val_col and size == "_lytrize_size"),
            }
            return [(f"Map: {loc_label}", fig)]
        except Exception:
            log.exception("scatter_map (tile) render failed; falling back to scatter_geo")

    # --- Offline fallback: bundled-geo scatter_geo (no tiles) --------------
    # Plotly ships the world/region geojson inside the package, so it needs no
    # network.  map_style is translated into an equivalent light/dark geo
    # theme because scatter_geo cannot draw tiles.
    geo_kwargs = dict(
        lat=lat, lon=lon,
        size_max=int(marker_size_max),
        hover_name=hover,
        hover_data=hover_data,
        custom_data=(["_lytrize_val"]
                     if "_lytrize_val" in plot_df.columns else None),
        title=title,
        projection="natural earth",
        fitbounds="locations",
    )
    if color and color in plot_df.columns:
        geo_kwargs["color"] = color
        if color_is_numeric:
            geo_kwargs["color_continuous_scale"] = _pal_to_continuous(pal, invert=invert_colorscale)
        elif colour_class in ("binary_numeric", "binary_text"):
            geo_kwargs["color_discrete_map"] = _binary_colour_map(
                pal, invert=invert_colorscale, colour_class=colour_class)
        else:
            geo_kwargs["color_discrete_sequence"] = list(reversed(pal)) if invert_colorscale else pal
    if size and size in plot_df.columns:
        geo_kwargs["size"] = size

    try:
        fig = px.scatter_geo(plot_df, **geo_kwargs)
    except Exception:
        log.exception("scatter_geo error")
        return []

    # scatter_geo has no opacity kwarg; apply marker opacity directly.
    fig.update_traces(marker=dict(opacity=float(marker_opacity)))
    if color and not color_is_numeric:
        # Same discrete-colour colorbar suppression as the tile path.
        try:
            if getattr(fig.layout.coloraxis, "showscale", None):
                fig.update_coloraxes(showscale=False)
        except Exception as exc:
            log.debug("map coloraxis suppression error: %s", exc)
        for _tr in fig.data:
            _m = getattr(_tr, "marker", None)
            if _m is not None and hasattr(_m, "showscale"):
                try:
                    _m.showscale = False
                except Exception:
                    pass
    # ``map_style`` selects the base map theme. scatter_geo ships no mapbox
    # tiles, so the (light/dark) style is translated into equivalent geo
    # surface colors instead of always forcing a dark base map.
    _is_dark = "dark" in str(map_style).lower()
    if _is_dark:
        _geo = dict(
            bgcolor="rgba(0,0,0,0)",
            showcoastlines=True, coastlinecolor="rgba(148,163,184,0.4)",
            showland=True, landcolor="rgba(30,41,59,0.8)",
            showocean=True, oceancolor="rgba(14,20,38,0.9)",
            showlakes=True, lakecolor="rgba(14,20,38,0.9)",
            showframe=False,
            showcountries=show_borders,
            countrycolor="rgba(255,255,255,0.4)" if show_borders else "rgba(0,0,0,0)",
        )
        _cb_tick  = "#94a3b8"
        _cb_title = "#cbd5e1"
    else:
        # Light base map (open-street-map / carto-positron).
        _geo = dict(
            bgcolor="rgba(0,0,0,0)",
            showcoastlines=True, coastlinecolor="rgba(100,116,139,0.6)",
            showland=True, landcolor="#f1f5f9",
            showocean=True, oceancolor="#bfdbfe",
            showlakes=True, lakecolor="#bae6fd",
            showframe=False,
            showcountries=show_borders,
            countrycolor="rgba(100,116,139,0.6)" if show_borders else "rgba(0,0,0,0)",
        )
        _cb_tick  = "#475569"
        _cb_title = "#1e293b"
    fig.update_geos(**_geo)


    if color_is_numeric:
        # scatter_geo with a continuous color renders its colorbar through the
        # LAYOUT coloraxis (the trace`s marker.colorbar is unused). update_coloraxes
        # is the correct, rendered colorbar API. (Re-applied by chart_settings.)
        try:
            fig.update_coloraxes(
                colorbar=dict(
                    title=dict(text=str(color), font=dict(color=_cb_title)),
                    tickfont=dict(color=_cb_tick),
                    thickness=14, len=0.80,
                    bgcolor="rgba(0,0,0,0)",
                    bordercolor="rgba(0,0,0,0)",
                    borderwidth=0, x=1.01,
                )
            )
        except Exception as exc:
            log.debug("map colorbar styling error: %s", exc)

    layout = chart_layout(height=520)
    for key in ("plot_bgcolor", "bargap", "bargroupgap", "xaxis", "yaxis"):
        layout.pop(key, None)
    layout["margin"] = dict(l=0, r=0, t=52, b=0)
    fig.update_layout(
        **layout,
        legend=dict(
            title=dict(text=str(color) if color else ""),
            orientation="v",
            bgcolor="rgba(0,0,0,0)",
        ),
    )


    if density:
        fig.add_annotation(
            text=f"⚠ Density map — {n_pts:,} cells from {len(clean_df):,} points",
            xref="paper", yref="paper", x=0.5, y=0.0,
            showarrow=False, xanchor="center", yanchor="bottom",
            font=dict(size=10, color="#f59e0b"),
        )
    elif sampled:
        fig.add_annotation(
            text=f"⚠ {n_pts:,}-point sample — zoom in for detail",
            xref="paper", yref="paper", x=0.5, y=0.0,
            showarrow=False, xanchor="center", yanchor="bottom",
            font=dict(size=10, color="#f59e0b"),
        )


    fig._lytrize_meta = {
        "analysis_type": "map_plot",
        "x_axis": None, "y_axis": None,
        "legend": color,
        "supports_notes": True,
        "supports_axis_editing": False,
        "supports_legend_editing": True,
        "colour_encoding": "continuous" if color_is_numeric else "discrete",
        "value_sized": bool(size_by_value and val_col and size == "_lytrize_size"),
    }
    return [(f"Map: {loc_label}", fig)]




def _run_choropleth(
    df, geo_col, value_col, color_col, agg_func,
    colorscale, projection, scope, show_borders, invert, pal,
):
    if not value_col or value_col not in df.columns:
        plot_df = df[[geo_col]].copy().dropna()
        plot_df["_count"] = 1
        plot_df = plot_df.groupby(geo_col, as_index=False)["_count"].sum()
        value_col = "_count"
        agg_label = "COUNT"
    else:
        needed = [geo_col, value_col]
        plot_df = df[needed].dropna(subset=[geo_col, value_col]).copy()
        agg = agg_func or "sum"
        agg_label = agg.upper()
        if pd.api.types.is_numeric_dtype(plot_df[value_col]):
            agg_funcs = {"sum": "sum", "mean": "mean", "median": "median",
                         "count": "count", "max": "max", "min": "min"}
            plot_df = plot_df.groupby(geo_col, as_index=False).agg(
                {value_col: agg_funcs.get(agg, "sum")}
            )
        else:
            plot_df = plot_df.groupby(geo_col, as_index=False).agg(
                {value_col: "count"}
            )
            agg_label = "COUNT"


    if plot_df.empty:
        return []


    resolved, geo_type = resolve_geo_names(plot_df[geo_col], col_name=geo_col)
    unresolved_count = resolved.isna().sum()


    if geo_type == "unknown":
        region_df = _resolve_world_regions(plot_df[geo_col])
        if region_df is not None:
            return _render_scatter_geo(
                plot_df, geo_col, value_col, agg_label,
                lat_col="_region_lat", lon_col="_region_lon",
                coord_df=region_df.rename(columns={"_region_lat": "_region_lat",
                                                    "_region_lon": "_region_lon",
                                                    "_region_name": "_region_name"}),
                name_col="_region_name",
                colorscale=colorscale, invert=invert,
                show_borders=show_borders, projection=projection, scope=scope,
            )


    if geo_type == "unknown":
        city_df = _resolve_cities(plot_df[geo_col])
        if city_df is not None:
            return _render_scatter_geo(
                plot_df, geo_col, value_col, agg_label,
                lat_col="_city_lat", lon_col="_city_lon",
                coord_df=city_df,
                name_col="_city_name",
                colorscale=colorscale, invert=invert,
                show_borders=show_borders, projection=projection, scope=scope,
            )


    if geo_type == "unknown":
        import streamlit as _st
        _sample = ', '.join(str(v) for v in plot_df[geo_col].dropna().unique()[:6])
        _st.warning(
            f"⚠️ **Map cannot render** — '{geo_col}' values could not be matched to "
            "countries, US states, world regions, or known cities.  \n"
            f"**Sample values:** {_sample}  \n"
            "Try using the **Geo Location Standardise** tool on the Upload page first, "
            "or make sure values are standard country names, ISO-2/3 codes, US state names, "
            "Indian/Canadian/Australian state names, or major city names."
        )
        return []


    plot_df["_iso_code"] = resolved.values
    plot_df = plot_df.dropna(subset=["_iso_code"])
    if plot_df.empty:
        return []


    if geo_type == "us_states":
        locationmode = "USA-states"
        plot_df["_iso_code"] = plot_df["_iso_code"].str.replace("US-", "", regex=False)
        scope = "usa"
    else:
        locationmode = "ISO-3"
        plot_df["_iso_code"] = plot_df["_iso_code"].apply(_ensure_alpha3)


    _cs = colorscale if colorscale in _CHOROPLETH_SCALES else "Blues"
    if invert:
        _cs = f"{_cs}_r"


    n_locs = len(plot_df)
    warning_text = (
        f"⚠ {unresolved_count} value(s) in '{geo_col}' could not be matched"
        if unresolved_count > 0 else ""
    )
    title = f"Choropleth: {agg_label}({value_col}) by {geo_col}  ({n_locs:,} locations)"


    try:
        fig = px.choropleth(
            plot_df,
            locations="_iso_code",
            locationmode=locationmode,
            color=value_col,
            hover_name=geo_col,
            hover_data={value_col: True, "_iso_code": False},
            color_continuous_scale=_cs,
            projection=projection if geo_type != "us_states" else "albers usa",
            scope=scope,
            title=title,
            labels={value_col: f"{agg_label}({value_col})"},
        )
    except Exception:
        log.exception("choropleth error")
        return []


    fig.update_traces(marker_line_width=0.5 if show_borders else 0)
    fig.update_geos(
        bgcolor="rgba(14,20,38,0)",
        showcoastlines=True, coastlinecolor="rgba(148,163,184,0.4)",
        showland=True, landcolor="rgba(30,41,59,0.8)",
        showocean=True, oceancolor="rgba(14,20,38,0.9)",
        showlakes=True, lakecolor="rgba(14,20,38,0.9)",
        showframe=False,
        showcountries=show_borders,
        countrycolor="rgba(255,255,255,0.4)" if show_borders else "rgba(0,0,0,0)",
    )
    fig.update_coloraxes(
        colorbar=dict(
            title=dict(text=f"{agg_label}({value_col})", font=dict(color="#cbd5e1")),
            tickfont=dict(color="#94a3b8"),
            thickness=14, len=0.80,
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(0,0,0,0)", borderwidth=0,
        )
    )
    layout = chart_layout(height=500)
    for key in ("plot_bgcolor", "bargap", "bargroupgap", "xaxis", "yaxis"):
        layout.pop(key, None)
    layout["margin"] = dict(l=0, r=0, t=52, b=0)
    layout["geo"] = dict(bgcolor="rgba(14,20,38,0)")
    fig.update_layout(**layout)
    if warning_text:
        fig.add_annotation(
            text=warning_text, xref="paper", yref="paper", x=0.5, y=0.0,
            showarrow=False, xanchor="center", yanchor="bottom",
            font=dict(size=10, color="#f59e0b"),
        )
    fig._lytrize_meta = {
        "analysis_type": "map_plot", "x_axis": None, "y_axis": None,
        "supports_notes": True, "supports_axis_editing": False,
        "supports_legend_editing": False,
    }
    return [(f"Choropleth: {geo_col}", fig)]




def _render_scatter_geo(
    plot_df, geo_col, value_col, agg_label,
    lat_col, lon_col, coord_df, name_col,
    colorscale, invert, show_borders, projection, scope,
):
    """Render a scatter_geo for world regions / cities where Plotly choropleth"""
    merged = pd.concat(
        [plot_df.reset_index(drop=True), coord_df.reset_index(drop=True)], axis=1
    ).dropna(subset=[lat_col, lon_col])


    if merged.empty:
        return []


    _cs = colorscale if colorscale in _CHOROPLETH_SCALES else "Blues"
    if invert:
        _cs = f"{_cs}_r"


    n_locs = len(merged)
    title = f"Map: {agg_label}({value_col}) by {geo_col}  ({n_locs:,} locations)"


    try:
        fig = px.scatter_geo(
            merged,
            lat=lat_col,
            lon=lon_col,
            size=value_col,
            color=value_col,
            hover_name=geo_col,
            hover_data={value_col: True, lat_col: False, lon_col: False,
                        name_col: False},
            color_continuous_scale=_cs,
            projection=projection,
            title=title,
            size_max=40,
        )
    except Exception:
        log.exception("scatter_geo error")
        return []


    fig.update_traces(marker=dict(line=dict(width=0.5, color="rgba(255,255,255,0.3)")))
    fig.update_geos(
        bgcolor="rgba(14,20,38,0)",
        showcoastlines=True, coastlinecolor="rgba(148,163,184,0.4)",
        showland=True, landcolor="rgba(30,41,59,0.8)",
        showocean=True, oceancolor="rgba(14,20,38,0.9)",
        showlakes=True, lakecolor="rgba(14,20,38,0.9)",
        showframe=False,
        showcountries=show_borders,
        countrycolor="rgba(255,255,255,0.4)" if show_borders else "rgba(0,0,0,0)",
    )
    fig.update_coloraxes(
        colorbar=dict(
            title=dict(text=f"{agg_label}({value_col})", font=dict(color="#cbd5e1")),
            tickfont=dict(color="#94a3b8"),
            thickness=14, len=0.80,
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(0,0,0,0)", borderwidth=0,
        )
    )
    layout = chart_layout(height=520)
    for key in ("plot_bgcolor", "bargap", "bargroupgap", "xaxis", "yaxis"):
        layout.pop(key, None)
    layout["margin"] = dict(l=0, r=0, t=52, b=0)
    layout["geo"] = dict(bgcolor="rgba(14,20,38,0)")
    fig.update_layout(**layout)
    fig._lytrize_meta = {
        "analysis_type": "map_plot", "x_axis": None, "y_axis": None,
        "supports_notes": True, "supports_axis_editing": False,
        "supports_legend_editing": False,
    }
    return [(f"Map: {geo_col}", fig)]




def _ensure_alpha3(code: str) -> str:
    """If code looks like a 2-letter ISO alpha-2, convert to alpha-3."""
    if not code or not isinstance(code, str):
        return code
    code = code.strip().upper()
    if len(code) == 2:
        try:
            import pycountry
            c = pycountry.countries.get(alpha_2=code)
            return c.alpha_3 if c else code
        except Exception:
            return code
    return code
