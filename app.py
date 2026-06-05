import streamlit as st
import os
from supabase import create_client
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", 15))
os.environ["GROQ_API_KEY"] = GROQ_API_KEY

st.set_page_config(
    page_title="MediScan AI",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif !important;
    background: #f0f4f8 !important;
    color: #1a2332 !important;
}
.stApp { background: #f0f4f8 !important; }
.block-container { padding: 2rem 2rem !important; max-width: 100% !important; }
#MainMenu, footer, header, [data-testid="stToolbar"], .stDeployButton {
    display: none !important; visibility: hidden !important;
}

/* FORCE SIDEBAR ALWAYS OPEN */
[data-testid="stSidebar"] {
    min-width: 280px !important;
    max-width: 280px !important;
    background: #ffffff !important;
    border-right: 1px solid #dde8f4 !important;
    transform: translateX(0px) !important;
}
[data-testid="stSidebarCollapsedControl"] { display: none !important; }
[data-testid="stSidebarContent"] { padding: 1.25rem 1rem !important; }

/* BUTTONS — main area */
.stButton > button {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    background: #1b4f8a !important;
    color: #fff !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.6rem 1.2rem !important;
    transition: background 0.2s !important;
    box-shadow: 0 2px 6px rgba(27,79,138,0.2) !important;
}
.stButton > button:hover {
    background: #154080 !important;
    transform: translateY(-1px) !important;
}

/* SIDEBAR BUTTONS — override to look like screenshot */
div[data-testid="stSidebar"] .stButton > button {
    background: #f0f6ff !important;
    color: #1b4f8a !important;
    border: 1px solid #c8daf0 !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-size: 0.82rem !important;
    text-align: left !important;
    box-shadow: none !important;
}
div[data-testid="stSidebar"] .stButton > button:hover {
    background: #dbeafe !important;
    transform: none !important;
    box-shadow: none !important;
}

/* INPUTS */
.stTextInput > div > div > input {
    background: #ffffff !important;
    border: 1.5px solid #d0dbe8 !important;
    border-radius: 8px !important;
    color: #1a2332 !important;
    font-size: 0.92rem !important;
    padding: 0.65rem 1rem !important;
}
.stTextInput > div > div > input:focus {
    border-color: #1b4f8a !important;
    box-shadow: 0 0 0 3px rgba(27,79,138,0.1) !important;
}
.stTextInput label {
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    color: #5a7080 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
}

/* TABS */
.stTabs [data-baseweb="tab-list"] {
    background: #e8eef5 !important;
    border-radius: 10px !important;
    padding: 3px !important;
    border: 1px solid #d0dbe8 !important;
}
.stTabs [data-baseweb="tab"] {
    color: #6b82a0 !important;
    border-radius: 7px !important;
    font-size: 0.875rem !important;
    font-weight: 600 !important;
    padding: 0.5rem 1.5rem !important;
    border: none !important;
    background: transparent !important;
}
.stTabs [aria-selected="true"] {
    background: #1b4f8a !important;
    color: #fff !important;
}

[data-testid="stFileUploader"] {
    background: #ffffff !important;
    border: 2px dashed #b0c8e0 !important;
    border-radius: 12px !important;
}
.stSpinner > div { border-top-color: #1b4f8a !important; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_sb():
    return create_client(SUPABASE_URL, SUPABASE_KEY)
sb = get_sb()

for k, v in {
    "user": None, "token": None, "sid": None,
    "msgs": [], "analysis": None, "report": None, "page": "auth"
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

def extract_pdf(f):
    import pdfplumber, io
    txt = ""
    with pdfplumber.open(io.BytesIO(f.read())) as pdf:
        for p in pdf.pages[:50]:
            t = p.extract_text()
            if t: txt += t + "\n"
    return txt.strip()

def extract_image_text(f):
    import base64
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    b64 = base64.b64encode(f.read()).decode("utf-8")
    ext = f.name.split(".")[-1].lower()
    mime = "image/png" if ext == "png" else "image/jpeg"
    try:
        r = client.chat.completions.create(
            model="meta-llama/llama-4-maverick-17b-128e-instruct",
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": "This is a blood test report. Extract ALL text — every test name, value, unit, and normal range exactly as shown."}
            ]}], max_tokens=2000)
        return r.choices[0].message.content
    except Exception as e:
        return f"Image error: {e}"

