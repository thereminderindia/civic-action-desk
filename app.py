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

# 1. SETUP & AUTHENTICATION
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
APP_PASSWORD = st.secrets["APP_PASSWORD"]
current_date = datetime.now().strftime("%d %B, %Y")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except:
    st.sidebar.error("Database connection issue.")

# 2. LOCAL CSV ENGINE
@st.cache_data
def load_pincode_db():
    try:
        df = pd.read_csv("pincodes.csv")
        df.columns = [c.strip().lower() for c in df.columns]
        df['pincode'] = df['pincode'].astype(str)
        return df
    except Exception as e:
        st.error(f"Error loading pincodes.csv: {e}")
        return None

def create_pdf(text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
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
st.sidebar.link_button("🔍 Official Pincode Verify", "https://www.indiapost.gov.in/VAS/Pages/findpincode.aspx")

pincode_df = load_pincode_db()

# Branding Header
logo_url = "https://www.facebook.com/photo/?fbid=122097222099239425&set=pb.61587182761969.-2207520000" 
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.image(logo_url, width=90)
with col_title:
    st.title("The Reminder India")
    st.subheader("National Civic Action Desk")

# 4. STEP 1: LANGUAGE & LOCATION (22 LANGUAGES RESTORED)
st.markdown("---")
st.subheader("📍 Step 1: Language & Area Selection")
lang_col, pin_col, details_col = st.columns([2, 2, 4])

with lang_col:
    target_language = st.selectbox("Select Letter Language:", 
        ["English", "Hindi (हिन्दी)", "Bengali (বাংলা)", "Marathi (मराठी)", 
         "Telugu (తెలుగు)", "Tamil (தமிழ்)", "Gujarati (ગુજરાતી)", 
         "Urdu (اردو)", "Kannada (ಕನ್ನಡ)", "Odia (ଓଡ଼ିଆ)", 
         "Malayalam (മലയാളം)", "Punjabi (ਪੰਜਾਬੀ)", "Assamese (অসমীয়া)", 
         "Maithili (मैथिली)", "Santali (संताली)", "Kashmiri (کٲशُر)", 
         "Nepali (नेपाली)", "Konkani (कोंকਣੀ)", "Sindhi (سنڌي)", 
         "Dogri (डोगरी)", "Manipuri (মৈতৈলোন)", "Bodo (बर')", "Sanskrit (संस्कृतम्)"])

with pin_col:
    user_pin = st.text_input("Enter 6-Digit PIN:", value="", max_chars=6, help="Must be exactly 6 digits")

selected_loc = None
with details_col:
    if user_pin and len(user_pin) == 6 and pincode_df is not None:
        matches = pincode_df[pincode_df['pincode'] == str(user_pin)]
        if not matches.empty:
            office_list = matches['officename'].unique().tolist()
            chosen_office = st.selectbox("Confirm Town/City:", office_list)
            row = matches[matches['officename'] == chosen_office].iloc[0]
            selected_loc = {"Town": row['officename'], "District": row['district'], "State": row['circlename'], "PIN": user_pin}
            st.success(f"✅ Area: {selected_loc['Town']}, {selected_loc['District']}")
        else:
            st.error("❌ PIN not found in database.")
    elif user_pin and len(user_pin) < 6:
        st.warning("⚠️ Pincode must be 6 digits.")

# GPS & File Uploads
col_gps, col_files = st.columns(2)
with col_gps:
    if st.button("🛰️ Capture Exact GPS"):
        loc = streamlit_js_eval(data_key='pos', func_name='getCurrentPosition', want_output=True)
        if loc:
            st.session_state.gps_coord = f"Lat: {loc['coords']['latitude']}, Lon: {loc['coords']['longitude']}"
            st.success(f"Captured: {st.session_state.gps_coord}")

with col_files:
    uploaded_files = st.file_uploader("Attach Evidence (Photos/Videos):", accept_multiple_files=True)

# 5. STEP 2: USER & ISSUE DETAILS (STRICT 10-DIGIT PHONE)
st.markdown("---")
st.subheader("📝 Step 2: Reporter Details")
user_name = st.text_input("Full Name (Sender):")
user_phone = st.text_input("Contact Number (Optional):", max_chars=10, help="Must be 10 digits")
issue = st.text_area("Describe the local problem:")

# 6. STEP 3: GENERATION
if st.button("🚀 1. Generate Official Letter"):
    # Validation
    phone_valid = True if not user_phone or (user_phone.isdigit() and len(user_phone) == 10) else False
    pin_valid = True if len(user_pin) == 6 else False

    if not pin_valid:
        st.error("❌ Pincode must be 6 digits.")
    elif not phone_valid:
        st.error("❌ Phone number must be 10 digits.")
    elif not user_name or not selected_loc or not issue:
        st.error("⚠️ Missing required details.")
    else:
        with st.spinner(f"Drafting formal letter in {target_language}..."):
            contact_line = f"Contact: {user_phone}" if user_phone.strip() else ""
            gps_line = f"GPS Coordinates: {st.session_state.get('gps_coord', 'Not captured')}"
            evidence_count = len(uploaded_files) if uploaded_files else 0

            system_prompt = f"""
            Draft a formal complaint in {target_language}.
            FORMAT:
            1. TOP RIGHT: Place '{current_date}' at the very top right.
            2. RECIPIENT: 'To, The Municipal Commissioner, {selected_loc['Town']}, {selected_loc['District']}'.
            3. SENDER: {user_name}, PIN: {selected_loc['PIN']}. {contact_line}
            4. BODY: 3 paragraphs. Mention GPS: {gps_line} and {evidence_count} evidence files attached.
            5. SIGN-OFF: Sincerely, {user_name}. Supported by The Reminder India community.
            
            END WITH: 'SUGGESTED_EMAIL: ' (Likely municipal email).
            """
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": issue}]
            )
            res_content = response.choices[0].message.content
            st.session_state.letter = res_content.split("SUGGESTED_EMAIL:")[0].strip()
            st.session_state.sug_email = res_content.split("SUGGESTED_EMAIL:")[1].strip() if "SUGGESTED_EMAIL:" in res_content else ""

# 7. STEP 4: REVIEW & SEND
if "letter" in st.session_state:
    st.divider()
    st.text_area("Final Letter Preview:", value=st.session_state.letter, height=450)
    
    col_pdf, col_to, col_cc = st.columns([1, 1, 1])
    with col_pdf:
        pdf_bytes = create_pdf(st.session_state.letter)
        st.download_button("📥 Download Print PDF", data=pdf_bytes, file_name=f"TRI_Report_{user_pin}.pdf")
    with col_to:
        rec_to = st.text_input("To (Primary):", value=st.session_state.sug_email)
    with col_cc:
        rec_cc = st.text_input("CC (Optional):", placeholder="e.g. tri.desk@gmail.com")

    if st.button("📧 2. Send Official Email"):
        if rec_to:
            with st.spinner("Sending..."):
                try:
                    msg = EmailMessage()
                    msg.set_content(st.session_state.letter)
                    msg['Subject'] = f"CIVIC COMPLAINT: {selected_loc['Town']} - {user_name}"
                    msg['From'] = SENDER_EMAIL
                    msg['To'] = rec_to
                    if rec_cc: msg['Cc'] = rec_cc
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