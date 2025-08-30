from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Product:
    PartNumber: str
    Description: str
    Title: str
    Category: str
    AltCode: str
    Model: str
    Available: float # if negative means backorder ( orders > available inventory )
    OnOrder: float
    Discontinued: bool
    ModifiedOn: Optional[str]
    AddedOn: Optional[str]
    CADmap: float
    USDmap: float
    Manufacturer: str
    ETA: Optional[str]
    Price: float
