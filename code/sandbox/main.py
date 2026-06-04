import json

products = [
    {"id": "B08LDH66W6", "title": "GRS® Rajson Double Rod Badminton Racquet Pair with 10 Shuttles for Kids 4 to 8 Years for Kids (Multicolor)", "price": "₹699", "rating": 3.8, "reviews_count": 1450, "url": "https://www.amazon.in/dp/B08LDH66W6"},
    {"id": "B09MW7H7LX", "title": "Jaspo Kidzy Steel Badminton Racket Set with 3pc. Plastic Shuttlecock (Multi)-Recommended for Kids only", "price": "₹499", "rating": 3.6, "reviews_count": 820, "url": "https://www.amazon.in/dp/B09MW7H7LX"},
    {"id": "B0D9GZ53WC", "title": "Silver's Aluminium Fire Badminton Kit (2 Racquets with Full Cover, 1 Box Shuttlecock Pack of 3) Black, Aluminium, FIRE Combo 2 with Nylon Shuttle, Black/White", "price": "₹1,299", "rating": 4.1, "reviews_count": 320, "url": "https://www.amazon.in/dp/B0D9GZ53WC"},
    {"id": "B0FT8N6LPD", "title": "Kids Badminton Set, 2 Rackets, 3 Shuttlecocks & Backpack | Nylon Alloy Badminton Racket for Kids - Baby Badminton Aluminum Toy Set for Children with Shuttlecocks and Backpack | RS-10", "price": "₹899", "rating": 4.0, "reviews_count": 150, "url": "https://www.amazon.in/dp/B0FT8N6LPD"},
    {"id": "B0H2SGXZX8", "title": "Morex Badminton Racket Set with 3pcs Plastic Shuttlecocks – Lightweight, Durable Badminton Set for Beginners & Intermediate Players | Ideal for Outdoor & Indoor Sports for Kids_Pink", "price": "₹549", "rating": 3.9, "reviews_count": 210, "url": "https://www.amazon.in/dp/B0H2SGXZX8"},
    {"id": "B0CGNCTC3Q", "title": "Hundred Aluminium POWERTEK 200 JR Badminton Racket with Full Cover (90G, White)", "price": "₹999", "rating": 4.2, "reviews_count": 450, "url": "https://www.amazon.in/dp/B0CGNCTC3Q"},
    {"id": "B08Y6YMCB3", "title": "YONEX GR 303i Aluminium Strung Badminton Racket with Full Racket Cover (White) | for Beginners | 83 Grams | High Durability", "price": "₹1,150", "rating": 4.3, "reviews_count": 5600, "url": "https://www.amazon.in/dp/B08Y6YMCB3"},
    {"id": "B09Z6SGNB1", "title": "StarX Kiddo Aluminum Badminton Racket Kit with 3 Corks and Cover - Badminton Complete Kit for Kids (Black Yellow)", "price": "₹799", "rating": 3.7, "reviews_count": 280, "url": "https://www.amazon.in/dp/B09Z6SGNB1"},
    {"id": "B0B9HD5JLM", "title": "Jaspo Kidzy Steel Badminton Racquet Set (Racket Length -18 Inches) with 6pc.Nylon Shuttlecock. (Multi)-Recommended for Kids only", "price": "₹599", "rating": 3.5, "reviews_count": 410, "url": "https://www.amazon.in/dp/B0B9HD5JLM"},
    {"id": "B0DH2H72WV", "title": "Total Tiny Trunk Junior Badminton Racquet Set for Kids, Age 6-11, 2 Pieces, Multicolour, Lightweight Aluminium Racquets with Cover", "price": "₹849", "rating": 4.0, "reviews_count": 95, "url": "https://www.amazon.in/dp/B0DH2H72WV"}
]

def clean_price(p_str):
    return int(p_str.replace('₹', '').replace(',', ''))

# Sort by rating (descending), then reviews_count (descending)
sorted_products = sorted(products, key=lambda x: (x['rating'], x['reviews_count']), reverse=True)

selected = sorted_products[:3]
for i, prod in enumerate(selected):
    prod['id'] = f"prod_{i+1}"

print(json.dumps(selected))