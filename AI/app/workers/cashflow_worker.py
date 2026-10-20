from typing import Dict, Any, Optional
from app.db.mongo import db_manager

class CashflowSimulationWorker:
    """100% Deterministic Cashflow Forecaster & Simulation Worker with Zero-Division Guard."""

    def simulate_cashflow(
        self,
        current_cash: float,
        new_expense: float = 0.0,
        upcoming_debt: float = 0.0,
        daily_burn_rate: float = 3000.0,
        new_income: float = 0.0
    ) -> Dict[str, Any]:
        """Calculates projected cash reserve, burn rate, remaining runway days, and risk flags."""
        projected_cash = round(current_cash + new_income - new_expense, 2)

        # 1. Zero Division & Edge Case Guard
        if daily_burn_rate <= 0:
            runway_days = 9999.0
            runway_status = "CASH_POSITIVE_OR_ZERO_BURN"
        else:
            if projected_cash <= 0:
                runway_days = 0.0
                runway_status = "CRITICAL_DEFICIT"
            else:
                runway_days = round(projected_cash / daily_burn_rate, 1)
                runway_status = "NORMAL"

        # 2. Risk Indicators
        is_liquidity_risk = runway_days < 15.0
        is_debt_default_risk = projected_cash < upcoming_debt
        deficit = max(0.0, round(upcoming_debt - projected_cash, 2))

        # 3. Overall Risk Level
        if is_debt_default_risk:
            risk_level = "CRITICAL_DEBT_DEFAULT_RISK"
        elif is_liquidity_risk:
            risk_level = "WARNING_LIQUIDITY_RISK"
        else:
            risk_level = "HEALTHY"

        return {
            "current_cash": current_cash,
            "new_expense": new_expense,
            "new_income": new_income,
            "net_flow": round(new_income - new_expense, 2),
            "projected_cash": projected_cash,
            "upcoming_debt": upcoming_debt,
            "daily_burn_rate": daily_burn_rate,
            "runway_days": runway_days,
            "runway_status": runway_status,
            "is_liquidity_risk": is_liquidity_risk,
            "is_debt_default_risk": is_debt_default_risk,
            "deficit": deficit,
            "risk_level": risk_level
        }

    async def simulate_for_business(self, business_id: str, new_expense: float) -> Dict[str, Any]:
        """Loads business statement profile from MongoDB and executes simulation."""
        stmt = await db_manager.statements.find_one({"business_id": business_id})
        if not stmt:
            # Default fallback profile if not found
            current_cash = 120000.0
            upcoming_debt = 70000.0
            burn_rate = 3000.0
            biz_name = "SME Business"
        else:
            current_cash = stmt.get("current_cash_reserve", 120000.0)
            upcoming_debt = stmt.get("upcoming_debt_service", 70000.0)
            burn_rate = stmt.get("daily_burn_rate", 3000.0)
            biz_name = stmt.get("business_name", "SME Business")

        result = self.simulate_cashflow(
            current_cash=current_cash,
            new_expense=new_expense,
            upcoming_debt=upcoming_debt,
            daily_burn_rate=burn_rate
        )
        result["business_id"] = business_id
        result["business_name"] = biz_name
        return result
