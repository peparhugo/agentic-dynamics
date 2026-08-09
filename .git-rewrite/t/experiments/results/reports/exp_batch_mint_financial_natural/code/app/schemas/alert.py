from pydantic import BaseModel
from datetime import datetime


class AlertResponse(BaseModel):
    id: str
    user_id: str
    alert_type: str
    title: str
    message: str
    severity: str
    is_read: bool
    is_dismissed: bool
    metadata_json: str | None
    created_at: datetime

    class Config:
        from_attributes = True
