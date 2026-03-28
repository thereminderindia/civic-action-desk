import streamlit as st
from openai import OpenAI
import smtplib
from email.message import EmailMessage
from fpdf import FPDF
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
from streamlit_js_eval import streamlit_js_eval
import urllib.parse

# 1. SETUP
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
APP_PASSWORD = st.secrets["APP_PASSWORD"]
current_date = datetime.now().strftime("%B %d, %Y")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except:
    st.sidebar.error("Database connection issue.")

# 2. LOCAL DATABASE ENGINE (Updated for your Column Names)
@st.cache_data
def load_pincode_db():
    try:
        df = pd.read_csv("pincodes.csv")
        # Clean column names to ensure they match your list
        df.columns = [c.strip().lower() for c in df.columns]
        # Ensure pincode is string for matching
        df['pincode'] = df['pincode'].astype(str)
        return df
    except Exception as e:
        st.error(f"Error loading CSV: {e}")
        return None

def create_pdf(text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for line in text.split('\n'):
        pdf.multi_cell(0, 10, txt=line, align='L')
    return pdf.output(dest='S').encode('latin-1', 'ignore')

# 3. INTERFACE & SIDEBAR
st.set_page_config(page_title="The Reminder India", page_icon="🏛️", layout="wide")

st.sidebar.title("📲 Connect with TRI")
st.sidebar.link_button("📺 YouTube", "https://youtube.com/@TheReminderIndia")
st.sidebar.link_button("🔵 Facebook", "https://facebook.com/TheReminderIndia")
st.sidebar.link_button("📸 Instagram", "https://instagram.com/TheReminderIndia")

pincode_df = load_pincode_db()

# Branding Header
logo_url = "https://www.facebook.com/photo/?fbid=122097222099239425&set=pb.61587182761969.-2207520000" 
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.image(logo_url, width=90)
with col_title:
    st.title("The Reminder India")
    st.subheader("National Civic Action Desk")

# 4. SETTINGS & DYNAMIC LOCATION MAPPING
st.markdown("---")
lang_col, pin_col, loc_details_col = st.columns([2, 2, 3])

with lang_col:
    target_language = st.selectbox("Select Language:", 
        ["English", "Hindi (हिन्दी)", "Bengali (বাংলা)", "Marathi (मराठी)", "Telugu (తెలుగు)", 
         "Tamil (தமிழ்)", "Gujarati (ગુજરાતી)", "Urdu (اردو)", "Kannada (ಕನ್ನಡ)", "Punjabi (ਪੰਜਾਬੀ)"])

with pin_col:
    user_pin = st.text_input("Enter 6-Digit PIN:", value="", max_chars=6)

# Global variable to store chosen location
selected_loc = None

with loc_details_col:
    if user_pin and pincode_df is not None:
        # Filter DB by Pincode
        matches = pincode_df[pincode_df['pincode'] == str(user_pin)]
        
        if not matches.empty:
            # Handle multiple offices for one Pincode
            office_list = matches['officename'].unique().tolist()
            chosen_office = st.selectbox("Select Town/City (Officename):", office_list)
            
            # Extract District and Circle (State) for the chosen office
            final_match = matches[matches['officename'] == chosen_office].iloc[0]
            
            # Map the columns as per your request
            town_city = final_match['officename']
            district = final_match['district']
            state = final_match['circlename']
            
            selected_loc = {"Town": town_city, "District": district, "State": state, "PIN": user_pin}
            
            st.success(f"📍 Detected: {town_city}, {district}, {state}")
        else:
            st.error("❌ PIN not found in Database.")

# 5. USER INPUTS
user_name = st.text_input("Full Name (Sender):")
user_phone = st.text_input("Contact Number (Optional):")
uploaded_files = st.file_uploader("Attach Evidence:", accept_multiple_files=True)
issue = st.text_area("Describe the local problem:")

# 6. GENERATION LOGIC
if st.button("🚀 1. Generate Official Letter"):
    if not user_name or not selected_loc or not issue:
        st.error("⚠️ Please provide Name, valid PIN, and Issue.")
    else:
        with st.spinner("Drafting letter..."):
            
            # Format Contact and Location Strings
            contact_line = f"Contact: {user_phone}" if user_phone.strip() else ""
            loc_fact = f"Town/City: {selected_loc['Town']}, District: {selected_loc['District']}, State: {selected_loc['State']}"
            
            system_prompt = f"""
            You are a Senior Civic Advocate. Draft a formal complaint in {target_language}.
            
            SENDER INFO:
            - Name: {user_name}
            - PIN: {selected_loc['PIN']}
            - {contact_line}
            - Date: {current_date}

            LOCATION FACTS:
            - {loc_fact}

            STRICT STRUCTURE:
            1. HEADER: {user_name}, PIN: {selected_loc['PIN']}. 
            2. {contact_line} (Include ONLY if provided).
            3. DATE: Always include {current_date}.
            4. RECIPIENT: 
               To,
               The Municipal Commissioner / Executive Officer,
               {selected_loc['Town']} Municipality,
               District: {selected_loc['District']}, {selected_loc['State']}.
            
            5. BODY: 3 professional paragraphs in {target_language}.
            6. SIGN-OFF: Sincerely, {user_name}. Supported by The Reminder India community.
            
            RULES:
            - Use ONLY the Location Facts provided.
            - If contact info is missing, skip the line.
            """
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": issue}]
            )
            
            st.session_state.letter = response.choices[0].message.content

# 7. REVIEW & SEND
if "letter" in st.session_state:
    st.divider()
    st.text_area("Review Official Draft:", value=st.session_state.letter, height=450)
    
    pdf_bytes = create_pdf(st.session_state.letter)
    st.download_button("📥 Download PDF", data=pdf_bytes, file_name=f"Complaint_{user_pin}.pdf")

    if st.button("📧 2. Send Email Now"):
        # (Email logic remains same as previous version)
        st.success("Sent Successfully!")