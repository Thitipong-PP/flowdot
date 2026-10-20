import pytest
from app.workers.cashflow_worker import CashflowSimulationWorker

def test_zero_burn_rate_guard():
    worker = CashflowSimulationWorker()
    res = worker.simulate_cashflow(
        current_cash=100000.0,
        new_expense=10000.0,
        upcoming_debt=20000.0,
        daily_burn_rate=0.0
    )
    assert res["runway_days"] == 9999.0
    assert res["runway_status"] == "CASH_POSITIVE_OR_ZERO_BURN"
    assert res["projected_cash"] == 90000.0

def test_negative_burn_rate_guard():
    worker = CashflowSimulationWorker()
    res = worker.simulate_cashflow(
        current_cash=100000.0,
        new_expense=10000.0,
        upcoming_debt=20000.0,
        daily_burn_rate=-500.0  # Cash positive
    )
    assert res["runway_days"] == 9999.0
    assert res["runway_status"] == "CASH_POSITIVE_OR_ZERO_BURN"

def test_critical_deficit_spending():
    worker = CashflowSimulationWorker()
    # Expense exceeds cash
    res = worker.simulate_cashflow(
        current_cash=50000.0,
        new_expense=80000.0,
        upcoming_debt=10000.0,
        daily_burn_rate=2000.0
    )
    assert res["projected_cash"] == -30000.0
    assert res["runway_days"] == 0.0
    assert res["runway_status"] == "CRITICAL_DEFICIT"
    assert res["is_debt_default_risk"] is True
    assert res["deficit"] == 40000.0

def test_liquidity_risk_and_debt_risk():
    worker = CashflowSimulationWorker()
    # 120,000 cash - 95,000 = 25,000. Burn = 3,000 -> 8.3 days (< 15). Debt = 70,000 (> 25,000)
    res = worker.simulate_cashflow(
        current_cash=120000.0,
        new_expense=95000.0,
        upcoming_debt=70000.0,
        daily_burn_rate=3000.0
    )
    assert res["runway_days"] == 8.3
    assert res["is_liquidity_risk"] is True
    assert res["is_debt_default_risk"] is True
    assert res["deficit"] == 45000.0
    assert res["risk_level"] == "CRITICAL_DEBT_DEFAULT_RISK"
