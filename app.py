import streamlit as st
import requests
from openai import OpenAI
import smtplib
from email.message import EmailMessage
from fpdf import FPDF
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
from streamlit_js_eval import streamlit_js_eval
import urllib.parse

# 1. AUTHENTICATION & SETUP
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
APP_PASSWORD = st.secrets["APP_PASSWORD"]
current_date = datetime.now().strftime("%B %d, %Y")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except:
    st.sidebar.error("Database connection issue.")

# 2. HELPER FUNCTIONS
def get_official_post_office_data(pin):
    try:
        response = requests.get(f"https://api.postalpincode.in/pincode/{pin}", timeout=5)
        data = response.json()
        if data[0]['Status'] == 'Success' and data[0]['PostOffice']:
            office = data[0]['PostOffice'][0]
            return {"Area": office['Name'], "District": office['District'], "State": office['State']}
    except:
        return None
    return None

def create_pdf(text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for line in text.split('\n'):
        pdf.multi_cell(0, 10, txt=line, align='L')
    return pdf.output(dest='S').encode('latin-1', 'ignore')

# 3. INTERFACE & SOCIAL MEDIA SIDEBAR
st.set_page_config(page_title="The Reminder India", page_icon="🏛️", layout="wide")

# --- SIDEBAR START ---
st.sidebar.title("📲 Connect with TRI")
st.sidebar.info("Support our mission by following our official channels:")

# Social Media Links (Replace '#' with your actual URLs)
st.sidebar.link_button("📺 YouTube: The Reminder India", "https://youtube.com/@TheReminderIndia")
st.sidebar.link_button("🔵 Facebook: The Reminder India", "https://facebook.com/TheReminderIndia")
st.sidebar.link_button("📸 Instagram: @TheReminderIndia", "https://instagram.com/TheReminderIndia")

st.sidebar.markdown("---")
st.sidebar.title("🛠️ Tools")
st.sidebar.link_button("🔍 Official Pincode Search", "https://www.indiapost.gov.in/VAS/Pages/findpincode.aspx")
# --- SIDEBAR END ---

# Branding Header
logo_url = "https://www.facebook.com/photo/?fbid=122097222099239425&set=pb.61587182761969.-2207520000" 
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.image(logo_url, width=90)
with col_title:
    st.title("The Reminder India")
    st.subheader("National Civic Action Desk")

# 4. SETTINGS & LOCATION
st.markdown("---")
lang_col, loc_input_col, gps_col = st.columns([2, 2, 1])

with lang_col:
    target_language = st.selectbox("Select Letter Language:", 
        ["English", "Hindi (हिन्दी)", "Bengali (বাংলা)", "Marathi (मराठी)", 
         "Telugu (తెలుగు)", "Tamil (தமிழ்)", "Gujarati (ગુજરાતી)", 
         "Urdu (اردו)", "Kannada (ಕನ್ನಡ)", "Odia (ଓଡ଼ିଆ)", 
         "Malayalam (മലയാളം)", "Punjabi (ਪੰਜਾਬੀ)", "Assamese (অসমীয়া)", 
         "Maithili (मैथिली)", "Santali (संताली)", "Kashmiri (کٲشُر)", 
         "Nepali (नेपाली)", "Konkani (कोंकणी)", "Sindhi (سنڌي)", 
         "Dogri (डोगरी)", "Manipuri (মৈতৈলোন)", "Bodo (बर')",
         "Sanskrit (संस्कृतम्)", "Spanish (Español)", "French (Français)"])

with loc_input_col:
    pincode = st.text_input("6-Digit Pincode:", value="", max_chars=6, placeholder="e.g. 247775")

with gps_col:
    st.write("OR")
    if st.button("🛰️ Use GPS"):
        location = streamlit_js_eval(data_key='pos', func_name='getCurrentPosition', want_output=True)
        if location:
            st.session_state.gps_data = f"Lat: {location['coords']['latitude']}, Lon: {location['coords']['longitude']}"
            st.success("GPS Captured!")

# 5. USER INPUTS
user_name = st.text_input("Full Name (Sender):")
user_phone = st.text_input("Contact Number (Optional):")
uploaded_files = st.file_uploader("Attach Evidence (Photos/Videos):", accept_multiple_files=True)
issue = st.text_area("Describe the local problem:")

# 6. GENERATION LOGIC
if st.button("🚀 1. Generate Official Letter"):
    official_data = get_official_post_office_data(pincode) if pincode else None
    gps_data = st.session_state.get('gps_data')

    if not user_name or not issue:
        st.error("⚠️ Name and Issue are required.")
    elif pincode and not official_data:
        st.error(f"❌ Pincode {pincode} not found. Please verify.")
    elif not pincode and not gps_data:
        st.error("⚠️ Please provide a Pincode or use GPS.")
    else:
        with st.spinner("Drafting..."):
            if official_data:
                loc_str = f"Area: {official_data['Area']}, District: {official_data['District']}, State: {official_data['State']}"
                recipient_body = f"The Municipal Commissioner / Executive Officer, {official_data['Area']} Municipality, {official_data['District']}, {official_data['State']}"
            else:
                loc_str = f"GPS Coordinates: {gps_data}"
                recipient_body = "The Municipal Commissioner of the local jurisdiction"

            contact_line = f"Contact: {user_phone}" if user_phone.strip() else ""

            system_prompt = f"""
            You are a Senior Civic Advocate. Draft a formal complaint in {target_language}.
            
            SENDER: {user_name}, Pincode: {pincode if pincode else 'GPS'}
            {contact_line}
            LOCATION: {loc_str}

            STRICT FORMAT:
            1. Start recipient with 'To,'.
            2. RECIPIENT: {recipient_body}.
            3. No guesses. No Nainital. No placeholders.
            4. SIGN-OFF: Sincerely, {user_name}. Supported by The Reminder India community.
            
            FORMAT:
            [LETTER_START]
            (Letter content)
            [LETTER_END]
            [ENGLISH_SUMMARY]: (Summary)
            [SUGGESTED_EMAIL]: (Official email)
            """
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": issue}]
            )
            
            full_res = response.choices[0].message.content
            try:
                st.session_state.letter = full_res.split("[LETTER_START]")[1].split("[LETTER_END]")[0].strip()
                st.session_state.eng_summary = full_res.split("[ENGLISH_SUMMARY]:")[1].split("[SUGGESTED_EMAIL]:")[0].strip()
                st.session_state.suggested_email = full_res.split("[SUGGESTED_EMAIL]:")[1].strip()
            except:
                st.session_state.letter = full_res
                st.session_state.eng_summary = "Processed."
                st.session_state.suggested_email = ""

