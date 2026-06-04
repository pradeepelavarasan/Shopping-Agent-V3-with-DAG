import json

products = [
    {"id": "B074C8C6F4", "title": "Lapcare Chillmate Powerful Laptop Cooler Pad with Dual 125mm Fans, Silent Operation Noiseless Fan, Dual USB Ports, 5 Step Retractable Stand and Removable Mobile Holder", "price": "₹679", "rating": 4.0, "reviews_count": 8300, "url": "https://www.amazon.in/dp/B074C8C6F4"},
    {"id": "B0C663VVP1", "title": "Zebronics NC5500D Powerful Laptop Cooler with Dual 125mm Fans, Silent Operation, Adjustable Fan Speed, Display, Controls, USB, 5 Step Retractable Stand and Mobile Holder", "price": "₹799", "rating": 4.0, "reviews_count": 2400, "url": "https://www.amazon.in/dp/B0C663VVP1"},
    {"id": "B0FKYK8H3H", "title": "CLAW Air Pro C39 Laptop Cooling Pad with Dual 125mm Fans (1000 RPM), Mobile Stand, Anti-Slip Baffle, 5 Height Levels, 2 USB 2.0 Ports, Supports Up to 17-Inch Laptops – Black", "price": "₹589", "rating": 4.1, "reviews_count": 518, "url": "https://www.amazon.in/dp/B0FKYK8H3H"},
    {"id": "B0D9W55VLG", "title": "Ant Esports NC230 Gaming Notebook Cooler for 10–17 Inch Laptops | Cooling Pad with 6 Fans RGB | USB Powered Silent Fan | Adjustable Height Cooling Stand | Compatible with MacBook, PS5 & PS4", "price": "₹729", "rating": 3.9, "reviews_count": 1000, "url": "https://www.amazon.in/dp/B0D9W55VLG"},
    {"id": "B07YWS9SP9", "title": "Zebronics, ZEB-NC3300 USB Powered Laptop Cooling Pad with Dual Fan, Dual USB Port and Blue LED Lights", "price": "₹599", "rating": 3.9, "reviews_count": 12800, "url": "https://www.amazon.in/dp/B07YWS9SP9"},
    {"id": "B0FV3F3NTH", "title": "EvoFox Frost Plus Laptop Cooling Pad | Laptop Cooler Pad with Dual Fans, Blue LED Backlight, Iron Mesh Design, LCD Display, Adjustable Stand, Ultra-Quiet Dual USB Cooling Pad (Black)", "price": "₹749", "rating": 4.1, "reviews_count": 229, "url": "https://www.amazon.in/dp/B0FV3F3NTH"},
    {"id": "B0CRZBR52Y", "title": "Dyazo Laptop Cooling Pad |Laptop Stand with Cooling Fan | Adjustable Height 5 Step with Mobile Holder Compatible for All laptops & Notebook 11.6/13.3/14 / 15.6 inch - (Black)", "price": "₹599", "rating": 3.9, "reviews_count": 4800, "url": "https://www.amazon.in/dp/B0CRZBR52Y"},
    {"id": "B09R9CK3DD", "title": "PLIXIO Aluminum Tabletop Laptop Stand Ergonomic Foldable Portable Laptop Stand Holder Compatible for MacBook, HP, Dell, Lenovo & All Other Notebook (Sliver)", "price": "₹1,798", "rating": 4.3, "reviews_count": 1300, "url": "https://www.amazon.in/dp/B09R9CK3DD"},
    {"id": "B0GSS9HQVS", "title": "SpinBot Airflow X10 Laptop Cooling Pad with Dual Fans | Low Noise 30dB | 4-Level Adjustable Stand | 2 USB Ports with Speed Control | Cooling Stand for Gaming & Work Laptops up to 17\"", "price": "₹1,799", "rating": 4.1, "reviews_count": 169, "url": "https://www.amazon.in/dp/B0GSS9HQVS"},
    {"id": "B0DGGTKVMP", "title": "Dracula 60 Laptop Cooling Pad, Gaming Laptop Cooler with 6 * 1 Quite Fans, Fan Speed Controller 5 Height Adjustable Angle 2 USB Ports Compatible for Laptop, Notebook up to 17\”", "price": "₹729", "rating": 3.9, "reviews_count": 1000, "url": "https://www.amazon.in/dp/B0DGGTKVMP"}
]

# Filter for Cooling Pads (exclude generic stands), sort by rating DESC then reviews_count DESC
# "PLIXIO" is a stand, not a cooler. 
filtered = [p for p in products if "Cool" in p['title'] and "Stand" in p['title'] or "Cooling" in p['title']]
filtered = [p for p in filtered if "PLIXIO" not in p['title']]

sorted_products = sorted(filtered, key=lambda x: (-x['rating'], -x['reviews_count']))

selected = sorted_products[:3]
for i, p in enumerate(selected):
    p['id'] = f"prod_{i+1}"

print(json.dumps(selected))