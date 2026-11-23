from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, EmailStr

class FieldSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    label: str = Field(..., min_length=1, max_length=100)
    type: str = Field(default="text", pattern="^(text|email|tel|number|textarea|select)$")
    required: bool = True
    options: Optional[List[str]] = None

class DisplayOptions(BaseModel):
    position: str = "bottom-right"
    theme_color: str = "#2563eb"
    headline_color: str = "#1f2937"
    trigger: str = "immediate"
    delay_seconds: int = 0

class WidgetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(default="signup_form", pattern="^(signup_form|cta|popover|contact_form)$")
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default="", max_length=500)
    fields: List[FieldSchema] = Field(default_factory=list)
    button_text: str = Field(default="Submit", max_length=50)
    display_options: DisplayOptions = Field(default_factory=DisplayOptions)

class WidgetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    type: Optional[str] = Field(None, pattern="^(signup_form|cta|popover|contact_form)$")
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    fields: Optional[List[FieldSchema]] = None
    button_text: Optional[str] = Field(None, max_length=50)
    display_options: Optional[DisplayOptions] = None
    is_active: Optional[bool] = None

class WidgetResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    type: str
    title: str
    description: str
    fields: List[Dict[str, Any]]
    button_text: str
    display_options: Dict[str, Any]
    is_active: bool
    embed_snippet: str
    created_at: str
    updated_at: str

class PublicWidgetConfig(BaseModel):
    id: str
    type: str
    title: str
    description: str
    fields: List[Dict[str, Any]]
    button_text: str
    display_options: Dict[str, Any]
    submission_url: str

class PublicSubmissionPayload(BaseModel):
    widget_id: str = Field(..., min_length=1)
    data: Dict[str, Any] = Field(...)
    _hp_trap: Optional[str] = None
    _hp_website: Optional[str] = None

class SubmissionResult(BaseModel):
    status: str
    submission_id: str
    message: str
    enriched: bool
    geo: Optional[Dict[str, Optional[str]]] = None

class DashboardStats(BaseModel):
    total_widgets: int
    total_submissions: int
    submissions_24h: int
    submissions_7d: int
    by_widget: List[Dict[str, Any]]
    geo_distribution: List[Dict[str, Any]]
