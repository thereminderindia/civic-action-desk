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

# Connect to Google Sheets
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except:
    st.sidebar.error("Database connection issue. Check Secrets.")

# 2. HELPER FUNCTIONS
def get_pincode_details(pin):
    """Fetches official Area/District/State from India Post API"""
    try:
        response = requests.get(f"https://api.postalpincode.in/pincode/{pin}", timeout=5)
        data = response.json()
        if data[0]['Status'] == 'Success':
            post_office = data[0]['PostOffice'][0]
            return {
                "Area": post_office['Name'],
                "District": post_office['District'],
                "State": post_office['State']
            }
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

# 3. INTERFACE & SIDEBAR TOOLS
st.set_page_config(page_title="The Reminder India", page_icon="🏛️", layout="centered")

st.sidebar.title("🛠️ Verification Tools")
st.sidebar.link_button("🔍 Find Official Pincode", "https://www.indiapost.gov.in/VAS/Pages/findpincode.aspx")
st.sidebar.markdown("---")

# Stats Sidebar
try:
    existing_data = conn.read(ttl="1m")
    if not existing_data.empty:
        st.sidebar.metric("Total Complaints Filed", len(existing_data))
except:
    st.sidebar.info("Initializing database...")

# Branding Header
logo_url = "https://www.facebook.com/photo.php?fbid=122097222099239425&set=pb.61587182761969.-2207520000&type=3" 
col1, col2 = st.columns([1, 4])
with col1:
    st.image(logo_url, width=80)
with col2:
    st.title("The Reminder India")
    st.subheader("National Civic Action Desk")

# 4. SETTINGS & LOCATION
st.markdown("---")
lang_col, loc_col = st.columns(2)

with lang_col:
    target_language = st.selectbox("Select Language:", 
        ["English", "Hindi (हिन्दी)", "Punjabi (ਪੰਜਾਬੀ)", "Bengali (বাংলা)", 
         "Marathi (मराठी)", "Tamil (தமிழ்)", "Telugu (తెలుగు)", 
         "Spanish (Español)", "French (Français)"])

with loc_col:
    pincode = st.text_input("6-Digit Pincode:", value="", max_chars=6, placeholder="e.g. 247775")

# GPS Option
if st.button("🛰️ Use Current GPS Location"):
    location = streamlit_js_eval(data_key='pos', func_name='getCurrentPosition', want_output=True)
    if location:
        st.session_state.lat_lon = f"Lat: {location['coords']['latitude']}, Lon: {location['coords']['longitude']}"
        st.success("GPS Captured!")

# 5. USER INPUTS
user_name = st.text_input("Full Name (Sender):")
user_phone = st.text_input("Contact Number (Optional):", placeholder="10 Digits")
uploaded_files = st.file_uploader("Attach Photos/Videos (Evidence):", accept_multiple_files=True)
issue = st.text_area("Describe the local problem:")

# 6. GENERATION LOGIC
if st.button("🚀 1. Generate Official Letter"):
    # VALIDATION
    official_loc = get_pincode_details(pincode) if pincode else None
    
    if user_phone and (len(user_phone) != 10 or not user_phone.isdigit()):
        st.error("⚠️ Contact number must be exactly 10 digits.")
    elif not user_name or not (pincode or st.session_state.get('lat_lon')) or not issue:
        st.error("⚠️ Please fill in all required fields.")
    elif pincode and not official_loc:
        st.error("⚠️ Pincode not found in India Post records. Please verify.")
    else:
        with st.spinner(f"Verifying location and drafting in {target_language}..."):
            # Get Factual Location
            loc_str = f"{official_loc['Area']}, {official_loc['District']}, {official_loc['State']}" if official_loc else "GPS Detected Area"
            
            system_prompt = f"""
            You are a Senior Civic Advocate. 
            TASK: Draft a formal complaint in {target_language}.
            
            FACTUAL DATA:
            - Date: {current_date}
            - Sender: {user_name}
            - Verified Location: {loc_str} (Pincode: {pincode})
            - Contact: {user_phone if user_phone else ""}
            
            STRUCTURE:
            1. Header: Name, Pincode, Contact (Only if provided).
            2. Recipient: Municipal Commissioner of {official_loc['District'] if official_loc else 'the local area'}.
            3. Subject: Formal Complaint regarding {issue[:30]}...
            4. Body: 3 paragraphs (Issue, Risks, Call to Action).
            5. Sign-off: Sincerely, {user_name}. Supported by The Reminder India.
            
            TASK 2: Translation for Admin.
            FORMAT:
            [LETTER_START]
            (Content)
            [LETTER_END]
            [ENGLISH_SUMMARY]: (1-sentence summary)
            [SUGGESTED_EMAIL]: (Likely municipal email)
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
                st.session_state.eng_summary = "Translation provided."
                st.session_state.suggested_email = ""

# 7. REVIEW, SEND & SHARE
if "letter" in st.session_state:
    st.divider()
    st.subheader(f"Generated Letter ({target_language})")
    st.text_area("Final Draft:", value=st.session_state.letter, height=400)
    
    # PDF
    pdf_bytes = create_pdf(st.session_state.letter)
    st.download_button("📥 Download PDF", data=pdf_bytes, file_name=f"Complaint_{pincode}.pdf")

    st.markdown("---")
    recipient = st.text_input("Authority Email(s):", value=st.session_state.suggested_email, placeholder="e.g. dm@gov.in, eo@gov.in")
    st.caption("💡 Separate multiple emails with a comma.")

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
                    
                    # Log to Sheets
                    new_entry = pd.DataFrame([{"Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "Name": user_name, "Pincode": pincode, "Issue_English": st.session_state.eng_summary, "Recipient": recipient}])
                    all_data = pd.concat([existing_data, new_entry], ignore_index=True)
                    conn.update(data=all_data)

                    st.success("Sent & Recorded!")
                    st.balloons()
                    
                    wa_text = f"I just reported a civic issue in {pincode} via TRI! Check: https://your-link.streamlit.app"
                    st.link_button("📢 Share on WhatsApp", f"https://wa.me/?text={urllib.parse.quote(wa_text)}")
                except Exception as e:
                    st.error(f"Error: {e}")