def daily_count(uid):
    today = datetime.now().date().isoformat()
    r = sb.table("chat_sessions").select("id").eq("user_id", uid).gte("created_at", today).execute()
    return len(r.data) if r.data else 0

def analyze(txt):
    from groq import Groq
    c = Groq(api_key=GROQ_API_KEY)
    prompt = f"""You are a clinical medical AI. Analyze this blood test report.
Respond in EXACTLY this format:

SUMMARY
2 clear sentences about the patient's overall health.

KEY FINDINGS
List every test like:
• Test Name: Value Unit (Normal: range) — Normal/High/Low

CONCERNS
Only abnormal results as bullet points. If all normal: • All values within normal range.

RECOMMENDATIONS
3-4 short specific health tips based on the results.

BLOOD REPORT:
{txt[:7000]}"""
    for m in ["meta-llama/llama-4-maverick-17b-128e-instruct","llama-3.3-70b-versatile","llama-3.1-8b-instant","llama3-70b-8192"]:
        try:
            r = c.chat.completions.create(model=m, messages=[{"role":"user","content":prompt}], max_tokens=1500, temperature=0.2)
            res = r.choices[0].message.content
            if res and len(res) > 50: return res
        except: continue
    return "SUMMARY\nAnalysis failed.\n\nKEY FINDINGS\n• Could not extract.\n\nCONCERNS\n• Please retry.\n\nRECOMMENDATIONS\n• Upload a clearer file."

def chat_reply(report, analysis, history, q):
    from groq import Groq
    c = Groq(api_key=GROQ_API_KEY)
    system = f"""Clinical medical AI. Answer in max 80 words. Be direct and professional.
REPORT: {report[:2000]}
ANALYSIS: {analysis[:2000]}"""
    msgs = [{"role": "system", "content": system}]
    for m in history[-8:]: msgs.append({"role": m["role"], "content": m["content"]})
    msgs.append({"role": "user", "content": q})
    try:
        r = c.chat.completions.create(model="llama-3.3-70b-versatile", messages=msgs, max_tokens=300, temperature=0.4)
        return r.choices[0].message.content
    except Exception as e: return f"Error: {e}"

def save_sess(uid, title, report, analysis):
    r = sb.table("chat_sessions").insert({"user_id":uid,"title":title,"report_text":report,"analysis":analysis}).execute()
    return r.data[0]["id"] if r.data else None

def save_msg(sid, role, content):
    sb.table("chat_messages").insert({"session_id":sid,"role":role,"content":content}).execute()

def get_sessions(uid):
    r = sb.table("chat_sessions").select("*").eq("user_id",uid).order("created_at",desc=True).execute()
    return r.data or []

def get_msgs(sid):
    r = sb.table("chat_messages").select("*").eq("session_id",sid).order("created_at").execute()
    return r.data or []

def del_sess(sid):
    sb.table("chat_sessions").delete().eq("id",sid).execute()

