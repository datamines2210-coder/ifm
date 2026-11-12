from dataclasses import dataclass
from typing import Optional

@dataclass
class Product:
    id: str
    name: str
    category: str
    state: str
    price: float
    mrp: float
    unit: str
    description: str
    image: str = ""
    parent_url: str = "https://theindianfamily.com/"
    active: bool = True
    status: str = "live"

PRODUCTS = [
    Product("demo-up-001", "Mango Pickle", "Pickles", "Andhra Pradesh", 539, 599, "500 g", "Traditional Andhra-style mango pickle from the parent collection.", "https://img1.wsimg.com/isteam/ip/926fcfc1-c2d4-4f09-b9b4-0881a36b6d11/ChatGPT%20Image%20Feb%206%2C%202026%2C%2004_29_33%20PM.png", "https://theindianfamily.com/shop/ols/products/andhra-mango-pickle-authentic-homemade"),
    Product("demo-rj-001", "Ker Sangri Pickle", "Pickles", "Rajasthan", 279, 329, "400 g", "Demo catalog item — replace with verified parent-brand SKU."),
    Product("demo-pb-001", "Punjabi Mixed Pickle", "Pickles", "Punjab", 239, 289, "500 g", "Demo catalog item — replace with verified parent-brand SKU."),
    Product("demo-kl-001", "Malabar Spice Blend", "Spices", "Kerala", 199, 249, "200 g", "Demo catalog item — replace with verified parent-brand SKU."),
    Product("demo-ra-001", "Byadgi Chilli Powder", "Spices", "Karnataka", 189, 229, "250 g", "Demo catalog item — replace with verified parent-brand SKU."),
    Product("demo-as-001", "Assam Black Tea", "Tea", "Assam", 299, 349, "250 g", "Demo catalog item — replace with verified parent-brand SKU."),
    Product("demo-wb-001", "Darjeeling Tea", "Tea", "West Bengal", 399, 449, "250 g", "Demo catalog item — replace with verified parent-brand SKU."),
    Product("demo-mh-001", "Kokum Fruit Drink", "Others", "Maharashtra", 149, 179, "500 ml", "Demo catalog item — replace with verified parent-brand SKU."),
]
