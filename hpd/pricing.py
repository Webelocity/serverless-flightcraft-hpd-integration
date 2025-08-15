from math import floor
from typing import List, Dict

from .models import Product


def compute_final_price(product: Product) -> float:

    """Compute the final retail price based on the provided Excel logic:
    - Prefer CADmap if > 0
    - Else use USDmap * 1.4, floored to integer, then + 0.99
    - Else use Cost (Product.Price) * 1.75, floored to integer, then + 0.99
    - Enforce minimum margin: max(calculated, floor(cost * 1.3) + 0.99)
    Returns a price rounded to 2 decimals. If no inputs are valid, returns 0.0
    """

    cad_map = product.CADmap
    usd_map = product.USDmap
    cost_price = product.Price

    conv_cad = cad_map if (cad_map is not None and cad_map > 0) else None
    conv_usd = (floor(usd_map * 1.4) + 0.99) if (usd_map is not None and usd_map > 0) else None
    conv_cost = (floor(cost_price * 1.75) + 0.99) if (cost_price is not None and cost_price > 0) else None

    base_price = next((v for v in (conv_cad, conv_usd, conv_cost) if v is not None), None)

    min_margin = (floor(cost_price * 1.3) + 0.99) if (cost_price is not None and cost_price > 0) else None

    if base_price is not None and min_margin is not None and base_price < min_margin:
        final_price = min_margin
    else:
        final_price = base_price

    if final_price is None:
        return 0.0
    return round(final_price, 2)


def compute_priced_catalog(products: List[Product]) -> List[Dict[str, object]]:
    """Return a list of dicts with PartNumber, Model, Title, FinalPrice for each product."""
    return [
        {
            "SKU": p.PartNumber,
            "Final Price": compute_final_price(p),
            "Cost Price": p.Price,
            "isActive": p.Discontinued,
            "Inventory": {"Online Store": int(p.Available)},
        }
        for p in products
    ]

