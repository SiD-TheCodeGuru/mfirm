import asyncio
from datetime import datetime, time, timezone
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext

# Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "mushroom_db")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


async def setup_collection_validators(db):
    print("--> Configuring collection validators and schema rules...")
    existing_collections = await db.list_collection_names()

    # 1. USERS
    users_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["_id", "username", "email", "hashed_password", "role", "is_active", "entry_dtm", "udate_dtm"],
            "properties": {
                "_id": {"bsonType": "string"},
                "username": {"bsonType": "string"},
                "email": {"bsonType": "string"},
                "hashed_password": {"bsonType": "string"},
                "full_name": {"bsonType": "string"},
                "phone": {"bsonType": ["string", "null"]},
                "role": {"enum": ["sys_admin", "firm_admin"]},
                "firm_id": {"bsonType": ["string", "null"]},
                "is_active": {"bsonType": "bool"},
                "entry_dtm": {"bsonType": "date"},
                "udate_dtm": {"bsonType": "date"},
            },
        }
    }

    # 2. FIRMS
    firms_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["_id", "firm_id", "firm_name", "is_active", "entry_dtm", "udate_dtm"],
            "properties": {
                "_id": {"bsonType": "string"},
                "firm_id": {"bsonType": "string"},
                "firm_name": {"bsonType": "string"},
                "address": {"bsonType": ["string", "null"]},
                "contact_number": {"bsonType": ["string", "null"]},
                "is_active": {"bsonType": "bool"},
                "entry_dtm": {"bsonType": "date"},
                "udate_dtm": {"bsonType": "date"},
            },
        }
    }

    # 3. ITEMS
    items_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["_id", "item_id", "item_name", "category", "default_unit", "firm_id", "user_id", "entry_dtm", "udate_dtm"],
            "properties": {
                "_id": {"bsonType": "string"},
                "item_id": {"bsonType": "string"},
                "item_name": {"bsonType": "string"},
                "category": {"bsonType": "string"},
                "default_unit": {"enum": ["ltr", "kg", "packets", "bags", "bottles", "pieces"]},
                "remarks": {"bsonType": ["string", "null"]},
                "firm_id": {"bsonType": "string"},
                "user_id": {"bsonType": "string"},
                "entry_dtm": {"bsonType": "date"},
                "udate_dtm": {"bsonType": "date"},
            },
        }
    }

    # 4. STOCKS
    stocks_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["_id", "stock_id", "item_id", "category", "quantity", "unit", "firm_id", "user_id", "entry_dtm", "udate_dtm"],
            "properties": {
                "_id": {"bsonType": "string"},
                "stock_id": {"bsonType": "string"},
                "item_id": {"bsonType": "string"},
                "category": {"bsonType": "string"},
                "quantity": {"bsonType": "double"},
                "unit": {"enum": ["ltr", "kg", "packets", "bags", "bottles", "pieces"]},
                "warehouse_location": {"bsonType": ["string", "null"]},
                "remarks": {"bsonType": ["string", "null"]},
                "firm_id": {"bsonType": "string"},
                "user_id": {"bsonType": "string"},
                "entry_dtm": {"bsonType": "date"},
                "udate_dtm": {"bsonType": "date"},
            },
        }
    }

    # 5. PURCHASED (Invoice Header)
    purchased_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["_id", "slno", "invoice_no", "invoice_date", "tax_paid", "total_paid", "payment_mode", "items", "firm_id", "user_id", "entry_dtm", "udate_dtm"],
            "properties": {
                "_id": {"bsonType": "string"},
                "slno": {"bsonType": "int"},
                "invoice_no": {"bsonType": "string"},
                "invoice_date": {"bsonType": "date"},
                "vendor_name": {"bsonType": ["string", "null"]},
                "tax_paid": {"bsonType": "double"},
                "total_paid": {"bsonType": "double"},
                "payment_mode": {"enum": ["CASH", "BANK_TRANSFER", "UPI", "CREDIT"]},
                "items": {"bsonType": "array"},
                "remarks": {"bsonType": ["string", "null"]},
                "firm_id": {"bsonType": "string"},
                "user_id": {"bsonType": "string"},
                "entry_dtm": {"bsonType": "date"},
                "udate_dtm": {"bsonType": "date"},
            },
        }
    }

    # 6. PURCHASED_ITEMS (Invoice Line Items)
    purchased_items_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["_id", "slno", "purchase_slno", "invoice_no", "item_id", "quantity", "unit", "purchage_amt", "firm_id", "user_id", "entry_dtm", "udate_dtm"],
            "properties": {
                "_id": {"bsonType": "string"},
                "slno": {"bsonType": "int"},
                "purchase_slno": {"bsonType": "int"},
                "invoice_no": {"bsonType": "string"},
                "item_id": {"bsonType": "string"},
                "quantity": {"bsonType": "double"},
                "unit": {"enum": ["ltr", "kg", "packets", "bags", "bottles", "pieces"]},
                "purchage_amt": {"bsonType": "double"},
                "remarks": {"bsonType": ["string", "null"]},
                "firm_id": {"bsonType": "string"},
                "user_id": {"bsonType": "string"},
                "entry_dtm": {"bsonType": "date"},
                "udate_dtm": {"bsonType": "date"},
            },
        }
    }

    # 7. EXPENSES
    expenses_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["_id", "expense_id", "slno", "expense_date", "category", "amount", "payment_mode", "firm_id", "user_id", "entry_dtm", "udate_dtm"],
            "properties": {
                "_id": {"bsonType": "string"},
                "expense_id": {"bsonType": "string"},
                "slno": {"bsonType": "int"},
                "expense_date": {"bsonType": "date"},
                "category": {"enum": ["LABOR", "ELECTRICITY", "WATER", "FUEL_FIREWOOD", "TRANSPORT", "REPAIR_MAINTENANCE", "RENT", "MISC"]},
                "amount": {"bsonType": "double"},
                "paid_to": {"bsonType": ["string", "null"]},
                "payment_mode": {"enum": ["CASH", "BANK_TRANSFER", "UPI", "CREDIT"]},
                "remarks": {"bsonType": ["string", "null"]},
                "firm_id": {"bsonType": "string"},
                "user_id": {"bsonType": "string"},
                "entry_dtm": {"bsonType": "date"},
                "udate_dtm": {"bsonType": "date"},
            },
        }
    }

    # 8. BATCHES
    batches_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["_id", "batch_id", "batch_code", "spawn_date", "room_no", "bag_count", "dry_substrate_weight_kg", "status", "total_yield_kg", "firm_id", "user_id", "entry_dtm", "udate_dtm"],
            "properties": {
                "_id": {"bsonType": "string"},
                "batch_id": {"bsonType": "string"},
                "batch_code": {"bsonType": "string"},
                "spawn_date": {"bsonType": "date"},
                "room_no": {"bsonType": "string"},
                "bag_count": {"bsonType": "int"},
                "dry_substrate_weight_kg": {"bsonType": "double"},
                "consumed_materials": {
                    "bsonType": "array",
                    "items": {
                        "bsonType": "object",
                        "required": ["item_id", "item_name", "quantity", "unit"],
                        "properties": {
                            "item_id": {"bsonType": "string"},
                            "item_name": {"bsonType": "string"},
                            "category": {"bsonType": "string"},
                            "quantity": {"bsonType": "double"},
                            "unit": {"bsonType": "string"},
                        },
                    },
                },
                "status": {"enum": ["INCUBATION", "FRUITING", "COMPLETED", "DISCARDED"]},
                "total_yield_kg": {"bsonType": "double"},
                "biological_efficiency": {"bsonType": ["double", "null"]},
                "remarks": {"bsonType": ["string", "null"]},
                "firm_id": {"bsonType": "string"},
                "user_id": {"bsonType": "string"},
                "entry_dtm": {"bsonType": "date"},
                "udate_dtm": {"bsonType": "date"},
            },
        }
    }

    # 9. HARVEST_LOGS
    harvest_logs_validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["_id", "log_id", "batch_id", "harvest_date", "flush_number", "weight_kg", "grade", "firm_id", "user_id", "entry_dtm", "udate_dtm"],
            "properties": {
                "_id": {"bsonType": "string"},
                "log_id": {"bsonType": "string"},
                "batch_id": {"bsonType": "string"},
                "harvest_date": {"bsonType": "date"},
                "flush_number": {"enum": [1, 2, 3]},
                "weight_kg": {"bsonType": "double"},
                "grade": {"enum": ["A_GRADE", "B_GRADE", "COMMERCIAL"]},
                "harvested_item_id": {"bsonType": ["string", "null"]},
                "remarks": {"bsonType": ["string", "null"]},
                "firm_id": {"bsonType": "string"},
                "user_id": {"bsonType": "string"},
                "entry_dtm": {"bsonType": "date"},
                "udate_dtm": {"bsonType": "date"},
            },
        }
    }

    all_specs = [
        ("users", users_validator),
        ("firms", firms_validator),
        ("items", items_validator),
        ("stocks", stocks_validator),
        ("purchased", purchased_validator),
        ("purchased_items", purchased_items_validator),
        ("expenses", expenses_validator),
        ("batches", batches_validator),
        ("harvest_logs", harvest_logs_validator),
    ]

    for coll_name, schema in all_specs:
        if coll_name in existing_collections:
            await db.command({
                "collMod": coll_name,
                "validator": schema,
                "validationLevel": "moderate",
            })
        else:
            await db.create_collection(
                coll_name,
                validator=schema,
                validationLevel="moderate",
            )

    # Counters collection (no schema needed)
    if "counters" not in existing_collections:
        await db.create_collection("counters")

    print("--> All validators applied with moderate validation level.")


