import os
from typing import Any, Dict, List, Optional, Type
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import (
    Project,
    TableDef,
    Relationship,
    ApiEndpoint,
    GraphQLSchema,
    AuthSettings,
    Role,
    Deployment,
    ApiKey,
    TeamMember,
    ActivityLog,
    AnalyticsPoint,
)

app = FastAPI(title="BackendForge API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------- Helpers ---------
class StrObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        try:
            return ObjectId(str(v))
        except Exception:  # noqa: BLE001
            raise ValueError("Invalid ObjectId")

def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    out = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            out[k] = str(v)
        elif isinstance(v, list):
            out[k] = [serialize_doc(i) if isinstance(i, dict) else (str(i) if isinstance(i, ObjectId) else i) for i in v]
        elif isinstance(v, dict):
            out[k] = serialize_doc(v)
        else:
            out[k] = v
    return out

# Generic CRUD registry
ModelMap: Dict[str, Type[BaseModel]] = {
    "projects": Project,
    "tables": TableDef,
    "relationships": Relationship,
    "api-endpoints": ApiEndpoint,
    "graphql-schemas": GraphQLSchema,
    "auth-settings": AuthSettings,
    "roles": Role,
    "deployments": Deployment,
    "api-keys": ApiKey,
    "team-members": TeamMember,
    "activity": ActivityLog,
    "analytics": AnalyticsPoint,
}

# Resolve collection name from model (lowercase class name)
def collection_name(model: Type[BaseModel]) -> str:
    return model.__name__.lower()

# ---------- Root & Health ----------
@app.get("/")
def read_root():
    return {"message": "BackendForge API running"}

@app.get("/health")
def health():
    ok = db is not None
    return {"status": "ok" if ok else "error"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set",
        "database_name": "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": [],
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:20]
                response["database"] = "✅ Connected & Working"
            except Exception as e:  # noqa: BLE001
                response["database"] = f"⚠️  Connected but Error: {str(e)[:80]}"
    except Exception as e:  # noqa: BLE001
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response

# ---------- Projects (rich endpoints) ----------
@app.get("/projects")
def list_projects() -> JSONResponse:
    docs = get_documents(collection_name(Project), {}) if db else []
    return JSONResponse([serialize_doc(d) for d in docs])

@app.post("/projects")
def create_project(payload: Project) -> JSONResponse:
    _id = create_document(collection_name(Project), payload)
    # seed default auth settings and environments
    create_document(collection_name(AuthSettings), AuthSettings(project_id=_id))
    for env in ["Dev", "QA", "Production"]:
        create_document(collection_name(Deployment), Deployment(project_id=_id, environment=env))
    return JSONResponse({"id": _id})

@app.delete("/projects/{project_id}")
def delete_project(project_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    # naive cascade: mark project removed and leave data (demo purpose)
    res = db[collection_name(Project)].delete_one({"_id": StrObjectId.validate(project_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "ok"}

# ---------- Generic project-scoped CRUD ----------

class IdResponse(BaseModel):
    id: str

@app.get("/{resource}")
def list_by_project(resource: str, project_id: Optional[str] = Query(None)):
    if resource not in ModelMap:
        raise HTTPException(status_code=404, detail="Unknown resource")
    if db is None:
        return []
    filt = {"project_id": project_id} if project_id else {}
    docs = get_documents(collection_name(ModelMap[resource]), filt)
    return [serialize_doc(d) for d in docs]

@app.post("/{resource}", response_model=IdResponse)
def create_item(resource: str, payload: Dict[str, Any]):
    if resource not in ModelMap:
        raise HTTPException(status_code=404, detail="Unknown resource")
    model = ModelMap[resource]
    try:
        obj = model(**payload)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=str(e))
    _id = create_document(collection_name(model), obj)
    return IdResponse(id=_id)

@app.put("/{resource}/{item_id}")
def update_item(resource: str, item_id: str, payload: Dict[str, Any]):
    if resource not in ModelMap:
        raise HTTPException(status_code=404, detail="Unknown resource")
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    # Validate payload with model but allow partial by intersecting fields
    model = ModelMap[resource]
    try:
        model(**{k: v for k, v in payload.items() if k in model.model_fields})
    except Exception:
        pass
    res = db[collection_name(model)].update_one(
        {"_id": StrObjectId.validate(item_id)}, {"$set": payload}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "ok"}

@app.delete("/{resource}/{item_id}")
def delete_item(resource: str, item_id: str):
    if resource not in ModelMap:
        raise HTTPException(status_code=404, detail="Unknown resource")
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    res = db[collection_name(ModelMap[resource])].delete_one({"_id": StrObjectId.validate(item_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
