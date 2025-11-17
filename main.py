import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from bson import ObjectId

# FastAPI app
app = FastAPI(title="Flames Blue API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utilities
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

def serialize_id(obj_id: Any) -> str:
    try:
        return str(obj_id)
    except Exception:
        return obj_id

def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    d = dict(doc)
    if "_id" in d:
        d["id"] = serialize_id(d.pop("_id"))
    return d

# Root
@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}

# Health and DB check
@app.get("/api/health")
def health() -> Dict[str, Any]:
    response: Dict[str, Any] = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        from database import db
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else os.getenv("DATABASE_NAME")
            try:
                response["collections"] = db.list_collection_names()[:10]
                response["connection_status"] = "Connected"
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:100]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except ImportError:
        response["database"] = "❌ Database module not found"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:100]}"

    # Also mirror legacy keys for /test page compatibility
    legacy = {
        "database_url": "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set",
        "database_name": "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set",
    }
    response.update(legacy)
    return response

# Backwards-compatible /test endpoint
@app.get("/test")
def test_database():
    return health()

# Schemas endpoint: expose Pydantic model fields
@app.get("/api/schema")
def get_schema() -> Dict[str, Any]:
    import inspect
    import schemas as app_schemas
    schema_map: Dict[str, Any] = {}
    for name, obj in inspect.getmembers(app_schemas):
        if inspect.isclass(obj) and issubclass(obj, BaseModel) and obj is not BaseModel:
            model: BaseModel = obj
            schema_map[name] = {
                "collection": name.lower(),
                "fields": {k: str(v.annotation) for k, v in model.model_fields.items()},
                "required": [k for k, v in model.model_fields.items() if v.is_required()],
            }
    return schema_map

# ----- Users API -----
from schemas import User, Product  # type: ignore
from database import create_document, get_documents
from pymongo.errors import PyMongoError

@app.post("/api/users", status_code=201)
def create_user(user: User) -> Dict[str, str]:
    try:
        new_id = create_document("user", user)
        return {"id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users")
def list_users(limit: int = 50) -> List[Dict[str, Any]]:
    try:
        docs = get_documents("user", {}, min(max(limit, 1), 200))
        return [serialize_doc(d) for d in docs]
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users/{user_id}")
def get_user(user_id: str) -> Dict[str, Any]:
    try:
        from database import db
        if not ObjectId.is_valid(user_id):
            raise HTTPException(status_code=400, detail="Invalid user id")
        doc = db.user.find_one({"_id": ObjectId(user_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="User not found")
        return serialize_doc(doc)
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----- Products API -----
@app.post("/api/products", status_code=201)
def create_product(product: Product) -> Dict[str, str]:
    try:
        new_id = create_document("product", product)
        return {"id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products")
def list_products(limit: int = 50) -> List[Dict[str, Any]]:
    try:
        docs = get_documents("product", {}, min(max(limit, 1), 200))
        return [serialize_doc(d) for d in docs]
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products/{product_id}")
def get_product(product_id: str) -> Dict[str, Any]:
    try:
        from database import db
        if not ObjectId.is_valid(product_id):
            raise HTTPException(status_code=400, detail="Invalid product id")
        doc = db.product.find_one({"_id": ObjectId(product_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Product not found")
        return serialize_doc(doc)
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail=str(e))

# Legacy hello
@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
