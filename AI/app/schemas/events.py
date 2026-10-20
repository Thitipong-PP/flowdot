from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field

class ActiveNode(str, Enum):
    INGRESS = "INGRESS"
    ORCHESTRATOR = "ORCHESTRATOR"
    VISION_WORKER = "VISION_WORKER"
    CASHFLOW_WORKER = "CASHFLOW_WORKER"
    LOAN_WORKER = "LOAN_WORKER"
    SANITY_GUARD = "SANITY_GUARD"
    RESPONSE_COMPILER = "RESPONSE_COMPILER"

class NodeStatus(str, Enum):
    IDLE = "IDLE"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"

class LiveMetrics(BaseModel):
    latency_ms: float = 0.0
    current_cash: Optional[float] = None
    projected_cash: Optional[float] = None
    runway_days: Optional[float] = None
    risk_level: Optional[str] = None

class TelemetryEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:8]}")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    session_id: str
    event: str
    active_node: ActiveNode
    node_status: NodeStatus
    active_wire: Optional[str] = None
    thought_log: Optional[str] = None
    live_metrics: LiveMetrics = Field(default_factory=LiveMetrics)
    payload: Optional[Dict[str, Any]] = None
