import streamlit as st
import requests
import time

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Guardian — Trade Surveillance",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* ── Global ── */
[data-testid="stAppViewContainer"] { background: #0a0e1a; }
[data-testid="stSidebar"] { background: #0d1220; border-right: 1px solid #1e2d45; }
h1, h2, h3, h4, label, p, span, div { color: #e0e6f0 !important; }

/* ── Cards ── */
.card {
    background: #111827;
    border: 1px solid #1e2d45;
    border-radius: 10px;
    padding: 20px 24px;
    margin-bottom: 16px;
}
.card-red   { border-left: 4px solid #ef4444; }
.card-amber { border-left: 4px solid #f59e0b; }
.card-blue  { border-left: 4px solid #3b82f6; }
.card-green { border-left: 4px solid #22c55e; }

/* ── Status badge ── */
.badge {
    display: inline-block;
    padding: 6px 20px;
    border-radius: 999px;
    font-weight: 700;
    font-size: 14px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}
.badge-escalate { background: #7f1d1d; color: #fca5a5 !important; border: 1px solid #ef4444; }
.badge-review   { background: #78350f; color: #fde68a !important; border: 1px solid #f59e0b; }
.badge-clear    { background: #14532d; color: #86efac !important; border: 1px solid #22c55e; }

/* ── Severity chip ── */
.chip {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    margin-right: 6px;
}
.chip-CRITICAL { background: #450a0a; color: #fca5a5 !important; border: 1px solid #ef4444; }
.chip-HIGH     { background: #431407; color: #fdba74 !important; border: 1px solid #f97316; }
.chip-MEDIUM   { background: #422006; color: #fde68a !important; border: 1px solid #f59e0b; }
.chip-LOW      { background: #1e3a5f; color: #93c5fd !important; border: 1px solid #3b82f6; }

/* ── Entity tag ── */
.tag {
    display: inline-block;
    background: #1e2d45;
    color: #93c5fd !important;
    border: 1px solid #2d4a7a;
    border-radius: 6px;
    padding: 2px 10px;
    font-size: 12px;
    margin: 3px 3px 3px 0;
    font-family: monospace;
}

/* ── Metric box ── */
.metric-box {
    background: #111827;
    border: 1px solid #1e2d45;
    border-radius: 10px;
    padding: 16px 20px;
    text-align: center;
}
.metric-value { font-size: 32px; font-weight: 800; color: #60a5fa !important; }
.metric-label { font-size: 12px; color: #6b7fa3 !important; text-transform: uppercase; letter-spacing: 1px; }

/* ── Inputs ── */
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea {
    background: #111827 !important;
    border: 1px solid #1e2d45 !important;
    color: #e0e6f0 !important;
    border-radius: 8px !important;
}
[data-testid="stButton"] button {
    background: linear-gradient(135deg, #1d4ed8, #2563eb) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 10px 28px !important;
    font-weight: 700 !important;
    letter-spacing: 0.5px !important;
    width: 100%;
}
[data-testid="stButton"] button:hover {
    background: linear-gradient(135deg, #1e40af, #1d4ed8) !important;
}

/* ── Divider ── */
hr { border-color: #1e2d45 !important; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🛡️ Guardian")
    st.markdown("**Dodd-Frank Communications Surveillance**")
    st.markdown("---")

    st.markdown("**Regulatory Coverage**")
    regs = [
        ("📋", "Dodd-Frank Act"),
        ("⚖️", "SEC Rule 10b-5"),
        ("📁", "SEC Rule 17a-4"),
        ("🏛️", "FINRA Rule 2010"),
        ("🚫", "FINRA Rule 2020"),
        ("📂", "FINRA Rule 4511"),
    ]
    for icon, reg in regs:
        st.markdown(f"{icon} {reg}")

    st.markdown("---")
    st.markdown("**Detection Categories**")
    cats = ["MNPI Disclosure", "Unauthorized Advice", "Market Manipulation",
            "Front-Running", "Restricted Securities", "Recordkeeping Violation"]
    for c in cats:
        st.markdown(f"• {c}")

    st.markdown("---")

    # API health check
    try:
        r = requests.get(f"{API_BASE}/health", timeout=2)
        if r.status_code == 200:
            st.success("API Online")
        else:
            st.error("API Error")
    except Exception:
        st.error("API Offline")


# ── Header ──────────────────────────────────────────────────────────────────

col_logo, col_title = st.columns([1, 8])
with col_logo:
    st.markdown("<div style='font-size:48px;margin-top:8px'>🛡️</div>", unsafe_allow_html=True)
with col_title:
    st.markdown("# Guardian — Trade Surveillance Platform")
    st.markdown("<span style='color:#6b7fa3;font-size:14px'>AI-powered Dodd-Frank & SEC/FINRA compliance monitoring for trader and RM communications</span>", unsafe_allow_html=True)

st.markdown("---")


# ── Input panel ─────────────────────────────────────────────────────────────

st.markdown("### Submit Call Recording for Surveillance")

col_url, col_id = st.columns([3, 1])
with col_url:
    video_url = st.text_input(
        "Recording URL",
        placeholder="YouTube URL (demo) or Azure Blob Storage SAS URL (production)",
        label_visibility="collapsed",
    )
with col_id:
    call_id = st.text_input(
        "Call ID (optional)",
        placeholder="e.g. trader-desk-3",
        label_visibility="collapsed",
    )

run_col, _ = st.columns([1, 3])
with run_col:
    submitted = st.button("▶  Run Surveillance Analysis")

st.markdown("---")


# ── Results ─────────────────────────────────────────────────────────────────

if submitted:
    if not video_url.strip():
        st.warning("Please enter a recording URL.")
        st.stop()

    with st.spinner("Ingesting recording · extracting transcript · running compliance analysis…"):
        try:
            payload = {"video_url": video_url}
            if call_id.strip():
                payload["call_id"] = call_id.strip()

            resp = requests.post(f"{API_BASE}/surveillance", json=payload, timeout=600)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.ConnectionError:
            st.error("Cannot reach the API at http://127.0.0.1:8000 — make sure the server is running.")
            st.stop()
        except requests.exceptions.HTTPError as e:
            st.error(f"API error {resp.status_code}: {resp.text}")
            st.stop()
        except Exception as e:
            st.error(f"Unexpected error: {e}")
            st.stop()

    status = data.get("final_status", "REVIEW")
    violations = data.get("compliance_violations", [])
    entities = data.get("flagged_entities", [])
    report = data.get("final_report", "")
    metadata = data.get("call_metadata") or {}
    errors = data.get("errors", [])

    # Status + summary metrics
    badge_class = f"badge-{status.lower()}"
    badge_icon = {"ESCALATE": "🔴", "REVIEW": "🟡", "CLEAR": "🟢"}.get(status, "⚪")

    st.markdown(
        f"<div class='card'>"
        f"<div style='display:flex;align-items:center;gap:16px'>"
        f"<span class='badge {badge_class}'>{badge_icon} {status}</span>"
        f"<span style='color:#6b7fa3;font-size:13px'>Session: {data.get('session_id','—')} &nbsp;|&nbsp; Call ID: {data.get('call_id','—')}</span>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    m1, m2, m3, m4 = st.columns(4)
    sev_counts = {}
    for v in violations:
        sev_counts[v.get("severity", "LOW")] = sev_counts.get(v.get("severity", "LOW"), 0) + 1

    with m1:
        st.markdown(f"<div class='metric-box'><div class='metric-value'>{len(violations)}</div><div class='metric-label'>Total Violations</div></div>", unsafe_allow_html=True)
    with m2:
        st.markdown(f"<div class='metric-box'><div class='metric-value' style='color:#fca5a5!important'>{sev_counts.get('CRITICAL',0)}</div><div class='metric-label'>Critical</div></div>", unsafe_allow_html=True)
    with m3:
        st.markdown(f"<div class='metric-box'><div class='metric-value' style='color:#fde68a!important'>{len(entities)}</div><div class='metric-label'>Flagged Entities</div></div>", unsafe_allow_html=True)
    with m4:
        dur = metadata.get("duration_seconds")
        dur_str = f"{int(dur)//60}m {int(dur)%60}s" if dur else "—"
        st.markdown(f"<div class='metric-box'><div class='metric-value' style='color:#86efac!important'>{dur_str}</div><div class='metric-label'>Call Duration</div></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    left, right = st.columns([3, 2])

    # ── Violations list ──
    with left:
        st.markdown("#### Compliance Violations")
        if not violations:
            st.markdown("<div class='card card-green'><b>No violations detected.</b></div>", unsafe_allow_html=True)
        else:
            sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
            sorted_v = sorted(violations, key=lambda x: sev_order.get(x.get("severity","LOW"), 3))
            for v in sorted_v:
                sev = v.get("severity", "LOW")
                card_color = {"CRITICAL": "card-red", "HIGH": "card-red", "MEDIUM": "card-amber", "LOW": "card-blue"}.get(sev, "card-blue")
                ts = f"<span style='color:#6b7fa3;font-size:11px'>⏱ {v['timestamp']}</span>" if v.get("timestamp") else ""
                st.markdown(
                    f"<div class='card {card_color}'>"
                    f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>"
                    f"<b style='font-size:15px'>{v.get('category','Unknown')}</b>"
                    f"<span><span class='chip chip-{sev}'>{sev}</span>{ts}</span>"
                    f"</div>"
                    f"<div style='color:#9ca3af;font-size:12px;margin-bottom:6px'>{v.get('regulation','')}</div>"
                    f"<div style='font-size:13px;color:#d1d5db'>{v.get('description','')}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    # ── Entities + metadata + speakers ──
    with right:
        st.markdown("#### Flagged Entities")
        if entities:
            tags_html = "".join(f"<span class='tag'>{e}</span>" for e in entities)
            st.markdown(f"<div class='card'>{tags_html}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='card'>No entities flagged.</div>", unsafe_allow_html=True)

        if metadata:
            st.markdown("#### Call Metadata")
            speaker_map = metadata.get("speaker_map", {})
            speakers_html = "".join(
                f"<div style='font-size:13px;margin:4px 0'><span style='color:#6b7fa3'>Speaker {sid}:</span> {name}</div>"
                for sid, name in speaker_map.items()
            )
            named = metadata.get("named_entities_detected", [])
            named_html = "".join(f"<span class='tag'>{n}</span>" for n in named) if named else "<span style='color:#6b7fa3'>none</span>"
            st.markdown(
                f"<div class='card'>"
                f"<div style='margin-bottom:10px'><b>Speakers</b><br>{speakers_html or '<span style=color:#6b7fa3>—</span>'}</div>"
                f"<div><b>Named Entities (VI)</b><br>{named_html}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # ── Narrative report ──
    if report:
        st.markdown("#### Surveillance Report")
        st.markdown(
            f"<div class='card' style='font-size:14px;line-height:1.8;white-space:pre-wrap'>{report}</div>",
            unsafe_allow_html=True,
        )

    # ── Errors ──
    if errors:
        st.markdown("#### Pipeline Errors")
        for e in errors:
            st.markdown(f"<div class='card card-red' style='font-size:13px'>⚠️ {e}</div>", unsafe_allow_html=True)

else:
    # Landing state — explain the pipeline
    st.markdown("### How It Works")
    c1, c2, c3 = st.columns(3)
    steps = [
        ("1", "📥 Ingest", "Submit a Zoom, Bloomberg, or Teams recording URL. The pipeline downloads and uploads to Azure Video Indexer for speaker-attributed transcription and OCR extraction."),
        ("2", "🔍 Analyse", "The surveillance agent RAGs against the Dodd-Frank / SEC / FINRA knowledge base, then uses a structured LLM to detect violations across 6 regulatory categories."),
        ("3", "📊 Report", "Receive a structured compliance report with violation severity, flagged securities, applicable regulations, and a CLEAR / REVIEW / ESCALATE status for the compliance officer."),
    ]
    for col, (num, title, desc) in zip([c1, c2, c3], steps):
        with col:
            st.markdown(
                f"<div class='card'>"
                f"<div style='font-size:32px;margin-bottom:8px'>{title}</div>"
                f"<div style='font-size:13px;color:#9ca3af;line-height:1.7'>{desc}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