# ── AUTH PAGE ─────────────────────────────────────────────────────────────────
def auth_page():
    import streamlit.components.v1 as components
    st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    .block-container { padding: 0 !important; max-width: 100% !important; }
    </style>""", unsafe_allow_html=True)

    col_l, col_r = st.columns([1.1, 0.9])
    with col_l:
        components.html("""
        <div style="background:linear-gradient(160deg,#0d1b35,#1b3060,#0d1b35);
             height:100vh;padding:3rem 3.5rem;display:flex;flex-direction:column;
             justify-content:space-between;font-family:-apple-system,sans-serif;">
          <div style="display:flex;align-items:center;gap:0.8rem;">
            <div style="width:38px;height:38px;background:linear-gradient(135deg,#3b82f6,#1d4ed8);
                 border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:1.1rem;">🏥</div>
            <div style="font-size:1.2rem;font-weight:700;color:#fff;">MediScan AI</div>
          </div>
          <div>
            <div style="font-size:0.75rem;font-weight:600;color:#60a5fa;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:1rem;">AI-Powered Blood Analysis</div>
            <div style="font-size:2.6rem;font-weight:800;color:#fff;line-height:1.15;letter-spacing:-0.03em;margin-bottom:1.25rem;">
              Your personal<br/><span style="color:#60a5fa;">medical AI</span><br/>assistant.
            </div>
            <div style="font-size:0.9rem;color:rgba(255,255,255,0.5);line-height:1.75;max-width:380px;margin-bottom:2rem;">
              Upload your blood test report and instantly receive clinical insights and personalized recommendations.
            </div>
            <div style="display:flex;flex-direction:column;gap:0.6rem;max-width:380px;">
              <div style="display:flex;align-items:center;gap:0.9rem;padding:0.8rem 1rem;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.09);border-radius:10px;">
                <div style="width:32px;height:32px;background:rgba(59,130,246,0.2);border-radius:8px;display:flex;align-items:center;justify-content:center;flex-shrink:0;">🔬</div>
                <div><div style="font-size:0.85rem;font-weight:600;color:rgba(255,255,255,0.9);">Instant CBC Analysis</div><div style="font-size:0.75rem;color:rgba(255,255,255,0.4);">Detect abnormal values in seconds</div></div>
              </div>
              <div style="display:flex;align-items:center;gap:0.9rem;padding:0.8rem 1rem;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.09);border-radius:10px;">
                <div style="width:32px;height:32px;background:rgba(59,130,246,0.2);border-radius:8px;display:flex;align-items:center;justify-content:center;flex-shrink:0;">🖼️</div>
                <div><div style="font-size:0.85rem;font-weight:600;color:rgba(255,255,255,0.9);">PDF & Image Support</div><div style="font-size:0.75rem;color:rgba(255,255,255,0.4);">Upload any format — AI reads it all</div></div>
              </div>
              <div style="display:flex;align-items:center;gap:0.9rem;padding:0.8rem 1rem;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.09);border-radius:10px;">
                <div style="width:32px;height:32px;background:rgba(59,130,246,0.2);border-radius:8px;display:flex;align-items:center;justify-content:center;flex-shrink:0;">💬</div>
                <div><div style="font-size:0.85rem;font-weight:600;color:rgba(255,255,255,0.9);">Ask AI Doctor</div><div style="font-size:0.75rem;color:rgba(255,255,255,0.4);">Chat about your results anytime</div></div>
              </div>
              <div style="display:flex;align-items:center;gap:0.9rem;padding:0.8rem 1rem;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.09);border-radius:10px;">
                <div style="width:32px;height:32px;background:rgba(59,130,246,0.2);border-radius:8px;display:flex;align-items:center;justify-content:center;flex-shrink:0;">🔒</div>
                <div><div style="font-size:0.85rem;font-weight:600;color:rgba(255,255,255,0.9);">Private & Secure</div><div style="font-size:0.75rem;color:rgba(255,255,255,0.4);">Your health data stays private</div></div>
              </div>
            </div>
          </div>
          <div style="font-size:0.72rem;color:rgba(255,255,255,0.25);">© 2026 MediScan AI · Powered by Groq LLaMA</div>
        </div>""", height=700, scrolling=False)

    with col_r:
        st.markdown("""
        <div style="text-align:center;padding:2.5rem 0 1.5rem;">
          <div style="width:52px;height:52px;background:linear-gradient(135deg,#1b4f8a,#0d2d5e);border-radius:14px;
               display:flex;align-items:center;justify-content:center;font-size:1.5rem;margin:0 auto 0.9rem;">🏥</div>
          <div style="font-size:1.5rem;font-weight:700;color:#1a2332;margin-bottom:0.25rem;">Patient Portal</div>
          <div style="font-size:0.85rem;color:#7090a0;">Sign in to access your blood analyses</div>
        </div>""", unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["Sign In", "Create Account"])
        with tab1:
            email = st.text_input("Email", key="si_e", placeholder="you@example.com")
            pwd   = st.text_input("Password", type="password", key="si_p", placeholder="Your password")
            st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)
            if st.button("Sign In →", key="signin", use_container_width=True):
                if not email or not pwd:
                    st.error("Please enter email and password.")
                else:
                    try:
                        res = sb.auth.sign_in_with_password({"email": email, "password": pwd})
                        st.session_state.user  = res.user
                        st.session_state.token = res.session.access_token
                        st.session_state.page  = "main"
                        st.rerun()
                    except:
                        st.error("Incorrect email or password.")

        with tab2:
            email2 = st.text_input("Email", key="su_e", placeholder="you@example.com")
            pwd2   = st.text_input("Password", type="password", key="su_p", placeholder="Min. 6 characters")
            st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)
            if st.button("Create Account →", key="signup", use_container_width=True):
                if not email2 or not pwd2:
                    st.error("Please fill in all fields.")
                elif len(pwd2) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    try:
                        sb.auth.sign_up({"email": email2, "password": pwd2})
                        st.success("✅ Account created! Switch to Sign In.")
                    except Exception as e:
                        st.error(f"Error: {e}")

        st.markdown("""
        <div style="margin-top:1.5rem;padding-top:1.25rem;border-top:1px solid #eaeef4;
             text-align:center;font-size:0.75rem;color:#aab8c8;">
          🔒 End-to-end encrypted · Your data is private
        </div>""", unsafe_allow_html=True)

# ── MAIN APP ──────────────────────────────────────────────────────────────────
def main_app():
    user      = st.session_state.user
    email     = user.email
    username  = email.split('@')[0]
    initials  = email[:2].upper()
    sessions  = get_sessions(user.id)
    dc        = daily_count(user.id)
    remaining = DAILY_LIMIT - dc

    # SIDEBAR
    with st.sidebar:
        st.markdown(f"""
        <div style="text-align:center;padding:0.5rem 0 1rem;border-bottom:1px solid #e2ecf5;margin-bottom:1rem;">
          <div style="font-size:1rem;font-weight:700;color:#1b4f8a;">💬 Chat Sessions</div>
        </div>""", unsafe_allow_html=True)

        if st.button("＋ New Analysis Session", use_container_width=True, key="new"):
            st.session_state.sid = None; st.session_state.msgs = []
            st.session_state.analysis = None; st.session_state.report = None
            st.rerun()

        st.markdown(f"""
        <div style="background:#f0f6ff;border:1px solid #c8daf0;border-radius:10px;
             padding:0.85rem 1rem;margin:0.75rem 0;text-align:center;">
          <div style="font-size:0.75rem;color:#5a7090;font-weight:500;margin-bottom:0.2rem;">Daily Analysis Limit</div>
          <div style="font-size:1rem;font-weight:700;color:#1b4f8a;">{remaining}/{DAILY_LIMIT} remaining</div>
        </div>""", unsafe_allow_html=True)

        if sessions:
            st.markdown("""<div style="font-size:0.72rem;font-weight:600;color:#7090a8;
                 text-transform:uppercase;letter-spacing:0.07em;margin-bottom:0.4rem;">
              Previous Sessions</div>""", unsafe_allow_html=True)
            for s in sessions[:10]:
                c1, c2 = st.columns([5, 1])
                with c1:
                    title = (s.get("title") or "Report")[:26]
                    if st.button(f"📋  {title}", key=f"s_{s['id']}", use_container_width=True):
                        st.session_state.sid = s["id"]
                        st.session_state.analysis = s.get("analysis")
                        st.session_state.report = s.get("report_text")
                        st.session_state.msgs = [{"role":m["role"],"content":m["content"]} for m in get_msgs(s["id"])]
                        st.rerun()
                with c2:
                    if st.button("🗑", key=f"d_{s['id']}"):
                        del_sess(s["id"])
                        if st.session_state.sid == s["id"]:
                            st.session_state.sid = None; st.session_state.msgs = []
                            st.session_state.analysis = None; st.session_state.report = None
                        st.rerun()

        st.markdown('<div style="height:1px;background:#e2ecf5;margin:0.75rem 0;"></div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.6rem;">
          <div style="width:26px;height:26px;border-radius:50%;background:#1b4f8a;display:flex;
               align-items:center;justify-content:center;font-size:0.68rem;font-weight:700;color:#fff;">{initials}</div>
          <div style="font-size:0.82rem;color:#1a2332;font-weight:500;">Hi, {username}!</div>
        </div>""", unsafe_allow_html=True)

        if st.button("Logout", use_container_width=True, key="so"):
            sb.auth.sign_out()
            for k in ["user","token","sid","msgs","analysis","report"]: st.session_state[k] = None
            st.session_state.msgs = []; st.session_state.page = "auth"
            st.rerun()

    # MAIN CONTENT
    if not st.session_state.analysis:
        now = datetime.now().strftime("%d-%m-%Y | %H:%M:%S")
        st.markdown(f"""
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1.5rem;">
          <div style="display:flex;align-items:center;gap:0.75rem;">
            <div style="font-size:1.4rem;">📊</div>
            <div style="font-size:1.4rem;font-weight:700;color:#1a2332;">{now}</div>
          </div>
          <div style="font-size:0.88rem;color:#5a7090;">👋 Hi, <strong>{username}</strong></div>
        </div>""", unsafe_allow_html=True)

        if remaining <= 0:
            st.warning("⚠️ Daily limit reached. Come back tomorrow.")
            return

        st.markdown("""
        <div style="background:#ffffff;border:1px solid #dde8f4;border-radius:14px;
             padding:2rem;box-shadow:0 2px 12px rgba(27,79,138,0.07);margin-bottom:1.5rem;">
          <div style="font-size:1rem;font-weight:700;color:#1a2332;margin-bottom:0.3rem;">Upload Blood Report</div>
          <div style="font-size:0.82rem;color:#7090a8;margin-bottom:1.5rem;">
            Supports PDF files and Images (JPG, PNG) — AI reads both formats
          </div>""", unsafe_allow_html=True)

        c1, c2 = st.columns([3, 2])
        with c1:
            uploaded = st.file_uploader("Upload", type=["pdf","jpg","jpeg","png"], label_visibility="collapsed")
        with c2:
            title = st.text_input("Session Label", value=datetime.now().strftime("%d-%m-%Y | %H:%M"))

        if uploaded:
            ext    = uploaded.name.split(".")[-1].lower()
            is_img = ext in ["jpg","jpeg","png"]
            fsize  = round(uploaded.size/1024, 1)
            if is_img:
                st.image(uploaded, width=360)
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:0.75rem;background:#f4f8ff;
                 border:1px solid #c8daf0;border-radius:10px;padding:0.8rem 1rem;margin:0.75rem 0;">
              <div style="font-size:1.3rem;">{"🖼️" if is_img else "📄"}</div>
              <div style="flex:1;">
                <div style="font-size:0.85rem;font-weight:600;color:#1a2332;">{uploaded.name}</div>
                <div style="font-size:0.72rem;color:#7090a8;">{fsize} KB · Ready</div>
              </div>
              <div style="background:#d1fae5;border:1px solid #6ee7b7;border-radius:6px;
                   padding:0.2rem 0.65rem;font-size:0.7rem;font-weight:600;color:#065f46;">✓ Valid</div>
            </div>""", unsafe_allow_html=True)

            if st.button("🔬  Run Analysis", key="analyze"):
                if is_img:
                    with st.spinner("Reading image..."):
                        try:
                            report_text = extract_image_text(uploaded)
                            if not report_text or len(report_text) < 30:
                                st.error("Could not read image."); return
                        except Exception as e:
                            st.error(f"Error: {e}"); return
                else:
                    with st.spinner("Reading PDF..."):
                        try:
                            report_text = extract_pdf(uploaded)
                            if len(report_text) < 30:
                                st.error("Could not read PDF."); return
                        except Exception as e:
                            st.error(f"Error: {e}"); return

                with st.spinner("Analyzing with AI..."):
                    analysis = analyze(report_text)

                sid = save_sess(user.id, title, report_text, analysis)
                st.session_state.sid = sid; st.session_state.analysis = analysis
                st.session_state.report = report_text; st.session_state.msgs = []
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.analysis:
        tab1, tab2 = st.tabs(["📋  Analysis Report", "💬  Ask AI Doctor"])

        with tab1:
            txt = st.session_state.analysis
            sections = {"SUMMARY":"","KEY FINDINGS":"","CONCERNS":"","RECOMMENDATIONS":""}
            current = None
            for line in txt.split('\n'):
                l = line.strip()
                if not l: continue
                matched = False
                for key in sections:
                    if l.upper().startswith(key):
                        current = key; matched = True; break
                if not matched and current:
                    sections[current] += line + "\n"

            def sh(icon, title):
                return f'<div style="display:flex;align-items:center;gap:0.6rem;margin:1.5rem 0 0.75rem;"><div style="width:26px;height:26px;background:#1b4f8a;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:0.8rem;color:#fff;">{icon}</div><span style="font-size:0.8rem;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:#4a6080;">{title}</span><div style="flex:1;height:1px;background:#e4edf5;margin-left:0.5rem;"></div></div>'

            if sections["SUMMARY"].strip():
                st.markdown(sh("📄","Clinical Summary"), unsafe_allow_html=True)
                st.markdown(f'<div style="background:#f4f8ff;border:1px solid #c8daf0;border-left:4px solid #1b4f8a;border-radius:10px;padding:1.25rem 1.5rem;font-size:0.92rem;color:#2a3f5a;line-height:1.75;">{sections["SUMMARY"].strip()}</div>', unsafe_allow_html=True)

            if sections["KEY FINDINGS"].strip():
                st.markdown(sh("🔬","Test Results"), unsafe_allow_html=True)
                findings = [f.strip() for f in sections["KEY FINDINGS"].strip().split('\n') if f.strip()]
                cols = st.columns(3)
                for i, f in enumerate(findings):
                    fc = f.lstrip('•-– ').strip()
                    is_h = any(w in f.upper() for w in ['HIGH','ELEVATED','ABOVE','CRITICAL'])
                    is_l = any(w in f.upper() for w in ['LOW','BELOW','DEFICIENT'])
                    if is_h:
                        bdg='<span style="display:inline-flex;padding:0.18rem 0.6rem;border-radius:100px;font-size:0.67rem;font-weight:700;text-transform:uppercase;background:#fef2f2;color:#dc2626;border:1px solid #fecaca;">↑ HIGH</span>'; tc="#dc2626"; bg="#fff"; bc="#fecaca"
                    elif is_l:
                        bdg='<span style="display:inline-flex;padding:0.18rem 0.6rem;border-radius:100px;font-size:0.67rem;font-weight:700;text-transform:uppercase;background:#fffbeb;color:#d97706;border:1px solid #fcd34d;">↓ LOW</span>'; tc="#d97706"; bg="#fff"; bc="#fde68a"
                    else:
                        bdg='<span style="display:inline-flex;padding:0.18rem 0.6rem;border-radius:100px;font-size:0.67rem;font-weight:700;text-transform:uppercase;background:#f0fdf4;color:#16a34a;border:1px solid #bbf7d0;">✓ NORMAL</span>'; tc="#16a34a"; bg="#fafffe"; bc="#d1fae5"
                    with cols[i%3]:
                        st.markdown(f'<div style="background:{bg};border:1px solid {bc};border-top:3px solid {tc};border-radius:12px;padding:1rem 1.1rem;margin-bottom:0.7rem;"><div style="font-size:0.67rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#9ab0c8;margin-bottom:0.45rem;">Result {i+1}</div><div style="font-size:0.83rem;color:#1a2332;line-height:1.55;margin-bottom:0.5rem;font-weight:500;">{fc}</div>{bdg}</div>', unsafe_allow_html=True)

            if sections["CONCERNS"].strip():
                cc = [c.strip() for c in sections["CONCERNS"].strip().split('\n') if c.strip()]
                if cc:
                    st.markdown(sh("⚠️","Areas of Concern"), unsafe_allow_html=True)
                    for c in cc:
                        st.markdown(f'<div style="background:#fff8f8;border:1px solid #fecaca;border-left:4px solid #dc2626;border-radius:8px;padding:0.85rem 1.1rem;margin-bottom:0.45rem;font-size:0.875rem;color:#4a2020;line-height:1.6;">⚠️ &nbsp;{c.lstrip("•-– ").strip()}</div>', unsafe_allow_html=True)

            if sections["RECOMMENDATIONS"].strip():
                rr = [r.strip() for r in sections["RECOMMENDATIONS"].strip().split('\n') if r.strip()]
                if rr:
                    st.markdown(sh("✅","Recommendations"), unsafe_allow_html=True)
                    for r in rr:
                        st.markdown(f'<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-left:4px solid #16a34a;border-radius:8px;padding:0.85rem 1.1rem;margin-bottom:0.45rem;font-size:0.875rem;color:#14532d;line-height:1.6;">✓ &nbsp;{r.lstrip("•-– ").strip()}</div>', unsafe_allow_html=True)

            st.markdown('<div style="background:#f8fafc;border:1px solid #e4edf5;border-radius:8px;padding:0.8rem 1rem;margin-top:1.5rem;font-size:0.75rem;color:#9ab0c8;line-height:1.6;">⚕️ <strong>Disclaimer:</strong> AI analysis for informational purposes only. Always consult a licensed physician.</div>', unsafe_allow_html=True)

        with tab2:
            st.markdown(sh("💬","Ask AI Doctor"), unsafe_allow_html=True)
            st.markdown('<div style="display:flex;flex-wrap:wrap;gap:0.4rem;margin-bottom:1.25rem;"><span style="background:#f4f8ff;border:1px solid #c8daf0;border-radius:100px;padding:0.32rem 0.9rem;font-size:0.78rem;color:#1b4f8a;font-weight:500;">Overall health status?</span><span style="background:#f4f8ff;border:1px solid #c8daf0;border-radius:100px;padding:0.32rem 0.9rem;font-size:0.78rem;color:#1b4f8a;font-weight:500;">Explain abnormal results</span><span style="background:#f4f8ff;border:1px solid #c8daf0;border-radius:100px;padding:0.32rem 0.9rem;font-size:0.78rem;color:#1b4f8a;font-weight:500;">Diet advice?</span><span style="background:#f4f8ff;border:1px solid #c8daf0;border-radius:100px;padding:0.32rem 0.9rem;font-size:0.78rem;color:#1b4f8a;font-weight:500;">See a doctor?</span></div>', unsafe_allow_html=True)

            for msg in st.session_state.msgs:
                if msg["role"] == "user":
                    st.markdown(f'<div style="display:flex;justify-content:flex-end;margin:0.6rem 0;"><div style="background:linear-gradient(135deg,#1b4f8a,#0d2d5e);color:#fff;border-radius:16px 16px 4px 16px;padding:0.8rem 1.1rem;max-width:68%;font-size:0.875rem;line-height:1.55;">{msg["content"]}</div></div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div style="display:flex;align-items:flex-start;gap:0.75rem;margin:0.6rem 0;"><div style="width:30px;height:30px;border-radius:50%;background:#1b4f8a;display:flex;align-items:center;justify-content:center;font-size:0.8rem;flex-shrink:0;">🏥</div><div style="background:#ffffff;border:1px solid #dde8f4;color:#1a2332;border-radius:16px 16px 16px 4px;padding:0.8rem 1.1rem;max-width:74%;font-size:0.875rem;line-height:1.65;">{msg["content"]}</div></div>', unsafe_allow_html=True)

            c1, c2 = st.columns([5, 1])
            with c1:
                q = st.text_input("q", placeholder="Ask about your blood results...", label_visibility="collapsed", key="cq")
            with c2:
                send = st.button("Send →", key="send", use_container_width=True)

            if send and q.strip():
                st.session_state.msgs.append({"role":"user","content":q})
                if st.session_state.sid: save_msg(st.session_state.sid,"user",q)
                with st.spinner(""):
                    reply = chat_reply(st.session_state.report or "", st.session_state.analysis, st.session_state.msgs[:-1], q)
                st.session_state.msgs.append({"role":"assistant","content":reply})
                if st.session_state.sid: save_msg(st.session_state.sid,"assistant",reply)
                st.rerun()

if st.session_state.user is None:
    auth_page()
else:
    main_app()
