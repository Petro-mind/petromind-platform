"""Gradio User Interface for PetroMind AI Agent with Real-Time Monitoring."""

import os
import sys
import uuid
import threading
import logging
import argparse
import time
import gradio as gr
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from petromind.config.settings import settings
from petromind.config.logging import setup_logging
from petromind.llm import get_llm_client
from petromind.inference.rul_service import RULService
from petromind.inference.classifier_service import ClassifierService
from petromind.inference.prediction_service import PredictionService
from petromind.rag.retrieval import RAGService
from petromind.agent.tools import ToolRegistry
from petromind.agent.planner import Planner
from petromind.agent.memory import MemoryManager
from petromind.agent.executor import Executor
from petromind.agent.reflection import ReflectionEngine
from petromind.agent.guardrails import GuardrailEngine
from petromind.agent.orchestrator import AgentOrchestrator
from petromind.db.repositories import init_db
from petromind.monitoring.asset_monitor import AssetMonitor

logger = logging.getLogger("petromind.app")

# ==========================================
# 1. System Initialization
# ==========================================

setup_logging()

# --- Database ---
try:
    init_db()
    logger.info("Database initialized successfully.")
except Exception as e:
    logger.warning("Database initialization failed (non-fatal): %s", e)

# --- LLM Client ---
llm_client = get_llm_client(settings)
use_llm = llm_client is not None

# --- ML Services ---
rul_service = RULService(model_path=settings.rul_checkpoint_abs)
classifier_service = ClassifierService(model_path=settings.classifier_checkpoint_abs)
prediction_service = PredictionService(
    rul_service=rul_service,
    classifier_service=classifier_service
)
rag_service = RAGService(db_instance=None)

services = {
    "prediction_service": prediction_service,
    "rag_service": rag_service,
}

# --- Agent Components ---
tool_registry = ToolRegistry(services)
planner = Planner(llm_client=llm_client, use_llm=use_llm)
memory_manager = MemoryManager()
executor = Executor(tool_registry, services)
reflection_engine = ReflectionEngine(llm_client=llm_client, use_llm=use_llm)
guardrail_engine = GuardrailEngine()

orchestrator = AgentOrchestrator(
    planner=planner,
    memory_manager=memory_manager,
    tool_registry=tool_registry,
    executor=executor,
    reflection_engine=reflection_engine,
    guardrail_engine=guardrail_engine,
    llm_client=llm_client
)

# --- Real-Time Asset Monitor (lazy init — started in main block) ---
monitor = None


# ==========================================
# 2. Gradio Interface Logic
# ==========================================

def get_or_create_session_id(state_session):
    """Return the session ID from Gradio state, or create a new one."""
    if state_session is None:
        state_session = str(uuid.uuid4())
    return state_session


def process_interaction(user_message, history, file_obj, session_id):
    """Handles the user input and returns chat history + agent trace + updated session."""
    if not user_message and file_obj is None:
        return history, "Please enter a message or upload a file.", None, session_id

    uploaded_files = []
    if file_obj is not None:
        file_path = getattr(file_obj, 'name', str(file_obj))
        uploaded_files.append(file_path)

    # Ensure we have a valid session ID
    session_id = get_or_create_session_id(session_id)

    # Run the orchestrator
    state = orchestrator.run(user_message or "", uploaded_files, session_id)
    
    # Format the chat history
    history = history or []
    display_msg = user_message or "[File uploaded]"
    history.append({"role": "user", "content": display_msg})
    history.append({"role": "assistant", "content": state.final_answer})
    
    # Format the Agent Trace
    trace_log = f"━━━ Agent Trace ━━━\n"
    trace_log += f"Session: {session_id[:8]}...\n"
    trace_log += f"Trace ID: {state.trace_id[:8]}...\n"
    trace_log += f"Intent: {state.intent}\n"
    trace_log += f"Plan: {state.plan}\n"
    trace_log += f"Status: {state.lifecycle_status}\n\n"
    
    trace_log += "── Tools Executed ──\n"
    if not state.tool_calls:
        trace_log += "  (none)\n"
    for record in state.tool_calls:
        status_icon = "✓" if record.status == "completed" else "✗"
        trace_log += f"  [{status_icon}] {record.tool_name} ({record.latency_ms:.1f}ms)\n"
        trace_log += f"      → {record.output_summary}\n"
        if record.error:
            trace_log += f"      ⚠ Error: {record.error}\n"
        
    trace_log += f"\n── Model Outputs ──\n"
    trace_log += f"  RUL: {state.model_outputs.predicted_rul}\n"
    trace_log += f"  Risk: {state.model_outputs.risk_label} ({state.model_outputs.risk_probability})\n"
    
    if state.retrieved_sources:
        trace_log += f"\n── Retrieved Sources ({len(state.retrieved_sources)}) ──\n"
        for src in state.retrieved_sources:
            trace_log += f"  [{src.source_id}] {src.title} (score: {src.score})\n"

    if state.errors:
        trace_log += f"\n── Errors ──\n"
        for err in state.errors:
            trace_log += f"  ⚠ {err}\n"
    
    if state.intermediate_notes:
        trace_log += f"\n── Notes ──\n"
        for note in state.intermediate_notes:
            trace_log += f"  • {note}\n"
    
    return history, trace_log, None, session_id


