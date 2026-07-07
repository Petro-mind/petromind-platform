# PetroMind Tool System — Analysis & Recommendations

Based on a thorough review of the **System Analysis document**, the **Agent package** (`state.py`, `tools.py`, `planner.py`, `executor.py`, `orchestrator.py`), the **entry point** (`app.py`), the **monitor** (`asset_monitor.py`), and the **prediction service**, this document identifies gaps between the planned architecture and the current implementation, and provides actionable recommendations.

---

## 1. Tool Coverage: Planned vs. Actual

| # | FR-AG4 Planned Tools (System Analysis §17) | Implemented in `tools.py` | Status |
|---|---|---|---|
| 1 | `validate_sensor_file_tool` | ✅ Yes | Implemented |
| 2 | `predict_rul_tool` | ✅ Yes | Implemented |
| 3 | `classify_failure_risk_tool` | ✅ Yes | Implemented |
| 4 | `retrieve_work_orders_tool` | ✅ Yes | Implemented |
| 5 | `retrieve_manual_sections_tool` | ✅ Yes | Implemented |
| 6 | `summarize_sources_tool` | ✅ Yes | Implemented |
| 7 | `generate_recommendation_tool` | ✅ Yes | Stub — always returns `"Recommendation generated."` (line 321) |
| 8 | `list_system_status_tool` | ✅ Yes | Implemented |
| 9 | `save_feedback_tool` | ✅ Yes | Implemented |

**Extra tools** (not in FR-AG4 but implemented):

| # | Tool | Purpose |
|---|---|---|
| 10 | `register_asset_tool` | Register new machines for monitoring |
| 11 | `get_latest_prediction_tool` | Query DB for latest prediction (per asset or fleet) |
| 12 | `get_alert_history_tool` | Retrieve recent alerts from DB |
| 13 | `list_assets_tool` | List all registered assets |
| 14 | `get_prediction_history_tool` | Show RUL trend over time |
| 15 | `compare_assets_tool` | Side-by-side RUL/risk comparison |
| 16 | `get_monitor_status_tool` | Show real-time monitor buffer status |
| 17 | `deactivate_asset_tool` | Soft-delete asset from monitoring |
| 18 | `clear_conversation_tool` | Reset conversation context |
| 19 | `get_sensor_info_tool` | Show required sensor columns |

**Observation:** The 10 extra tools significantly extend the agent's capabilities, particularly around **database queries** and **asset management**. This is positive, but they were added organically without updating the planner's rule-based logic to trigger all of them.

---

## 2. Critical Issue: Fragile Monitor Access

### Problem

In `tools.py` line 676–681, `_run_get_monitor_status` tries to access the monitor:

```python
monitor = services.get("monitor")
if monitor is None:
    try:
        from app import monitor as app_monitor  # ← circular import risk
        monitor = app_monitor
    except (ImportError, AttributeError):
        return "Real-time monitor is not available."
```

This is **fragile** because:

- It creates a circular dependency (`tools.py` ← imports → `app.py` ← imports → `tools.py`)
- The `services` dict in `app.py` doesn't include `"monitor"` as a key
- If the module-level import order changes, this breaks silently

### Recommendation

Pass `monitor` through the `services` dict properly in `app.py`:

```python
# In app.py, after creating the monitor:
services["monitor"] = monitor
```

And simplify `_run_get_monitor_status` to just `services.get("monitor")` without the fallback import.

---

## 3. Rule-Based Planner Gaps

The `_rule_create_plan` method in `planner.py` (line 123–205) handles:

1. ✅ Uploaded file → validate → RUL → classify
2. ✅ Asset status keywords → `get_latest_prediction_tool`
3. ✅ Manual/procedure keywords → `retrieve_manual_sections_tool`
4. ✅ Historical/work order keywords → `retrieve_work_orders_tool`
5. ✅ System diagnostics → `list_system_status_tool`
6. ✅ Feedback → `save_feedback_tool`
7. ✅ Catch-all questions → RAG

**Missing triggers for extra tools:**

| Tool | Not triggered by rule-based planner |
|---|---|
| `get_alert_history_tool` | ❌ |
| `list_assets_tool` | ❌ |
| `get_prediction_history_tool` | ❌ |
| `compare_assets_tool` | ❌ |
| `get_monitor_status_tool` | ❌ |
| `get_sensor_info_tool` | ❌ |
| `register_asset_tool` | ❌ |
| `deactivate_asset_tool` | ❌ |
| `clear_conversation_tool` | ❌ |

**Impact:** When the LLM is offline (i.e., `use_llm=False`), the agent can only trigger **6 of 19 tools**. Users asking "list my assets" or "show me recent alerts" will get a response that doesn't use the correct tool.

### Recommendation

Add keyword patterns for each missing tool, e.g.:

