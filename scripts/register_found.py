# scripts/register_found.py

import os
from lens_agent.agent import geocode_location, register_found_item, PROJECT_ID

# 1) Your “AI” description of the item (in practice your agent would generate this)
description = "Black leather wallet with silver logo and two card slots."

# 2) The finder’s contact email
contact_email = "finder@example.com"

# 3) The location text they provided
user_location_text = "Union Square, San Francisco"

# 4) First call geocode_location to turn text → (address, lat, lon)
geo = geocode_location(user_location_text)
if geo.get("status") != "success":
    print("❌ Failed to geocode:", geo.get("error_message"))
    exit(1)

address   = geo["address"]
latitude  = geo["latitude"]
longitude = geo["longitude"]

# 5) Finally, call register_found_item
result = register_found_item(
    description=description,
    contact_email=contact_email,
    address=address,
    latitude=latitude,
    longitude=longitude,
)

if result.get("status") == "success":
    print("✅ Stored found item with ID:", result["item_id"])
else:
    print("❌ Error storing item:", result.get("error_message"))
