import streamlit as st
from openai import OpenAI
import smtplib
from email.message import EmailMessage
from fpdf import FPDF
import pandas as pd
import re
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
from streamlit_js_eval import streamlit_js_eval
import urllib.parse

# 1. SETUP & AUTHENTICATION
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
APP_PASSWORD = st.secrets["APP_PASSWORD"]
current_date = datetime.now().strftime("%d %B, %Y")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except:
    st.sidebar.error("Database connection issue.")

# EMAIL VALIDATION HELPER
def is_valid_email(email_str):
    if not email_str.strip():
        return True 
    emails = [e.strip() for e in email_str.split(',')]
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return all(re.match(pattern, e) for e in emails if e)

# 2. LOCAL CSV ENGINE
@st.cache_data
def load_pincode_db():
    try:
        df = pd.read_csv("pincodes.csv")
        df.columns = [c.strip().lower() for c in df.columns]
        df['pincode'] = df['pincode'].astype(str)
        return df
    except:
        return None

def create_pdf(text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)
    for line in text.split('\n'):
        if current_date in line:
            pdf.cell(0, 10, txt=line, ln=True, align='R')
        else:
            pdf.multi_cell(0, 10, txt=line, align='L')
    return pdf.output(dest='S').encode('latin-1', 'ignore')

# 3. INTERFACE & SIDEBAR
st.set_page_config(page_title="The Reminder India", page_icon="🏛️", layout="wide")

st.sidebar.title("📲 Connect with TRI")
st.sidebar.link_button("📺 YouTube", "https://youtube.com/@TheReminderIndia")
st.sidebar.link_button("🔵 Facebook", "https://facebook.com/TheReminderIndia")
st.sidebar.link_button("📸 Instagram", "https://instagram.com/TheReminderIndia")
st.sidebar.markdown("---")
st.sidebar.title("🛠️ Tools")
st.sidebar.link_button("🔍 Pincode Verify", "https://www.indiapost.gov.in/VAS/Pages/findpincode.aspx")

pincode_df = load_pincode_db()

# Branding
logo_url = "https://www.facebook.com/photo/?fbid=122097222099239425&set=pb.61587182761969.-2207520000" 
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.image(logo_url, width=90)
with col_title:
    st.title("The Reminder India")
    st.subheader("National Civic Action Desk")

# 4. STEP 1: LANGUAGE & LOCATION
st.markdown("---")
st.subheader("📍 Step 1: Language & Location")
lang_col, pin_col, details_col = st.columns([2, 2, 4])

with lang_col:
    target_language = st.selectbox("Select Letter Language:", 
        ["English", "Hindi (हिन्दी)", "Bengali (বাংলা)", "Marathi (मराठी)", 
         "Telugu (తెలుగు)", "Tamil (தமிழ்)", "Gujarati (ગુજરાતી)", 
         "Urdu (اردו)", "Kannada (କನ್ನಡ)", "Odia (ଓଡ଼ିଆ)", 
         "Malayalam (മലയാളം)", "Punjabi (ਪੰਜਾਬੀ)", "Assamese (অসমੀয়া)", 
         "Maithili (मैथिली)", "Santali (संताली)", "Kashmiri (کٲशُر)", 
         "Nepali (नेपाली)", "Konkani (कोंकਣੀ)", "Sindhi (سنڌي)", 
         "Dogri (डोगरी)", "Manipuri (মৈতৈলোন)", "Bodo (बर')", "Sanskrit (संस्कृतम्)"])

with pin_col:
    user_pin = st.text_input("Enter 6-Digit PIN:", value="", max_chars=6)
    if user_pin and (not user_pin.isdigit() or len(user_pin) != 6):
        st.error("⚠️ Pincode must be exactly 6 digits.")

selected_loc = None
if user_pin and len(user_pin) == 6 and pincode_df is not None:
    matches = pincode_df[pincode_df['pincode'] == str(user_pin)]
    if not matches.empty:
        with details_col:
            office_list = matches['officename'].unique().tolist()
            chosen_office = st.selectbox("Confirm Town/City:", office_list)
            row = matches[matches['officename'] == chosen_office].iloc[0]
            selected_loc = {"Town": row['officename'], "District": row['district'], "State": row['circlename'], "PIN": user_pin}
            st.success(f"✅ Area: {selected_loc['Town']}, {selected_loc['District']}")
            
            # SIDEBAR SEARCH TOOL
            st.sidebar.markdown("---")
            st.sidebar.subheader("🔍 Find Official Email")
            search_query = f"official email municipal commissioner {selected_loc['Town']} {selected_loc['District']} site:.gov.in OR site:.nic.in"
            google_url = f"https://www.google.com/search?q={urllib.parse.quote(search_query)}"
            st.sidebar.link_button(f"🌐 Search for {selected_loc['Town']} Email", google_url)
    else:
        with details_col:
            st.error("❌ PIN not found.")