async def create_indexes(db):
    print("--> Creating database indexes...")
    # Unique compound indexes
    await db.users.create_index([("username", 1)], unique=True)
    await db.users.create_index([("email", 1)], unique=True)
    await db.firms.create_index([("firm_id", 1)], unique=True)
    await db.items.create_index([("firm_id", 1), ("item_name", 1)], unique=True)
    await db.stocks.create_index([("firm_id", 1), ("item_id", 1)], unique=True)
    await db.purchased.create_index([("firm_id", 1), ("invoice_no", 1)], unique=True)
    await db.batches.create_index([("firm_id", 1), ("batch_code", 1)], unique=True)

    # Query & sorting indexes
    await db.expenses.create_index([("firm_id", 1), ("expense_date", -1)])
    await db.harvest_logs.create_index([("batch_id", 1), ("harvest_date", -1)])
    print("--> Indexes successfully created.")


async def seed_data(db):
    now_dt = datetime.now(timezone.utc)
    print("--> Seeding core application documents...")

    # 1. FIRMS
    firm_doc = {
        "_id": "FIRM_001",
        "firm_id": "FIRM_001",
        "firm_name": "Sunrise Mushroom Farm",
        "address": "Bishalgarh Agri-Zone, Tripura",
        "contact_number": "+91 9876543210",
        "is_active": True,
        "entry_dtm": now_dt,
        "udate_dtm": now_dt,
    }
    await db.firms.update_one({"_id": firm_doc["_id"]}, {"$set": firm_doc}, upsert=True)

    # 2. USERS
    sys_admin = {
        "_id": "USR_SYS_ADMIN_01",
        "username": "sysadmin",
        "email": "sysadmin@mfirm.local",
        "hashed_password": hash_password("admin123"),
        "full_name": "System Administrator",
        "phone": "+91 9436123456",
        "role": "sys_admin",
        "firm_id": None,
        "is_active": True,
        "entry_dtm": now_dt,
        "udate_dtm": now_dt,
    }
    await db.users.update_one({"_id": sys_admin["_id"]}, {"$set": sys_admin}, upsert=True)

    firm_admin = {
        "_id": "USR_FIRM_ADMIN_01",
        "username": "sunrisemanager",
        "email": "manager@sunrisemushrooms.com",
        "hashed_password": hash_password("manager123"),
        "full_name": "Sunrise Farm Manager",
        "phone": "+91 9862112233",
        "role": "firm_admin",
        "firm_id": "FIRM_001",
        "is_active": True,
        "entry_dtm": now_dt,
        "udate_dtm": now_dt,
    }
    await db.users.update_one({"_id": firm_admin["_id"]}, {"$set": firm_admin}, upsert=True)

    # 3. ITEM MASTER CATALOG
    items_to_seed = [
        {
            "_id": "ITM_OYSTER_SPAWN",
            "item_id": "ITM_OYSTER_SPAWN",
            "item_name": "Oyster Mushroom Spawn (Pleurotus florida)",
            "category": "Spawn",
            "default_unit": "packets",
            "remarks": "Mother spawn packets (200g standard)",
            "firm_id": "FIRM_001",
            "user_id": firm_admin["_id"],
            "entry_dtm": now_dt,
            "udate_dtm": now_dt,
        },
        {
            "_id": "ITM_PADDY_STRAW",
            "item_id": "ITM_PADDY_STRAW",
            "item_name": "Dry Paddy Straw",
            "category": "Raw Material",
            "default_unit": "kg",
            "remarks": "Clean sorted golden paddy straw",
            "firm_id": "FIRM_001",
            "user_id": firm_admin["_id"],
            "entry_dtm": now_dt,
            "udate_dtm": now_dt,
        },
        {
            "_id": "ITM_PP_BAGS",
            "item_id": "ITM_PP_BAGS",
            "item_name": "PP Bags (12x18 inch, 150 gauge)",
            "category": "Packaging",
            "default_unit": "pieces",
            "remarks": "Autoclavable polypropylene bag rolls",
            "firm_id": "FIRM_001",
            "user_id": firm_admin["_id"],
            "entry_dtm": now_dt,
            "udate_dtm": now_dt,
        },
        {
            "_id": "ITM_CALCIUM_CARB",
            "item_id": "ITM_CALCIUM_CARB",
            "item_name": "Calcium Carbonate / Chalk Powder (CaCO3)",
            "category": "Chemical / Fertilizer",
            "default_unit": "kg",
            "remarks": "Substrate pH buffer stabilizer",
            "firm_id": "FIRM_001",
            "user_id": firm_admin["_id"],
            "entry_dtm": now_dt,
            "udate_dtm": now_dt,
        },
        {
            "_id": "ITM_FRESH_OYSTER",
            "item_id": "ITM_FRESH_OYSTER",
            "item_name": "Fresh Oyster Mushrooms (Grade A)",
            "category": "Fresh Mushroom",
            "default_unit": "kg",
            "remarks": "Daily plucked fresh mushroom crop",
            "firm_id": "FIRM_001",
            "user_id": firm_admin["_id"],
            "entry_dtm": now_dt,
            "udate_dtm": now_dt,
        },
    ]

    for itm in items_to_seed:
        await db.items.update_one({"_id": itm["_id"]}, {"$set": itm}, upsert=True)

    # 4. COUNTERS (Initialize atomic sequences)
    await db.counters.update_one(
        {"_id": "purchase_slno_FIRM_001"},
        {"$setOnInsert": {"seq": int(1)}},
        upsert=True,
    )
    await db.counters.update_one(
        {"_id": "purchased_item_slno_FIRM_001"},
        {"$setOnInsert": {"seq": int(3)}},
        upsert=True,
    )
    await db.counters.update_one(
        {"_id": "expense_slno_FIRM_001"},
        {"$setOnInsert": {"seq": int(1)}},
        upsert=True,
    )

    # 5. SAMPLE PURCHASE INVOICE & PURCHASED ITEMS
    inv_date = datetime.combine(now_dt.date(), time.min).replace(tzinfo=timezone.utc)
    purchase_slno = 1
    invoice_no = "INV-2026-001"

    line_items = [
        {
            "_id": "PITM_SEED_01",
            "slno": int(1),
            "purchase_slno": int(purchase_slno),
            "invoice_no": invoice_no,
            "item_id": "ITM_OYSTER_SPAWN",
            "quantity": float(100.0),
            "unit": "packets",
            "purchage_amt": float(2500.0),
            "remarks": "100 packets @ Rs 25/packet",
            "firm_id": "FIRM_001",
            "user_id": firm_admin["_id"],
            "entry_dtm": now_dt,
            "udate_dtm": now_dt,
        },
        {
            "_id": "PITM_SEED_02",
            "slno": int(2),
            "purchase_slno": int(purchase_slno),
            "invoice_no": invoice_no,
            "item_id": "ITM_PADDY_STRAW",
            "quantity": float(500.0),
            "unit": "kg",
            "purchage_amt": float(3000.0),
            "remarks": "500 kg @ Rs 6/kg",
            "firm_id": "FIRM_001",
            "user_id": firm_admin["_id"],
            "entry_dtm": now_dt,
            "udate_dtm": now_dt,
        },
        {
            "_id": "PITM_SEED_03",
            "slno": int(3),
            "purchase_slno": int(purchase_slno),
            "invoice_no": invoice_no,
            "item_id": "ITM_PP_BAGS",
            "quantity": float(500.0),
            "unit": "pieces",
            "purchage_amt": float(750.0),
            "remarks": "500 bags @ Rs 1.50/bag",
            "firm_id": "FIRM_001",
            "user_id": firm_admin["_id"],
            "entry_dtm": now_dt,
            "udate_dtm": now_dt,
        },
    ]

    for p_item in line_items:
        await db.purchased_items.update_one({"_id": p_item["_id"]}, {"$set": p_item}, upsert=True)

    purchase_doc = {
        "_id": "PUR_SEED_01",
        "slno": int(purchase_slno),
        "invoice_no": invoice_no,
        "invoice_date": inv_date,
        "vendor_name": "Tripura Bio-Agri Supplies",
        "tax_paid": float(250.0),
        "total_paid": float(6500.0),
        "payment_mode": "UPI",
        "items": [
            {"item_id": "ITM_OYSTER_SPAWN", "item_name": "Oyster Mushroom Spawn", "quantity": 100.0, "unit": "packets", "purchage_amt": 2500.0},
            {"item_id": "ITM_PADDY_STRAW", "item_name": "Dry Paddy Straw", "quantity": 500.0, "unit": "kg", "purchage_amt": 3000.0},
            {"item_id": "ITM_PP_BAGS", "item_name": "PP Bags", "quantity": 500.0, "unit": "pieces", "purchage_amt": 750.0},
        ],
        "remarks": "Season opening material purchase",
        "firm_id": "FIRM_001",
        "user_id": firm_admin["_id"],
        "entry_dtm": now_dt,
        "udate_dtm": now_dt,
    }
    await db.purchased.update_one({"_id": purchase_doc["_id"]}, {"$set": purchase_doc}, upsert=True)

    # 6. INITIAL STOCK BALANCES
    # (Reflects 100 Spawn bought minus 30 used in Batch below = 70 remaining)
    stock_records = [
        {
            "_id": "STK_SEED_SPAWN",
            "stock_id": "STK_SEED_SPAWN",
            "item_id": "ITM_OYSTER_SPAWN",
            "category": "Spawn",
            "quantity": float(70.0),
            "unit": "packets",
            "warehouse_location": "Spawn Cold Box",
            "remarks": "Inoculated fresh stock",
            "firm_id": "FIRM_001",
            "user_id": firm_admin["_id"],
            "entry_dtm": now_dt,
            "udate_dtm": now_dt,
        },
        {
            "_id": "STK_SEED_STRAW",
            "stock_id": "STK_SEED_STRAW",
            "item_id": "ITM_PADDY_STRAW",
            "category": "Raw Material",
            "quantity": float(350.0),
            "unit": "kg",
            "warehouse_location": "Shed 1 Straw Stack",
            "remarks": "Dry storage",
            "firm_id": "FIRM_001",
            "user_id": firm_admin["_id"],
            "entry_dtm": now_dt,
            "udate_dtm": now_dt,
        },
        {
            "_id": "STK_SEED_BAGS",
            "stock_id": "STK_SEED_BAGS",
            "item_id": "ITM_PP_BAGS",
            "category": "Packaging",
            "quantity": float(350.0),
            "unit": "pieces",
            "warehouse_location": "Store Room Shelf B",
            "remarks": "Ready for filling",
            "firm_id": "FIRM_001",
            "user_id": firm_admin["_id"],
            "entry_dtm": now_dt,
            "udate_dtm": now_dt,
        },
        {
            "_id": "STK_SEED_FRESH",
            "stock_id": "STK_SEED_FRESH",
            "item_id": "ITM_FRESH_OYSTER",
            "category": "Fresh Mushroom",
            "quantity": float(18.5),
            "unit": "kg",
            "warehouse_location": "Cold Room / Harvest Tray",
            "remarks": "From Flush 1 morning picking",
            "firm_id": "FIRM_001",
            "user_id": firm_admin["_id"],
            "entry_dtm": now_dt,
            "udate_dtm": now_dt,
        },
    ]

    for stk in stock_records:
        await db.stocks.update_one({"_id": stk["_id"]}, {"$set": stk}, upsert=True)

    # 7. SAMPLE EXPENSES (Daily Labor & Firewood)
    expense_doc = {
        "_id": "EXP_SEED_01",
        "expense_id": "EXP_SEED_01",
        "slno": int(1),
        "expense_date": inv_date,
        "category": "LABOR",
        "amount": float(850.0),
        "paid_to": "Subrata Debnath & helper",
        "payment_mode": "CASH",
        "remarks": "Paddy straw chopping, boiling & cylinder filling wages",
        "firm_id": "FIRM_001",
        "user_id": firm_admin["_id"],
        "entry_dtm": now_dt,
        "udate_dtm": now_dt,
    }
    await db.expenses.update_one({"_id": expense_doc["_id"]}, {"$set": expense_doc}, upsert=True)

    # 8. SAMPLE BATCH
    batch_doc = {
        "_id": "BAT_SEED_01",
        "batch_id": "BAT_SEED_01",
        "batch_code": "OYST-2026-B1",
        "spawn_date": inv_date,
        "room_no": "Cropping Room 1",
        "bag_count": int(150),
        "dry_substrate_weight_kg": float(150.0),
        "consumed_materials": [
            {"item_id": "ITM_OYSTER_SPAWN", "item_name": "Oyster Mushroom Spawn", "category": "Spawn", "quantity": 30.0, "unit": "packets"},
            {"item_id": "ITM_PADDY_STRAW", "item_name": "Dry Paddy Straw", "category": "Raw Material", "quantity": 150.0, "unit": "kg"},
            {"item_id": "ITM_PP_BAGS", "item_name": "PP Bags", "category": "Packaging", "quantity": 150.0, "unit": "pieces"},
        ],
        "status": "FRUITING",
        "total_yield_kg": float(18.5),
        "biological_efficiency": float(12.33),  # (18.5 / 150.0) * 100
        "remarks": "First production run of October 2026",
        "firm_id": "FIRM_001",
        "user_id": firm_admin["_id"],
        "entry_dtm": now_dt,
        "udate_dtm": now_dt,
    }
    await db.batches.update_one({"_id": batch_doc["_id"]}, {"$set": batch_doc}, upsert=True)

    # 9. SAMPLE HARVEST LOG (Flush 1)
    harvest_doc = {
        "_id": "HRV_SEED_01",
        "log_id": "HRV_SEED_01",
        "batch_id": "BAT_SEED_01",
        "harvest_date": inv_date,
        "flush_number": int(1),
        "weight_kg": float(18.5),
        "grade": "A_GRADE",
        "harvested_item_id": "ITM_FRESH_OYSTER",
        "remarks": "Day 22 flush 1 initiation - excellent white cap formation",
        "firm_id": "FIRM_001",
        "user_id": firm_admin["_id"],
        "entry_dtm": now_dt,
        "udate_dtm": now_dt,
    }
    await db.harvest_logs.update_one({"_id": harvest_doc["_id"]}, {"$set": harvest_doc}, upsert=True)

    print("--> Database seeded successfully.")


async def main():
    print(f"Connecting to MongoDB at {MONGO_URI} (Database: '{DB_NAME}')...")
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    try:
        await setup_collection_validators(db)
        await create_indexes(db)
        await seed_data(db)
        print("\n=== SEED COMPLETE ===")
        print("Default Logins:")
        print("  • System Admin : sysadmin / admin123")
        print("  • Farm Admin   : sunrisemanager / manager123")
        print(f"Active Firm ID   : FIRM_001 (Sunrise Mushroom Farm)")
    except Exception as ex:
        print(f"\n[ERROR] Seed failed: {ex}")
        raise
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())