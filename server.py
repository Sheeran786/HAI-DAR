from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import logging
import os
import secrets
import uuid

import jwt
from bson import ObjectId
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from pydantic import BaseModel, Field, ConfigDict
from pymongo.errors import DuplicateKeyError
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]
JWT_SECRET = os.getenv("JWT_SECRET", "haidar-development-secret-change-me")
ADMIN_EMAIL_DEFAULT = os.getenv("ADMIN_EMAIL", "admin@haidartools.in")
ADMIN_PASSWORD_ENV = os.getenv("ADMIN_PASSWORD")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
DUMMY_HASH = pwd_context.hash("dummy-value-used-only-for-timing")


def hash_password(value: str) -> str:
    return pwd_context.hash(value)


def verify_password(value: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(value, hashed)
    except (ValueError, TypeError):
        return False


CREDENTIALS_FILE = Path("/app/memory/test_credentials.md")


def write_admin_credentials(email: str, password: str) -> None:
    body = (
        "# HAI-DAR Test Credentials\n\n"
        "## Admin Control Room (Email + Password)\n"
        f"- Email: `{email}`\n"
        f"- Password: `{password}`\n"
        "- Access: App → Profile tab → \"Admin control room\" → email + password sheet\n\n"
        "## Customer OTP Login (Dummy Development Flow)\n"
        "- Mobile: any valid 10-digit mobile number (e.g. `9999999999`)\n"
        "- OTP: any 4-digit numeric code (e.g. `1234`)\n\n"
        "## Notes\n"
        "- Admin credentials are stored in MongoDB (`admins` collection) with a bcrypt hash. The plain password shown above is only recorded here for the operator; change it after first sign-in.\n"
        "- OTP delivery is simulated; no real SMS is sent yet.\n"
        "- WhatsApp number is configurable from Admin → Settings.\n"
    )
    try:
        CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        CREDENTIALS_FILE.write_text(body, encoding="utf-8")
    except OSError:
        pass

app = FastAPI(title="HAI-DAR Wholesale API", version="1.0.0")
api_router = APIRouter(prefix="/api")
logger = logging.getLogger("haidar")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not doc:
        return None
    result = dict(doc)
    result.pop("_id", None)
    for key, value in list(result.items()):
        if isinstance(value, ObjectId):
            result[key] = str(value)
    return result


def token_for(subject: str, role: str) -> str:
    return jwt.encode(
        {"sub": subject, "role": role, "exp": datetime.now(timezone.utc) + timedelta(days=14)},
        JWT_SECRET,
        algorithm="HS256",
    )


async def current_identity(authorization: Optional[str] = Header(default=None)) -> Dict[str, str]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return jwt.decode(authorization.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session") from exc


async def admin_identity(identity: Dict[str, str] = Depends(current_identity)) -> Dict[str, str]:
    if identity.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return identity


class Variant(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    label: str
    sku: str
    weight: Optional[str] = ""
    moq: int = 1
    wholesale_price: Optional[float] = None
    stock: int = 0


class ProductCreate(BaseModel):
    name: str
    category: str
    sku: str
    description: str = ""
    specifications: List[str] = Field(default_factory=list)
    packaging: str = "Standard factory carton"
    delivery: str = "Pan India delivery available"
    image_data: List[str] = Field(default_factory=list)
    variants: List[Variant] = Field(default_factory=list)
    featured: bool = False
    is_new: bool = False
    active: bool = True
    badge: str = ""


class ProductPatch(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: Optional[str] = None
    category: Optional[str] = None
    sku: Optional[str] = None
    description: Optional[str] = None
    specifications: Optional[List[str]] = None
    packaging: Optional[str] = None
    delivery: Optional[str] = None
    image_data: Optional[List[str]] = None
    variants: Optional[List[Variant]] = None
    featured: Optional[bool] = None
    is_new: Optional[bool] = None
    active: Optional[bool] = None
    badge: Optional[str] = None


class EnquiryCreate(BaseModel):
    customer_name: str
    business_name: str
    mobile: str
    whatsapp: str
    city: str
    state: str
    product: str
    required_quantity: int
    message: str = ""
    items: List[Dict[str, Any]] = Field(default_factory=list)


class OrderCreate(BaseModel):
    items: List[Dict[str, Any]]
    customer_name: str = ""
    business_name: str = ""
    mobile: str = ""
    total: float


class SettingsPatch(BaseModel):
    whatsapp: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    delivery_info: Optional[str] = None
    announcement: Optional[str] = None


DEFAULT_SETTINGS = {
    "id": "business",
    "whatsapp": "919999999999",
    "phone": "+91 99999 99999",
    "email": "sales@haidartools.in",
    "address": "HAI-DAR Factory, India",
    "delivery_info": "Pan India delivery available for wholesale orders.",
    "announcement": "Factory-direct wholesale supply across India",
}

SEED_PRODUCTS = [
    {
        "name": "HAI-DAR Sledge Hammer",
        "category": "Sledge Hammer",
        "sku": "HD-SH-001",
        "description": "Heavy-duty forged sledge hammer for demanding construction and fabrication work.",
        "specifications": ["Forged steel head", "High-grip handle", "Factory packed"],
        "packaging": "6 pieces per carton",
        "delivery": "Dispatch in 3–5 business days",
        "image_data": [],
        "variants": [
            {"id": "sh-1", "label": "1 LB", "sku": "HD-SH-1", "weight": "1 LB", "moq": 24, "wholesale_price": 210, "stock": 240},
            {"id": "sh-2", "label": "2 LB", "sku": "HD-SH-2", "weight": "2 LB", "moq": 24, "wholesale_price": 285, "stock": 180},
            {"id": "sh-4", "label": "4 LB", "sku": "HD-SH-4", "weight": "4 LB", "moq": 12, "wholesale_price": 420, "stock": 96},
        ],
        "featured": True, "is_new": False, "active": True, "badge": "FACTORY DIRECT",
    },
    {
        "name": "HAI-DAR Claw Hammer",
        "category": "Claw Hammer",
        "sku": "HD-CH-002",
        "description": "Balanced claw hammer with a strong striking face for hardware and workshop buyers.",
        "specifications": ["Drop forged head", "Comfort handle", "Polished claw"],
        "packaging": "12 pieces per carton",
        "delivery": "Ready stock",
        "image_data": [],
        "variants": [
            {"id": "ch-16", "label": "16 OZ", "sku": "HD-CH-16", "weight": "16 OZ", "moq": 24, "wholesale_price": 175, "stock": 320},
            {"id": "ch-20", "label": "20 OZ", "sku": "HD-CH-20", "weight": "20 OZ", "moq": 24, "wholesale_price": 205, "stock": 220},
        ],
        "featured": True, "is_new": True, "active": True, "badge": "NEW",
    },
    {
        "name": "HAI-DAR Cold Chisel",
        "category": "Cold Chisel",
        "sku": "HD-CC-003",
        "description": "Industrial cold chisel designed for controlled cutting and shaping applications.",
        "specifications": ["Heat-treated steel", "Precision ground edge", "Rust-resistant finish"],
        "packaging": "24 pieces per carton",
        "delivery": "Ready stock",
        "image_data": [],
        "variants": [
            {"id": "cc-6", "label": "6 IN", "sku": "HD-CC-6", "weight": "6 IN", "moq": 48, "wholesale_price": 72, "stock": 600},
            {"id": "cc-8", "label": "8 IN", "sku": "HD-CC-8", "weight": "8 IN", "moq": 48, "wholesale_price": 95, "stock": 410},
        ],
        "featured": False, "is_new": True, "active": True, "badge": "BULK READY",
    },
    {
        "name": "HAI-DAR Hexa Frame",
        "category": "Hexa Frame",
        "sku": "HD-HF-004",
        "description": "Reliable hacksaw frame for hardware counters, maintenance teams and industrial buyers.",
        "specifications": ["Rigid steel frame", "Quick blade change", "Contractor grade"],
        "packaging": "12 pieces per carton",
        "delivery": "Ready stock",
        "image_data": [],
        "variants": [{"id": "hf-12", "label": "12 IN", "sku": "HD-HF-12", "weight": "12 IN", "moq": 24, "wholesale_price": 160, "stock": 150}],
        "featured": True, "is_new": False, "active": True, "badge": "WHOLESALE",
    },
]


@app.on_event("startup")
async def seed_database() -> None:
    if await db.settings.count_documents({}) == 0:
        await db.settings.insert_one(dict(DEFAULT_SETTINGS))
    if await db.products.count_documents({}) == 0:
        stamp = now_iso()
        for item in SEED_PRODUCTS:
            item["id"] = str(uuid.uuid4())
            item["created_at"] = stamp
        await db.products.insert_many(SEED_PRODUCTS)
    await db.admins.create_index("email", unique=True, name="uq_admin_email")
    if await db.admins.count_documents({}, limit=1) == 0:
        email = ADMIN_EMAIL_DEFAULT.strip().lower()
        # Prefer operator-supplied password from env; otherwise generate a strong random one so the operator can log in.
        seeded_password = (ADMIN_PASSWORD_ENV or secrets.token_urlsafe(18)).strip() or secrets.token_urlsafe(18)
        try:
            await db.admins.insert_one({
                "id": str(uuid.uuid4()),
                "email": email,
                "password_hash": hash_password(seeded_password),
                "created_at": now_iso(),
            })
            logger.warning("HAI-DAR ADMIN SEEDED: email=%s password=%s", email, seeded_password)
            write_admin_credentials(email, seeded_password)
        except DuplicateKeyError:
            pass


@api_router.get("/")
async def root() -> Dict[str, str]:
    return {"message": "HAI-DAR wholesale systems online"}


@api_router.get("/settings")
async def get_settings() -> Dict[str, Any]:
    settings = await db.settings.find_one({"id": "business"}, {"_id": 0})
    return settings or DEFAULT_SETTINGS


@api_router.patch("/admin/settings")
async def update_settings(payload: SettingsPatch, _: Dict[str, str] = Depends(admin_identity)) -> Dict[str, Any]:
    updates = {key: value for key, value in payload.model_dump().items() if value is not None}
    await db.settings.update_one({"id": "business"}, {"$set": updates}, upsert=True)
    settings = await db.settings.find_one({"id": "business"}, {"_id": 0})
    return settings or DEFAULT_SETTINGS


@api_router.get("/products")
async def list_products(
    search: str = Query(default=""),
    category: str = Query(default=""),
    sort: str = Query(default="featured"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=40, ge=1, le=100),
) -> Dict[str, Any]:
    query: Dict[str, Any] = {"active": True}
    if category and category != "All":
        query["category"] = category
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"sku": {"$regex": search, "$options": "i"}},
            {"category": {"$regex": search, "$options": "i"}},
            {"variants.label": {"$regex": search, "$options": "i"}},
            {"variants.sku": {"$regex": search, "$options": "i"}},
        ]
    sort_field = [("created_at", -1)]
    if sort == "price_low":
        sort_field = [("variants.wholesale_price", 1)]
    elif sort == "price_high":
        sort_field = [("variants.wholesale_price", -1)]
    elif sort == "newest":
        sort_field = [("created_at", -1)]
    elif sort == "name":
        sort_field = [("name", 1)]
    cursor = db.products.find(query, {"_id": 0}).sort(sort_field).skip((page - 1) * limit).limit(limit)
    products = [clean_doc(doc) async for doc in cursor]
    categories = await db.products.distinct("category", {"active": True})
    return {"items": products, "categories": sorted(categories), "page": page, "has_more": len(products) == limit}


@api_router.get("/products/{product_id}")
async def get_product(product_id: str) -> Dict[str, Any]:
    product = await db.products.find_one({"id": product_id, "active": True}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Product unavailable")
    return clean_doc(product) or {}


@api_router.get("/admin/products")
async def admin_products(_: Dict[str, str] = Depends(admin_identity)) -> List[Dict[str, Any]]:
    return [clean_doc(doc) async for doc in db.products.find({}, {"_id": 0}).sort("created_at", -1)]


@api_router.post("/admin/products")
async def create_product(payload: ProductCreate, _: Dict[str, str] = Depends(admin_identity)) -> Dict[str, Any]:
    product = payload.model_dump()
    product.update({"id": str(uuid.uuid4()), "created_at": now_iso()})
    await db.products.insert_one(dict(product))
    return product


@api_router.patch("/admin/products/{product_id}")
async def patch_product(product_id: str, payload: ProductPatch, _: Dict[str, str] = Depends(admin_identity)) -> Dict[str, Any]:
    updates = {key: value for key, value in payload.model_dump().items() if value is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No product changes supplied")
    result = await db.products.update_one({"id": product_id}, {"$set": updates})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Product not found")
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    return clean_doc(product) or {}


@api_router.delete("/admin/products/{product_id}")
async def delete_product(product_id: str, _: Dict[str, str] = Depends(admin_identity)) -> Dict[str, bool]:
    result = await db.products.delete_one({"id": product_id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"deleted": True}


@api_router.post("/auth/request-otp")
async def request_otp(mobile: str) -> Dict[str, str]:
    cleaned = mobile.strip()
    digits = "".join(ch for ch in cleaned if ch.isdigit())
    if len(digits) < 7:
        raise HTTPException(status_code=400, detail="Enter a valid mobile number")
    await db.otp_codes.update_one({"mobile": cleaned}, {"$set": {"mobile": cleaned, "code": "dev", "created_at": now_iso()}}, upsert=True)
    return {"message": "Development mode: enter any 4-digit OTP to continue", "dev_code": "1234"}


@api_router.post("/auth/verify-otp")
async def verify_otp(mobile: str, code: str) -> Dict[str, Any]:
    cleaned_mobile = mobile.strip()
    cleaned_code = code.strip()
    digits = "".join(ch for ch in cleaned_mobile if ch.isdigit())
    if len(digits) < 7:
        raise HTTPException(status_code=400, detail="Enter a valid mobile number")
    if not (cleaned_code.isdigit() and len(cleaned_code) == 4):
        raise HTTPException(status_code=401, detail="Enter the 4-digit development OTP")
    user = await db.customers.find_one({"mobile": cleaned_mobile}, {"_id": 0})
    if not user:
        user = {"id": str(uuid.uuid4()), "mobile": cleaned_mobile, "name": "", "business_name": "", "city": "", "state": "", "created_at": now_iso()}
        await db.customers.insert_one(dict(user))
    return {"token": token_for(user["id"], "customer"), "user": clean_doc(user)}


@api_router.post("/auth/admin-login")
async def admin_login(email: str, password: str) -> Dict[str, str]:
    normalized = (email or "").strip().lower()
    admin = await db.admins.find_one({"email": normalized}, {"_id": 0})
    stored_hash = admin["password_hash"] if admin else DUMMY_HASH
    # Always run bcrypt so response time does not leak whether the email exists.
    valid = verify_password(password or "", stored_hash)
    if not admin or not valid:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return {"token": token_for(admin["id"], "admin"), "role": "admin"}


@api_router.post("/enquiries")
async def create_enquiry(payload: EnquiryCreate, identity: Dict[str, str] = Depends(current_identity)) -> Dict[str, Any]:
    enquiry = payload.model_dump()
    enquiry.update({"id": f"ENQ-{datetime.now(timezone.utc).strftime('%y%m%d')}-{uuid.uuid4().hex[:4].upper()}", "customer_id": identity.get("sub"), "status": "Enquiry Received", "sales_response": "", "sales_notes": "", "created_at": now_iso()})
    await db.enquiries.insert_one(dict(enquiry))
    return enquiry


@api_router.get("/enquiries")
async def customer_enquiries(identity: Dict[str, str] = Depends(current_identity)) -> List[Dict[str, Any]]:
    return [clean_doc(doc) async for doc in db.enquiries.find({"customer_id": identity.get("sub")}, {"_id": 0}).sort("created_at", -1)]


@api_router.get("/enquiries/{enquiry_id}")
async def customer_enquiry_detail(enquiry_id: str, identity: Dict[str, str] = Depends(current_identity)) -> Dict[str, Any]:
    enquiry = await db.enquiries.find_one({"id": enquiry_id, "customer_id": identity.get("sub")}, {"_id": 0})
    if not enquiry:
        raise HTTPException(status_code=404, detail="Enquiry not found")
    return clean_doc(enquiry) or {}


@api_router.get("/admin/enquiries")
async def admin_enquiries(_: Dict[str, str] = Depends(admin_identity)) -> List[Dict[str, Any]]:
    return [clean_doc(doc) async for doc in db.enquiries.find({}, {"_id": 0}).sort("created_at", -1)]


@api_router.patch("/admin/enquiries/{enquiry_id}")
async def update_enquiry(enquiry_id: str, status: str, sales_notes: str = "", _: Dict[str, str] = Depends(admin_identity)) -> Dict[str, Any]:
    await db.enquiries.update_one({"id": enquiry_id}, {"$set": {"status": status, "sales_notes": sales_notes}})
    enquiry = await db.enquiries.find_one({"id": enquiry_id}, {"_id": 0})
    if not enquiry:
        raise HTTPException(status_code=404, detail="Enquiry not found")
    return clean_doc(enquiry) or {}


@api_router.post("/orders")
async def create_order(payload: OrderCreate, identity: Dict[str, str] = Depends(current_identity)) -> Dict[str, Any]:
    order = payload.model_dump()
    order.update({"id": f"HD-{datetime.now(timezone.utc).strftime('%y%m%d')}-{uuid.uuid4().hex[:4].upper()}", "customer_id": identity.get("sub"), "status": "Enquiry Received", "tracking": "", "created_at": now_iso()})
    await db.orders.insert_one(dict(order))
    return order


@api_router.get("/orders")
async def customer_orders(identity: Dict[str, str] = Depends(current_identity)) -> List[Dict[str, Any]]:
    return [clean_doc(doc) async for doc in db.orders.find({"customer_id": identity.get("sub")}, {"_id": 0}).sort("created_at", -1)]


@api_router.get("/orders/{order_id}")
async def customer_order_detail(order_id: str, identity: Dict[str, str] = Depends(current_identity)) -> Dict[str, Any]:
    order = await db.orders.find_one({"id": order_id, "customer_id": identity.get("sub")}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return clean_doc(order) or {}


@api_router.get("/admin/orders")
async def admin_orders(_: Dict[str, str] = Depends(admin_identity)) -> List[Dict[str, Any]]:
    return [clean_doc(doc) async for doc in db.orders.find({}, {"_id": 0}).sort("created_at", -1)]


@api_router.patch("/admin/orders/{order_id}")
async def update_order(order_id: str, status: str, tracking: str = "", _: Dict[str, str] = Depends(admin_identity)) -> Dict[str, Any]:
    await db.orders.update_one({"id": order_id}, {"$set": {"status": status, "tracking": tracking}})
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return clean_doc(order) or {}


app.include_router(api_router)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("shutdown")
async def shutdown_db_client() -> None:
    client.close()