# 7. REVIEW & SEND
if "letter" in st.session_state:
    st.divider()
    st.text_area("Review Official Draft:", value=st.session_state.letter, height=400)
    
    recipient = st.text_input("Authority Email(s):", value=st.session_state.suggested_email)

    if st.button("📧 2. Send Email Now"):
        if recipient:
            with st.spinner("Sending..."):
                try:
                    email_list = [e.strip() for e in recipient.split(",")]
                    msg = EmailMessage()
                    msg.set_content(st.session_state.letter)
                    msg['Subject'] = f"CIVIC COMPLAINT: {pincode} - {user_name}"
                    msg['From'] = SENDER_EMAIL
                    msg['To'] = ", ".join(email_list)
                    
                    if uploaded_files:
                        for f in uploaded_files:
                            msg.add_attachment(f.read(), maintype='application', subtype='octet-stream', filename=f.name)
                    
                    smtp = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                    smtp.login(SENDER_EMAIL, APP_PASSWORD)
                    smtp.send_message(msg)
                    smtp.quit()
                    
                    # Log to GSheets
                    new_entry = pd.DataFrame([{"Timestamp": datetime.now(), "Name": user_name, "Pincode": pincode, "Issue_English": st.session_state.eng_summary, "Recipient": recipient}])
                    all_data = pd.concat([conn.read(), new_entry], ignore_index=True)
                    conn.update(data=all_data)

                    st.success("Sent & Recorded!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error: {e}")