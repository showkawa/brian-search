## Cassiel Agent — Learnings

### Session: 2026-04-29
- User is HR Leader in pipeline robotics industry, targeting HRD promotion
- Core use case: BOSS Zhipin recruitment automation (NOT general chat agent)
- UI framework changed from PySide6+Fluent to NiceGUI (richer chat components)
- MS-Agent chosen for native GLM+Qwen+DeepSeek support
- Playwright for browser automation (headful mode for safety)
- Cookie-based login (no password storage)
- Operation intervals: search ≥5s, pagination ≥3s, send ≥10s

### Session: 2026-05-02 — Phase 2 UI Integration

**Patterns discovered:**
- NiceGUI stepper requires .next() / .previous() for navigation — no declarative routing
- aggrid owClicked event passes e.args["data"] with the row dict; use _candidate_index to map back to Candidate objects
- Sync Playwright (BossCollector) must run in loop.run_in_executor() inside NiceGUI async context
- Walrus operator := cannot assign to self.attr — must split into separate assignment + usage

**Architecture decisions:**
- UI directly calls backend components (BossCollector, CandidateFilter, InvitationWriter) rather than going through Orchestrator — gives finer control over step transitions
- Model selection uses "provider:model" combined key with display labels; parsed at call time
- InvitationPreviewComponent uses callback pattern (on_regenerate, on_send, on_skip) for loose coupling with main.py
- SearchConfig().CITY_CODES works for getting city list (dataclass default_factory resolves on instance)

**Gotchas:**
- Chinese curly quotes (""'' ) conflict with Python string delimiters — use guillemets (《》) or corner brackets (「」) instead
- basedpyright LSP not installed on this machine; used python -m py_compile for syntax verification