def get_monitor_status():
    """Return the latest monitor data as formatted strings for the dashboard."""
    if monitor is None:
        return "Monitor not running.", "Monitor not started."
    
    predictions = monitor.latest_predictions
    alerts = monitor.latest_alerts[-5:]  # last 5 alerts
    
    # Build asset cards
    cards = ""
    for uid in monitor.unit_ids:
        asset_id = f"ENG-{uid:03d}"
        pred = predictions.get(asset_id)
        if pred:
            rul = pred.predicted_rul
            risk = pred.risk_label
            prob = pred.risk_probability
            color = {"healthy": "green", "at_risk": "orange", "critical": "red", "unknown": "gray"}.get(risk, "gray")
            cards += (
                f"**{asset_id}** (Engine {uid})\n"
                f"  - RUL: `{rul:.1f}` cycles\n"
                f"  - Risk: `{risk}` (prob: `{prob:.2f}`)  \n"
                f"  - Status: <span style='color:{color}'>{'●' if risk in ('at_risk','critical') else '○'}</span>\n\n"
            )
        else:
            cards += f"**{asset_id}** (Engine {uid})\n  - Awaiting initial prediction (buffer filling...)\n\n"
    
    if not cards:
        cards = "No assets configured."
    
    # Build alert log
    alert_log = ""
    if alerts:
        for a in reversed(alerts[-5:]):
            alert_log += (
                f"[{a['risk_label'].upper()}] {a['asset_id']} — "
                f"RUL={a['predicted_rul']:.0f} risk={a['risk_probability']:.2f}\n"
            )
    else:
        alert_log = "No alerts triggered yet."
    
    return cards, alert_log


def refresh_dashboard():
    """Called periodically by Gradio to update the dashboard."""
    cards, alerts = get_monitor_status()
    return cards, alerts


# ==========================================
# 3. Gradio Layout
# ==========================================

