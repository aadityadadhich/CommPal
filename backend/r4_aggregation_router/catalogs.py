from typing import Dict, Any, List

chaos_flags = {
    "out_of_stock_items": set(),
    "price_spikes": {},
    "down_merchants": set(),
    "slow_merchants": set(),
    "payment_failure": False
}

def reset_chaos():
    chaos_flags["out_of_stock_items"].clear()
    chaos_flags["price_spikes"].clear()
    chaos_flags["down_merchants"].clear()
    chaos_flags["slow_merchants"].clear()
    chaos_flags["payment_failure"] = False

MOCK_CATALOGS: Dict[str, List[Dict[str, Any]]] = {
    "quick10": [
        {"sku": "Q10-MILK-1", "title": "Farm Fresh Whole Milk 1L", "item_name": "milk", "brand": "Organic Valley", "size": "1L", "unit_price": 4.29, "delivery_fee": 1.99, "stock_qty": 25, "eta_minutes": 15, "rating": 4.8},
        {"sku": "Q10-PROT-1", "title": "Optimum Nutrition Gold Standard Whey 1kg", "item_name": "protein powder", "brand": "Optimum Nutrition", "size": "1kg", "unit_price": 44.99, "delivery_fee": 2.49, "stock_qty": 6, "eta_minutes": 20, "rating": 4.9},
        {"sku": "Q10-PAPR-1", "title": "HP Multipurpose A4 Copy Paper 500 Sheets", "item_name": "a4 paper", "brand": "HP", "size": "500 sheets", "unit_price": 11.99, "delivery_fee": 1.99, "stock_qty": 12, "eta_minutes": 18, "rating": 4.7},
        {"sku": "Q10-WD40-1", "title": "WD-40 Multi-Use Smart Straw 300ml", "item_name": "wd-40", "brand": "WD-40", "size": "300ml", "unit_price": 10.49, "delivery_fee": 1.99, "stock_qty": 8, "eta_minutes": 22, "rating": 4.8},
        {"sku": "Q10-EGGS-1", "title": "Pasture-Raised Brown Eggs Grade A 12ct", "item_name": "eggs", "brand": "Vital Farms", "size": "12 count", "unit_price": 5.99, "delivery_fee": 1.99, "stock_qty": 15, "eta_minutes": 15, "rating": 4.8},
        {"sku": "Q10-COFF-1", "title": "Medium Roast Ground Coffee 500g", "item_name": "coffee", "brand": "Lavazza", "size": "500g", "unit_price": 13.99, "delivery_fee": 1.99, "stock_qty": 10, "eta_minutes": 16, "rating": 4.7},
    ],
    "zipbasket": [
        {"sku": "ZB-MILK-1", "title": "Horizon Organic Whole Milk 1L", "item_name": "milk", "brand": "Horizon", "size": "1L", "unit_price": 3.99, "delivery_fee": 1.49, "stock_qty": 30, "eta_minutes": 30, "rating": 4.7},
        {"sku": "ZB-PROT-1", "title": "Dymatize ISO100 Hydrolyzed Whey 1kg", "item_name": "protein powder", "brand": "Dymatize", "size": "1kg", "unit_price": 42.50, "delivery_fee": 1.99, "stock_qty": 8, "eta_minutes": 35, "rating": 4.8},
        {"sku": "ZB-PAPR-1", "title": "Hammermill A4 Printer Paper 500ct", "item_name": "a4 paper", "brand": "Hammermill", "size": "500 sheets", "unit_price": 9.99, "delivery_fee": 1.49, "stock_qty": 14, "eta_minutes": 28, "rating": 4.6},
        {"sku": "ZB-WD40-1", "title": "WD-40 Specialist Penetrant Spray 300ml", "item_name": "wd-40", "brand": "WD-40", "size": "300ml", "unit_price": 9.49, "delivery_fee": 1.49, "stock_qty": 5, "eta_minutes": 30, "rating": 4.7},
        {"sku": "ZB-BRED-1", "title": "Artisan Sourdough Loaf 500g", "item_name": "bread", "brand": "Boulangerie", "size": "500g", "unit_price": 4.49, "delivery_fee": 1.49, "stock_qty": 10, "eta_minutes": 25, "rating": 4.6},
    ],
    "cornerstore": [
        {"sku": "CS-MILK-1", "title": "Local Dairy Farm Whole Milk 1L", "item_name": "milk", "brand": "Clover", "size": "1L", "unit_price": 3.79, "delivery_fee": 0.99, "stock_qty": 15, "eta_minutes": 90, "rating": 4.5},
        {"sku": "CS-PAPR-1", "title": "Standard Office Copy Paper 500ct", "item_name": "a4 paper", "brand": "Generic", "size": "500 sheets", "unit_price": 8.99, "delivery_fee": 0.99, "stock_qty": 4, "eta_minutes": 80, "rating": 4.2},
        {"sku": "CS-WD40-1", "title": "WD-40 Original Formula 300ml", "item_name": "wd-40", "brand": "WD-40", "size": "300ml", "unit_price": 8.99, "delivery_fee": 0.99, "stock_qty": 3, "eta_minutes": 75, "rating": 4.6},
        {"sku": "CS-EGGS-1", "title": "Cage-Free Large White Eggs 12ct", "item_name": "eggs", "brand": "Local Farm", "size": "12 count", "unit_price": 4.29, "delivery_fee": 0.99, "stock_qty": 8, "eta_minutes": 70, "rating": 4.4},
    ],
    "megamart": [
        {"sku": "MM-MILK-1", "title": "Value Pack Shelf-Stable UHT Milk 1L x 4", "item_name": "milk", "brand": "ValueMart", "size": "4L", "unit_price": 11.50, "delivery_fee": 3.99, "stock_qty": 100, "eta_minutes": 2880, "rating": 4.2},
        {"sku": "MM-PROT-1", "title": "Optimum Nutrition Gold Standard Whey 1kg", "item_name": "protein powder", "brand": "Optimum Nutrition", "size": "1kg", "unit_price": 34.99, "delivery_fee": 0.0, "stock_qty": 45, "eta_minutes": 1440, "rating": 4.8},
        {"sku": "MM-PAPR-1", "title": "AmazonBasics Multipurpose A4 Paper 500ct", "item_name": "a4 paper", "brand": "AmazonBasics", "size": "500 sheets", "unit_price": 6.49, "delivery_fee": 0.0, "stock_qty": 120, "eta_minutes": 2160, "rating": 4.5},
        {"sku": "MM-WD40-1", "title": "WD-40 Multi-Use Can with Smart Straw 300ml", "item_name": "wd-40", "brand": "WD-40", "size": "300ml", "unit_price": 6.99, "delivery_fee": 0.0, "stock_qty": 50, "eta_minutes": 1440, "rating": 4.8},
        {"sku": "MM-BATT-1", "title": "AmazonBasics AA Alkaline Batteries 8-Pack", "item_name": "batteries", "brand": "AmazonBasics", "size": "8 pack", "unit_price": 5.99, "delivery_fee": 0.0, "stock_qty": 80, "eta_minutes": 1440, "rating": 4.6},
        {"sku": "MM-DETG-1", "title": "Tide Liquid Laundry Detergent 2L", "item_name": "detergent", "brand": "Tide", "size": "2L", "unit_price": 14.99, "delivery_fee": 0.0, "stock_qty": 40, "eta_minutes": 1440, "rating": 4.8},
    ],
    "bulkbarn": [
        {"sku": "BB-PROT-1", "title": "Bulk Whey Protein Isolate Unflavored 2.5kg", "item_name": "protein powder", "brand": "BulkBarn", "size": "2.5kg", "unit_price": 59.99, "delivery_fee": 0.0, "stock_qty": 30, "eta_minutes": 2880, "rating": 4.6},
        {"sku": "BB-PAPR-1", "title": "A4 Copy Paper Carton (5 Reams / 2500 Sheets)", "item_name": "a4 paper", "brand": "BulkBarn", "size": "2500 sheets", "unit_price": 27.50, "delivery_fee": 0.0, "stock_qty": 60, "eta_minutes": 2880, "rating": 4.5},
        {"sku": "BB-WD40-1", "title": "WD-40 Multi-Use Twin Pack 300ml x 2", "item_name": "wd-40", "brand": "WD-40", "size": "600ml", "unit_price": 12.50, "delivery_fee": 0.0, "stock_qty": 25, "eta_minutes": 2160, "rating": 4.7},
    ]
}
