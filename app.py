import os
import streamlit as st
from google import genai
from google.genai import types
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
from google.oauth2 import service_account

# Page setup
st.set_page_config(
    page_title="KolterAI Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for compact iframe embedding in Looker Studio
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {
        padding: 0.75rem !important;
    }
    .stChatMessage {
        padding: 0.5rem 0.75rem !important;
        font-size: 0.9rem !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("### 📊 KolterAI Assistant")
st.caption("Connected to live GA4 metrics.")

# Verify secrets exist
if "GEMINI_API_KEY" not in st.secrets or "GA4_PROPERTY_ID" not in st.secrets or "gcp_service_account" not in st.secrets:
    st.error("⚠️ Missing credentials. Check Streamlit Secrets configuration.")
    st.stop()

property_id = st.secrets["GA4_PROPERTY_ID"]

# Initialize API Clients
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

# Fetch live GA4 metric summary for the last 30 days
def get_live_ga4_summary(prop_id: str) -> str:
    try:
        request = RunReportRequest(
            property=f"properties/{prop_id}",
            dimensions=[Dimension(name="sessionSourceMedium")],
            metrics=[
                Metric(name="activeUsers"),
                Metric(name="sessions"),
                Metric(name="conversions"),
                Metric(name="bounceRate")
            ],
            date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
            limit=5
        )

        response = ga4_client.run_report(request)
        
        data_summary = []
        for row in response.rows:
            source = row.dimension_values[0].value
            users = row.metric_values[0].value
            sessions = row.metric_values[1].value
            conversions = row.metric_values[2].value
            bounce_rate = round(float(row.metric_values[3].value) * 100, 2)
            data_summary.append(f"- Channel: {source} | Users: {users} | Sessions: {sessions} | Conversions: {conversions} | Bounce Rate: {bounce_rate}%")
            
        return "\n".join(data_summary) if data_summary else "No traffic metric data returned."
    except Exception as e:
        return f"Error pulling GA4 data: {str(e)}"

# Query GA4 context on load
with st.spinner("Fetching live GA4 context..."):
    ga4_data_context = get_live_ga4_summary(property_id)

SYSTEM_INSTRUCTION = f"""
You are KolterAI Assistant, embedded inside a Looker Studio dashboard.
You have access to live GA4 performance data for the last 30 days:

[LIVE GA4 DATA CONTEXT]
{ga4_data_context}

Guidelines:
1. Reference the live metrics above when users ask about site performance or traffic sources.
2. Keep answers concise, structured, and easy to read in a narrow dashboard panel.
3. Use bolding and bullet points for high scannability.
"""

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "👋 Hi! I'm KolterAI Assistant. I'm synced with your live GA4 metrics for the last 30 days. Ask me about your traffic channels, bounce rates, or conversions!"
        }
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask about your GA4 metrics..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

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
                    temperature=0.4,
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
            st.error(f"Error querying Gemini API: {str(e)}")