def build_gradio_app(include_monitoring_tab=True):
    """Build and return the Gradio Blocks app.
    
    Args:
        include_monitoring_tab: If True, include the Live Monitoring tab.
    """
    with gr.Blocks(title="PetroMind AI") as demo:
        session_state = gr.State(None)
        gr.Markdown("# 🛠️ PetroMind — Predictive Maintenance Agent")
        gr.Markdown(
            "Ask questions about equipment maintenance, upload sensor data for RUL prediction "
            "and risk classification, or retrieve historical work orders and manual sections."
        )
        
        with gr.Tabs():
            with gr.TabItem("💬 Chat Interface"):
                with gr.Row():
                    with gr.Column(scale=2):
                        chatbot = gr.Chatbot(height=500, label="Agent Interaction")
                        
                        with gr.Row():
                            msg = gr.Textbox(
                                show_label=False, 
                                placeholder="Enter your question or maintenance request...", 
                                scale=4
                            )
                            submit_btn = gr.Button("Send", variant="primary", scale=1)
                            
                    with gr.Column(scale=1):
                        gr.Markdown("### 📂 Upload Sensor Data")
                        file_input = gr.File(label="CSV or Excel", file_types=[".csv", ".xlsx"])
                        gr.Markdown(
                            "*Upload a file to automatically trigger RUL prediction "
                            "and Risk Classification.*"
                        )
                        
                        gr.Markdown("---")
                        gr.Markdown("### ℹ️ Quick Actions")
                        gr.Markdown(
                            "Try asking:\n"
                            "- *What maintenance procedure should I follow for high vibration?*\n"
                            "- *Show me similar past work orders for bearing failure*\n"
                            "- *How to inspect a generator cooling system?*"
                        )
                        
            with gr.TabItem("🔍 Agent Trace (Debug)"):
                gr.Markdown("### Internal Agent Thoughts & Actions")
                trace_output = gr.Textbox(
                    lines=30, 
                    label="Execution Trace",
                    interactive=False
                )
            
            if include_monitoring_tab:
                with gr.TabItem("📊 Live Monitoring"):
                    gr.Markdown("## Real-Time Asset Health")
                    gr.Markdown(
                        "Continuously monitoring N-CMAPSS engines. "
                        "Predictions run every time a new 30-cycle window is available."
                    )
                    
                    with gr.Row():
                        with gr.Column(scale=1):
                            gr.Markdown("### 🏭 Asset Status")
                            asset_cards = gr.Markdown("Initializing...")
                            
                        with gr.Column(scale=1):
                            gr.Markdown("### 🚨 Recent Alerts")
                            alert_log = gr.Textbox(
                                lines=10,
                                label="Alert History",
                                value="No alerts yet."
                            )
                    
                    refresh_btn = gr.Button("🔄 Refresh Dashboard")
                    refresh_btn.click(
                        fn=refresh_dashboard,
                        inputs=[],
                        outputs=[asset_cards, alert_log]
                    )
                    
                    # Load initial dashboard state on page load
                    demo.load(
                        fn=refresh_dashboard,
                        inputs=[],
                        outputs=[asset_cards, alert_log]
                    )
                    
                    # Auto-refresh every 5 seconds using Gradio Timer (Gradio 6 compatible)
                    timer = gr.Timer(value=5)
                    timer.tick(
                        fn=refresh_dashboard,
                        inputs=[],
                        outputs=[asset_cards, alert_log]
                    )

        # Wire up the events (include session_state so each conversation gets its own ID)
        submit_btn.click(
            process_interaction, 
            inputs=[msg, chatbot, file_input, session_state], 
            outputs=[chatbot, trace_output, file_input, session_state]
        )
        
        msg.submit(
            process_interaction, 
            inputs=[msg, chatbot, file_input, session_state], 
            outputs=[chatbot, trace_output, file_input, session_state]
        )
    
    return demo


def start_monitor():
    """Create and start the real-time asset monitor."""
    global monitor
    monitor = AssetMonitor(
        prediction_service=prediction_service,
        orchestrator=orchestrator,
        h5_path="data/N-CMAPSS_DS02-006.h5",
        unit_ids=[1, 2, 3],
        window_size=30,
        cycles_per_second=1.0,  # 1 cycle/second = real-time
    )
    monitor.start()
    print(f"[✓] Real-Time Monitor: {len(monitor.unit_ids)} engines at {monitor.cycles_per_second} cyc/s")
    return monitor


# ==========================================
# 4. Entry Point with Mode Selection
# ==========================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="PetroMind AI — Predictive Maintenance Agent"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["full", "chat", "realtime"],
        default="full",
        help=(
            "Select application mode:\n"
            "  full     - Gradio UI + Real-Time Monitor (default)\n"
            "  chat     - Gradio UI only, no real-time monitoring\n"
            "  realtime - Real-Time Monitor only, no Gradio UI"
        ),
    )
    args = parser.parse_args()

    if args.mode == "realtime":
        # ── Real-Time Monitor Only ──
        print("[Mode] Real-Time Only — starting monitor without Gradio UI...")
        start_monitor()
        print("Monitor running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping monitor...")
            monitor.stop()
            sys.exit(0)

    elif args.mode == "chat":
        # ── Chat Only (no real-time monitor) ──
        print("[Mode] Chat Only — starting Gradio without real-time monitor...")
        demo = build_gradio_app(include_monitoring_tab=False)
        demo.launch(server_name="127.0.0.1", server_port=7860, share=False)

    else:
        # ── Full Mode (default): Gradio + Real-Time Monitor ──
        print("[Mode] Full App — Gradio + Real-Time Monitor")
        start_monitor()
        print("[✓] PetroMind Agent initialized and ready.")
        demo = build_gradio_app(include_monitoring_tab=True)
        demo.launch(server_name="127.0.0.1", server_port=7860, share=False)