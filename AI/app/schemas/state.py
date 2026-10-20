from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class AgentSessionState(BaseModel):
    session_id: str
    current_cash: float = 120000.0
    upcoming_debt: float = 70000.0
    daily_burn_rate: float = 3000.0
    active_intent: Optional[str] = None
    context_history: List[Dict[str, Any]] = Field(default_factory=list)
    pending_receipt: Optional[Dict[str, Any]] = None
    retry_count: int = 0
