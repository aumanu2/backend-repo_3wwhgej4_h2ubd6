"""
BackendForge Database Schemas

Each Pydantic model maps to a MongoDB collection using the lowercase class name.
All resources are project-scoped: include project_id on every model that belongs
to a specific project.
"""
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

# Core
class Project(BaseModel):
    name: str = Field(..., description="Project name")
    db_type: Literal["PostgreSQL", "MySQL", "MongoDB"] = Field("MongoDB")
    region: str = Field("us-east-1")
    status: Literal["active", "provisioning", "error"] = Field("active")

class ActivityLog(BaseModel):
    project_id: str
    action: str
    details: Optional[str] = None
    actor: Optional[str] = None
    level: Literal["info", "warning", "error"] = "info"

# Database designer
class ColumnDef(BaseModel):
    name: str
    data_type: Literal["String", "Integer", "Boolean", "Date", "JSON", "Enum"]
    primary_key: bool = False
    required: bool = False
    default_value: Optional[Any] = None
    relation: Optional[str] = Field(None, description="Related table id")
    description: Optional[str] = None

class TableDef(BaseModel):
    project_id: str
    name: str
    description: Optional[str] = None
    columns: List[ColumnDef] = []

class Relationship(BaseModel):
    project_id: str
    name: str
    rel_type: Literal["One-to-One", "One-to-Many", "Many-to-Many"]
    source_table_id: str
    target_table_id: str
    on_delete: Literal["NO ACTION", "CASCADE", "SET NULL", "RESTRICT"] = "NO ACTION"
    on_update: Literal["NO ACTION", "CASCADE", "SET NULL", "RESTRICT"] = "NO ACTION"

# API
class ApiEndpoint(BaseModel):
    project_id: str
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    url: str
    auth_required: bool = True
    description: Optional[str] = None

class GraphQLSchema(BaseModel):
    project_id: str
    schema: Dict[str, Any]

# Auth
class AuthSettings(BaseModel):
    project_id: str
    jwt_enabled: bool = True
    oauth_google: bool = False
    oauth_github: bool = False
    oauth_microsoft: bool = False

class Role(BaseModel):
    project_id: str
    name: str
    description: Optional[str] = None
    permissions: List[str] = []

# Deployment
class Deployment(BaseModel):
    project_id: str
    environment: Literal["Dev", "QA", "Production"]
    status: Literal["Success", "Pending", "Failed"] = "Pending"
    logs: Optional[str] = None

# Settings sub-sections
class ApiKey(BaseModel):
    project_id: str
    name: str
    key: str

class TeamMember(BaseModel):
    project_id: str
    name: str
    role: str
    status: Literal["invited", "active", "removed"] = "invited"

# Analytics (aggregated points)
class AnalyticsPoint(BaseModel):
    project_id: str
    metric: Literal["api_usage", "response_time", "error_rate"]
    timestamp: int
    value: float
