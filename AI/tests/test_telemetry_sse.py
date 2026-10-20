import pytest
import asyncio
import json
from app.core.telemetry import TelemetryEmitter, telemetry_emitter
from app.schemas.events import TelemetryEvent, ActiveNode, NodeStatus, LiveMetrics

@pytest.mark.asyncio
async def test_telemetry_sse_subscription():
    emitter = TelemetryEmitter()
    queue = emitter.subscribe("user_99")
    
    evt = TelemetryEvent(
        event_id="evt_test_01",
        session_id="user_99",
        event="TOOL_COMPLETED",
        active_node=ActiveNode.VISION_WORKER,
        node_status=NodeStatus.SUCCESS,
        payload={"result": "ok"}
    )
    await emitter.emit(evt)
    
    received = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert received.event == "TOOL_COMPLETED"
    assert received.payload["result"] == "ok"
    assert received.active_node == ActiveNode.VISION_WORKER

@pytest.mark.asyncio
async def test_telemetry_multiple_subscribers_and_isolation():
    emitter = TelemetryEmitter()
    q_user1_a = emitter.subscribe("user_1")
    q_user1_b = emitter.subscribe("user_1")
    q_user2 = emitter.subscribe("user_2")

    evt1 = TelemetryEvent(
        session_id="user_1",
        event="THINKING",
        active_node=ActiveNode.ORCHESTRATOR,
        node_status=NodeStatus.PROCESSING,
        thought_log="Analyzing cashflow ledger"
    )
    await emitter.emit(evt1)

    # Both listeners of user_1 should receive evt1
    r_a = await asyncio.wait_for(q_user1_a.get(), timeout=1.0)
    r_b = await asyncio.wait_for(q_user1_b.get(), timeout=1.0)
    assert r_a.thought_log == "Analyzing cashflow ledger"
    assert r_b.thought_log == "Analyzing cashflow ledger"

    # user_2 should NOT have received evt1
    assert q_user2.empty()

@pytest.mark.asyncio
async def test_telemetry_unsubscribe():
    emitter = TelemetryEmitter()
    q = emitter.subscribe("user_x")
    emitter.unsubscribe("user_x", q)

    evt = TelemetryEvent(
        session_id="user_x",
        event="DONE",
        active_node=ActiveNode.RESPONSE_COMPILER,
        node_status=NodeStatus.SUCCESS
    )
    await emitter.emit(evt)
    assert q.empty()

@pytest.mark.asyncio
async def test_telemetry_sse_generator_formatting():
    emitter = TelemetryEmitter()
    
    async def push_event():
        await asyncio.sleep(0.05)
        evt = TelemetryEvent(
            session_id="user_stream",
            event="METRICS_UPDATED",
            active_node=ActiveNode.CASHFLOW_WORKER,
            node_status=NodeStatus.SUCCESS,
            live_metrics=LiveMetrics(latency_ms=12.5, current_cash=50000.0)
        )
        await emitter.emit(evt)

    asyncio.create_task(push_event())

    gen = emitter.subscribe_events("user_stream")
    init_chunk = await anext(gen)
    assert init_chunk.startswith(":")

    chunk = await anext(gen)
    assert chunk.startswith("data: ")
    assert chunk.endswith("\n\n")
    
    parsed = json.loads(chunk[6:].strip())
    assert parsed["event"] == "METRICS_UPDATED"
    assert parsed["live_metrics"]["latency_ms"] == 12.5
    assert parsed["live_metrics"]["current_cash"] == 50000.0