# GPS & File Uploads
col_gps, col_files = st.columns(2)
with col_gps:
    if st.button("🛰️ Capture Exact GPS"):
        loc = streamlit_js_eval(data_key='pos', func_name='getCurrentPosition', want_output=True)
        if loc:
            lat = loc['coords']['latitude']
            lon = loc['coords']['longitude']
            # Creating a professional Google Maps Navigation link
            st.session_state.gps_coord = f"{lat}, {lon}"
            st.session_state.maps_link = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}&travelmode=driving"
            st.success(f"✅ GPS Captured! Navigation link ready.")

with col_files:
    uploaded_files = st.file_uploader("Attach Evidence (Photos/Videos):", accept_multiple_files=True)

# 5. STEP 2: REPORTER DETAILS
st.markdown("---")
st.subheader("📝 Step 2: Reporter Details")
user_name = st.text_input("Full Name (Sender):")
user_phone = st.text_input("Contact Number (Optional):", max_chars=10)
if user_phone and (not user_phone.isdigit() or len(user_phone) != 10):
    st.error("⚠️ Phone number must be exactly 10 digits.")

issue = st.text_area("Describe the local problem:")

# 6. STEP 3: GENERATION
if st.button("🚀 1. Generate Official Letter"):
    if "letter" in st.session_state:
        del st.session_state["letter"]
        
    if not user_name or not selected_loc or not issue or len(user_pin) != 6:
        st.error("⚠️ Please complete all fields.")
    else:
        with st.spinner(f"Drafting formal petition..."):
            p_val = user_phone.strip()
            contact_line = f"Contact Number: {p_val}" if p_val else ""
            
            # LOGIC: Check if GPS exists
            maps_url = st.session_state.get('maps_link', "")
            gps_line = f"Issue Location (Google Maps Navigation): {maps_url}" if maps_url else "NONE"
            
            evidence_count = len(uploaded_files) if uploaded_files else 0

            system_prompt = f"""
            Draft a professional civic complaint in {target_language}.
            
            STRICT LAYOUT:
            1. DATE (TOP RIGHT): '{current_date}'
            2. FROM: Name: {user_name}. {contact_line}
            3. TO: The Municipal Commissioner, {selected_loc['Town']}, {selected_loc['District']}. PIN: {selected_loc['PIN']}
            4. BODY: 
               - State issue: {issue}
               - GPS RULE: If gps_line is not 'NONE', include this exact line: {gps_line}. If it is 'NONE', do NOT mention GPS, location links, or 'NOT_CAPTURED'.
               - EVIDENCE: If files > 0, mention that evidence is attached. Otherwise, skip.
            5. SIGN-OFF: Sincerely, {user_name}. Supported by The Reminder India community.

            RULES: RAW TEXT ONLY. NO backticks (```). Omit empty fields.
            END WITH: 'SUGGESTED_EMAIL: '
            """
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": issue}]
            )
            res_content = response.choices[0].message.content.replace("```", "").strip()
            st.session_state.letter = res_content.split("SUGGESTED_EMAIL:")[0].strip()
            raw_email = res_content.split("SUGGESTED_EMAIL:")[1].strip() if "SUGGESTED_EMAIL:" in res_content else ""
            st.session_state.sug_email = raw_email.replace("`", "").replace("'", "").strip()

# 7. STEP 4: REVIEW & MULTI-SEND
if "letter" in st.session_state:
    st.divider()
    st.subheader("📬 Step 4: Final Review & Email Controls")
    st.text_area("Letter Content:", value=st.session_state.letter, height=500)
    
    col_to, col_cc, col_bcc = st.columns(3)
    with col_to:
        rec_to = st.text_input("To (Primary Official):", value=st.session_state.sug_email)
    with col_cc:
        rec_cc = st.text_input("CC (Public Copy):", value="")
    with col_bcc:
        rec_bcc = st.text_input("BCC (Secret Archive):", value="")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        pdf_bytes = create_pdf(st.session_state.letter)
        st.download_button("📥 Download Print PDF", data=pdf_bytes, file_name=f"TRI_Report_{user_pin}.pdf")
    with col_btn2:
        if st.button("📧 Send Official Email Now"):
            if not is_valid_email(rec_to) or not is_valid_email(rec_cc) or not is_valid_email(rec_bcc):
                st.error("❌ Invalid email format.")
            elif not rec_to:
                st.error("❌ Recipient required.")
            else:
                with st.spinner("Sending..."):
                    try:
                        msg = EmailMessage()
                        msg.set_content(st.session_state.letter)
                        msg['Subject'] = f"CIVIC COMPLAINT: {selected_loc['Town']} - {user_name}"
                        msg['From'] = SENDER_EMAIL
                        msg['To'] = rec_to
                        if rec_cc: msg['Cc'] = rec_cc
                        if rec_bcc: msg['Bcc'] = rec_bcc
                        if uploaded_files:
                            for f in uploaded_files:
                                msg.add_attachment(f.read(), maintype='application', subtype='octet-stream', filename=f.name)
                        smtp = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                        smtp.login(SENDER_EMAIL, APP_PASSWORD)
                        smtp.send_message(msg)
                        smtp.quit()
                        st.success("✅ Reported Successfully!")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Error: {e}")
