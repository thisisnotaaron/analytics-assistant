import os
import streamlit as st
from google import genai
from google.genai import types

# Page setup: optimized layout for sidebar/panel embedding
st.set_page_config(
    page_title="Web Analytics Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS: Hide Streamlit chrome & adjust padding for snug iframe fit inside Looker Studio
st.markdown("""
<style>
    /* Hide Streamlit header, footer, and hamburger menu */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Remove body margins for iframe embedding */
    .block-container {
        padding-top: 0.75rem !important;
        padding-bottom: 0.75rem !important;
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
    }
    
    /* Reduce chat padding for tight UI constraints */
    .stChatMessage {
        padding: 0.5rem 0.75rem !important;
        font-size: 0.9rem !important;
    }
</style>
""", unsafe_allow_html=True)

# Compact Header
st.markdown("### 📊 Web Analytics AI Assistant")
st.caption("Ask about web traffic trends, GA4 metrics, or conversion funnel diagnostics.")

# Retrieve API key from secrets, env vars, or sidebar input fallback
api_key = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")

if not api_key:
    with st.sidebar:
        st.subheader("Configuration")
        api_key = st.text_input("Enter Gemini API Key", type="password")
        st.info("Get an API key from [Google AI Studio](https://aistudio.google.com/).")

if not api_key:
    st.warning("⚠️ API Key missing. Add `GEMINI_API_KEY` to `.streamlit/secrets.toml` or sidebar settings.")
    st.stop()

# Initialize Gemini Client
@st.cache_resource
def get_gemini_client(key: str):
    return genai.Client(api_key=key)

client = get_gemini_client(api_key)

# System Instructions tailored for Web Analytics & Looker Studio
SYSTEM_INSTRUCTION = """
You are an expert Web Analytics AI Assistant embedded inside a Looker Studio dashboard. 
Your role is to help marketers, product managers, and site owners interpret web metrics.

Guidelines:
1. Explain GA4 metrics simply (e.g., Session vs User, Bounce Rate vs Engagement Rate, Conversions).
2. Provide diagnostic frameworks when users ask why metrics dropped or spiked (e.g., check channel breakdown, technical errors, campaign end dates).
3. Keep responses structured, concise, and easy to read inside a narrow dashboard sidebar.
4. Use bullet points and bold key terms for high scannability.
"""

# Initialize session state for conversation history
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "👋 Hi! I'm your analytics assistant. Ask me questions like:\n- *Why might organic traffic drop week-over-week?*\n- *What's the difference between Sessions and Engaged Sessions?*\n- *How do I diagnose a dip in conversion rate?*"
        }
    ]

# Render existing chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User Chat Input
if prompt := st.chat_input("Ask an analytics question..."):
    # Append & display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Convert chat history into Google GenAI Content objects
    contents = []
    for msg in st.session_state.messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])]))

    # Stream Gemini Response
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        
        try:
            response = client.models.generate_content_stream(
                model="gemini-2.5-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.5,
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
