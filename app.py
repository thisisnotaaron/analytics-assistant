import os
import re
from datetime import datetime
import streamlit as st
from google import genai
from google.genai import types
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
from google.oauth2 import service_account

# Page Configuration
st.set_page_config(
    page_title="KolterAI Assistant",
    page_icon="https://www.gstatic.com/lamda/images/favicon_v1_150160cddff784c78619.svg",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS: Force Light Mode & High Contrast
st.markdown("""
<style>
    /* Hide default Streamlit headers & footers */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* App container background & text colors */
    .stApp {
        background-color: #f8f9fa !important;
        color: #1f1f1f !important;
    }

    .block-container {
        padding: 1.25rem 1rem !important;
        max-width: 100% !important;
    }

    /* Header styling */
    .app-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid #e3e8ef;
        margin-bottom: 0.5rem;
    }
    
    .app-title {
        font-size: 1.1rem;
        font-weight: 600;
        letter-spacing: -0.02em;
        color: #1f1f1f !important;
    }

    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 0.75rem;
        font-weight: 500;
        color: #444746 !important;
        background: #e9eef6 !important;
        padding: 4px 10px;
        border-radius: 12px;
    }

    .status-dot {
        height: 7px;
        width: 7px;
        background-color: #1e8e3e;
        border-radius: 50%;
        display: inline-block;
    }

    .session-disclaimer {
        font-size: 0.75rem;
        color: #5e5e5e !important;
        margin-bottom: 1rem;
    }

    /* Chat bubble container overrides */
    [data-testid="stChatMessage"] {
        border-radius: 16px !important;
        padding: 0.85rem 1.1rem !important;
        margin-bottom: 0.75rem !important;
        border: 1px solid #e3e8ef !important;
        font-size: 0.9rem !important;
        line-height: 1.5 !important;
        color: #1f1f1f !important;
    }

    /* Assistant response background */
    [data-testid="stChatMessage"]:nth-child(odd) {
        background-color: #ffffff !important;
    }

    /* User prompt background */
    [data-testid="stChatMessage"]:nth-child(even) {
        background-color: #f0f4f9 !important;
        border-color: #d3e3fd !important;
    }

    /* Text inside chat bubbles */
    [data-testid="stChatMessage"] p {
        color: #1f1f1f !important;
    }

    /* Input box styling */
    .stChatInput > div {
        border-radius: 24px !important;
        border: 1px solid #c4c7c5 !important;
        background-color: #ffffff !important;
        color: #1f1f1f !important;
    }
</style>
""", unsafe_allow_html=True)

# Helper Function: PII Regex Sanitization
def sanitize_pii(text: str) -> str:
    if not text:
        return text
    # Redact email addresses
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    text = re.sub(email_pattern, '[REDACTED_EMAIL]', text)
    
    # Redact long UUIDs / User IDs (16+ chars)
    uuid_pattern = r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b'
    text = re.sub(uuid_pattern, '[REDACTED_ID]', text)
    
    # Redact phone numbers
    phone_pattern = r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'
    text = re.sub(phone_pattern, '[REDACTED_PHONE]', text)
    
    return text

# Verify secrets existence
if "GEMINI_API_KEY" not in st.secrets or "GA4_PROPERTY_ID" not in st.secrets or "gcp_service_account" not in st.secrets:
    st.error("Missing credentials. Please check Streamlit Secrets configuration.")
    st.stop()

property_id = st.secrets["GA4_PROPERTY_ID"]

# Cached Client Initialization
@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

@st.cache_resource
def get_ga4_client():
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = service_account.Credentials.from_service_account_info(creds_dict)
    return BetaAnalyticsDataClient(credentials=creds)

client = get_gemini_client()
ga4_client = get_ga4_client()

# Fetch live GA4 metric summary for YTD (Year-To-Date)
def get_live_ga4_summary(prop_id: str) -> str:
    try:
        # Dynamically set start date to January 1st of current year
        ytd_start = f"{datetime.now().year}-01-01"

        request = RunReportRequest(
            property=f"properties/{prop_id}",
            dimensions=[Dimension(name="sessionSourceMedium")],
            metrics=[
                Metric(name="activeUsers"),
                Metric(name="sessions"),
                Metric(name="conversions"),
                Metric(name="bounceRate")
            ],
            date_ranges=[DateRange(start_date=ytd_start, end_date="today")],
            limit=10
        )

        response = ga4_client.run_report(request)
        
        data_summary = []
        for row in response.rows:
            source = row.dimension_values[0].value
            users = row.metric_values[0].value
            sessions = row.metric_values[1].value
            conversions = row.metric_values[2].value
            bounce_rate = round(float(row.metric_values[3].value) * 100, 2)
            data_summary.append(
                f"- Channel: {source} | Active Users: {users} | Sessions: {sessions} | Conversions: {conversions} | Bounce Rate: {bounce_rate}%"
            )
            
        return "\n".join(data_summary) if data_summary else "No traffic metric data returned for YTD."
    except Exception as e:
        return f"Unable to retrieve GA4 metrics: {str(e)}"

# Query & Sanitize GA4 YTD Context on Load
with st.spinner("Connecting to Google Analytics..."):
    ga4_data_context = sanitize_pii(get_live_ga4_summary(property_id))

# System Instruction with Analyst Persona
SYSTEM_INSTRUCTION = f"""
You are KolterAI, a senior web analytics consultant embedded directly inside a performance dashboard.
You have real-time access to Year-To-Date (YTD) GA4 metric summaries for this site:

[YTD GA4 DATA CONTEXT]
{ga4_data_context}

Guidelines:
1. Provide concise, high-density analytical insights. Avoid fluff, filler phrases, or robotic pleasantries.
2. Structure observations logically using concise bullet points and bolding for key performance metrics.
3. Compare channel performance objectively based strictly on the YTD data provided above.
4. Maintain a professional, executive-ready tone suitable for digital strategy teams.
"""

# Header UI
st.markdown("""
<div class="app-header">
    <div class="app-title">KolterAI Intelligence</div>
    <div class="status-badge">
        <span class="status-dot"></span>
        GA4 Live (YTD)
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="session-disclaimer">Session history is temporary and clears upon refreshing the dashboard.</div>', unsafe_allow_html=True)

# Session State & Message Initialization
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Connected to GA4 Year-To-Date metrics. Ask a question regarding traffic acquisition, channel conversion efficiency, or engagement trends."
        }
    ]

# Render Message History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat Input Processing
if prompt := st.chat_input("Ask about YTD analytics..."):
    clean_prompt = sanitize_pii(prompt)
    st.session_state.messages.append({"role": "user", "content": clean_prompt})
    
    with st.chat_message("user"):
        st.markdown(clean_prompt)

    # Reconstruct Chat History for Gemini API Payload
    contents = []
    for msg in st.session_state.messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])]))

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        try:
            response = client.models.generate_content_stream(
                model="gemini-3.6-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.3,
                )
            )
            
            full_response = ""
            for chunk in response:
                if chunk.text:
                    full_response += chunk.text
                    response_placeholder.markdown(full_response + "▌")
            
            response_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})

        except Exception as e:
            st.error(f"Error querying model: {str(e)}")