- `"alert"`, `"triggered"`, `"recent notification"` → `get_alert_history_tool`
- `"list assets"`, `"what machines"`, `"show equipment"` → `list_assets_tool`
- `"trend"`, `"history of"`, `"degradation"` → `get_prediction_history_tool`
- `"compare"`, `"vs"`, `"versus"` → `compare_assets_tool`
- `"monitor status"`, `"buffer"`, `"streaming"` → `get_monitor_status_tool`
- `"what sensors"`, `"required columns"`, `"sensor info"` → `get_sensor_info_tool`
- `"register"`, `"add machine"`, `"new asset"` → `register_asset_tool`
- `"deactivate"`, `"remove"`, `"decommission"` → `deactivate_asset_tool`
- `"clear"`, `"reset", "start over"`, `"new conversation"` → `clear_conversation_tool`

---

## 4. Tool Input Parameter Inconsistency

### Current State

Tools access their parameters in different ways:

| Pattern | Example Tools | Issue |
|---|---|---|
| `inputs.get("key")` | `predict_rul_tool`, `register_asset_tool` | ✅ Preferred |
| Falls back to `state.uploaded_files[0]` | `_run_predict_rul`, `_run_classify_risk`, `_run_validate_sensor_file` | ✅ Good fallback |
| Regex extracts from `state.user_message` | `_run_register_asset` | Fragile — depends on message format |
| Hardcoded inner function introspection | `_run_get_sensor_info` line 790 | **❌ Fragile** — uses `__code__.co_varnames[1]` |

### Recommendation

1. Standardize: **always prefer `inputs.get()` first, then fall back to `state.*`**.
2. Fix `_run_get_sensor_info` hardcoded reference at line 790:

   ```python
   # Current (fragile):
   f"Minimum {prediction_service.rul_service.predict.__code__.co_varnames[1]} time steps..."
   # Should be:
   f"Minimum 30 time steps per window..."
   ```

---

## 5. `generate_recommendation_tool` is a No-Op

### Problem

Line 320–321:

```python
def _run_generate_recommendation(self, inputs, state, services):
    return "Recommendation generated."
```

This always returns a static string and doesn't actually call the LLM or generate anything.

### Recommendation

This tool should either:

- **Option A:** Be removed from the registry if the orchestrator's `_generate_response` method handles recommendations (which it does — line 216–257 of `orchestrator.py`).
- **Option B:** Be properly implemented to call the LLM with the retrieved context and model outputs, similar to what `_generate_response` already does.

**Recommendation:** Remove this tool from the registry (keep in code but unregister it), since `orchestrator._generate_response()` already handles final answer generation using the RAG template.

---

## 6. `services` Dict Lacks Monitor Reference

### Current State

In `app.py`:

```python
services = {
    "prediction_service": prediction_service,
    "rag_service": rag_service,
}
```

But many tools now need access to:

- Database (uses `SessionLocal()` directly — ✅ OK)
- Monitor status (imports from `app` — ❌ fragile)

### Recommendation

Expand `services` to include:

```python
services = {
    "prediction_service": prediction_service,
    "rag_service": rag_service,
    "monitor": None,  # Set after lazy init
    "settings": settings,
}
```

Then update `_run_get_monitor_status` to only use `services.get("monitor")` without the `from app import monitor` fallback.

---

## 7. Tool File Size: Consider Splitting

`tools.py` is currently **803 lines** with 19 tools. This is manageable but will grow.

### Recommendation

Consider splitting into separate modules:

```
petromind/agent/tools/
    __init__.py          # Re-exports Tool, ToolRegistry
    base.py              # Tool dataclass, ToolRegistry class
    prediction.py        # predict_rul, classify_failure_risk, validate_sensor_file
    database.py          # get_latest_prediction, get_alert_history, list_assets, compare_assets, get_prediction_history
    rag.py               # retrieve_work_orders, retrieve_manual_sections, summarize_sources
    asset_management.py  # register_asset, deactivate_asset
    system.py            # list_system_status, get_monitor_status, get_sensor_info, clear_conversation
    feedback.py          # save_feedback, generate_recommendation
```

**Priority:** Low — good for maintainability but not urgent.

---

## 8. Mode Selection (Already Implemented)

The `--mode {full,chat,realtime}` argument is now properly implemented in `app.py` using `argparse` instead of the broken `sys.argv` approach. This aligns with the system analysis document's description of:

- **Full mode**: Gradio UI + Real-Time Monitor (the default system behavior)
- **Chat mode**: Engineer interacts with the knowledge assistant without monitoring
- **Realtime mode**: Headless monitoring for automated alerting

This is complete and working.

---

## 9. Summary of Priority Recommendations

| Priority | Category | Action |
|---|---|---|
| **HIGH** | Monitor Access | Pass `monitor` through `services` dict in `app.py` instead of fragile `from app import monitor` |
| **HIGH** | Planner | Add missing 9 tool triggers to `_rule_create_plan()` so they work when LLM is offline |
| **MEDIUM** | Stub Tool | Fix or remove `generate_recommendation_tool` (currently a no-op) |
| **MEDIUM** | Code Quality | Fix fragile `__code__.co_varnames[1]` in `_run_get_sensor_info` |
| **LOW** | Maintainability | Optionally split `tools.py` into submodules |
| **LOW** | Consistency | Standardize input parameter extraction pattern across all tools |
| **LOW** | Documentation | Add docstrings to all `_run_*` methods explaining expected inputs |
