"""External automotive data connectors."""

from backend.app.connectors.carfax import fetch as fetch_carfax
from backend.app.connectors.fueleconomy import fetch as fetch_fueleconomy
from backend.app.connectors.kbb import fetch as fetch_kbb
from backend.app.connectors.nhtsa import fetch as fetch_nhtsa

__all__ = [
    "fetch_carfax",
    "fetch_fueleconomy",
    "fetch_kbb",
    "fetch_nhtsa",
]