from pydantic import BaseModel, ConfigDict, Field


class AssistantProfileContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_name: str = Field(min_length=1, max_length=120)
    # None means the backend has no verified opening/current cash balance.
    current_cash: float | None = Field(default=None, ge=0, le=1_000_000_000_000)
    upcoming_debt: float = Field(ge=0)
    daily_burn_rate: float = Field(ge=0)
    monthly_revenue: float = Field(ge=0)
    net_income: float
    business_age_years: float = Field(ge=0, le=100)
    has_collateral: bool


class AssistantChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    content: str = Field(min_length=1, max_length=4000)
    profile_context: AssistantProfileContext | None = None
