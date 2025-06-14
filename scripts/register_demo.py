from itemradar_ai.semantic_db import register_item, ItemType

resp = register_item(
    raw_description="Found blue Nike backpack with laptop inside",
    item_type=ItemType.FOUND,
    contact_email="finder@example.com",
    address="Union Square, San Francisco",
    latitude=37.787994,
    longitude=-122.407437,
    image_url=None
)

print(resp)
