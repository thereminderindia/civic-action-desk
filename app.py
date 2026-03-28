import streamlit as st
from openai import OpenAI
import smtplib
from email.message import EmailMessage
from fpdf import FPDF
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
from streamlit_js_eval import streamlit_js_eval

# 1. Setup
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
APP_PASSWORD = st.secrets["APP_PASSWORD"]
current_date = datetime.now().strftime("%B %d, %Y")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except:
    st.sidebar.error("Database connection issue.")

# 2. PDF Function
def create_pdf(text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for line in text.split('\n'):
        pdf.multi_cell(0, 10, txt=line, align='L')
    return pdf.output(dest='S').encode('latin-1')

# 3. Interface & Branding
st.set_page_config(page_title="The Reminder India", page_icon="🏛️")
# Paste your permanent logo link here
logo_url = "https://www.facebook.com/photo/?fbid=122097222099239425&set=pb.61587182761969.-2207520000" 

col1, col2 = st.columns([1, 4])
with col1:
    st.image(logo_url, width=80)
with col2:
    st.title("The Reminder India")
    st.subheader("National Civic Action Desk")

# 4. LOCATION SECTION
st.markdown("### 📍 Location Details")
loc_col1, loc_col2 = st.columns([2, 1])

with loc_col2:
    if st.button("🛰️ Use GPS"):
        location = streamlit_js_eval(data_key='pos', func_name='getCurrentPosition', want_output=True)
        if location:
            lat = location['coords']['latitude']
            lon = location['coords']['longitude']
            st.session_state.lat_lon = f"Lat: {lat}, Lon: {lon}"
            st.success("GPS Captured!")

with loc_col1:
    pincode = st.text_input("6-Digit Pincode:", value="247775", max_chars=6)

# 5. User Inputs
user_name = st.text_input("Full Name (Sender):", placeholder="Your name will appear in the letter")
user_phone = st.text_input("Contact Number (Optional):", placeholder="Must be 10 digits")
uploaded_files = st.file_uploader("Attach Evidence:", type=["jpg", "png", "jpeg", "mp4", "mov"], accept_multiple_files=True)
issue = st.text_area("Describe the local problem:")

# 6. Smart AI Generation
if st.button("🚀 1. Generate Official Letter"):
    # Phone Validation
    if user_phone and (not user_phone.isdigit() or len(user_phone) != 10):
        st.error("⚠️ Contact number must be exactly 10 digits.")
    elif not user_name or not issue:
        st.error("⚠️ Please provide your Name and describe the Issue.")
    else:
        with st.spinner("Drafting letter..."):
            location_data = st.session_state.get('lat_lon', pincode)
            
            system_prompt = f"""
            You are a Senior Civic Advocate. Draft a formal complaint letter with this EXACT structure:

            [HEADER]
            {user_name}
            Pincode: {pincode}
            {f"Contact: {user_phone}" if user_phone else ""} 

            {current_date}

            [RECIPIENT]
            To Whom It May Concern,
            Municipal Corporation,
            Kandhla, Uttar Pradesh (If Pincode is 247775)

            [SUBJECT]
            Subject: Formal Complaint Regarding {issue[:30]}...

            [BODY]
            Write a professional 3-paragraph letter. 
            - Paragraph 1: State the problem at {pincode}.
            - Paragraph 2: Explain the risks (health, safety, mosquitoes).
            - Paragraph 3: Urge immediate action.

            Sincerely,
            {user_name}
            Supported by The Reminder India community.

            STRICT RULES:
            - If contact number is missing, leave that line BLANK. Do NOT write "Not provided".
            - Put the sender name {user_name} at the top and after Sincerely.
            - Do NOT include any placeholder brackets like [City, State]. Use Kandhla, Uttar Pradesh for 247775.
            
            At the end, add 'SUGGESTED_EMAIL: ' followed by the likely municipal email.
            """
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system_prompt},
                          {"role": "user", "content": f"Issue: {issue}"}]
            )
            
            full_res = response.choices[0].message.content
            if "SUGGESTED_EMAIL:" in full_res:
                st.session_state.letter = full_res.split("SUGGESTED_EMAIL:")[0].strip()
                st.session_state.suggested_email = full_res.split("SUGGESTED_EMAIL:")[1].strip()
            else:
                st.session_state.letter = full_res
                st.session_state.suggested_email = ""

# 7. Review & Send
if "letter" in st.session_state:
    st.divider()
    st.text_area("Final Letter Draft:", value=st.session_state.letter, height=450)
    pdf_bytes = create_pdf(st.session_state.letter)
    st.download_button("📥 Download PDF", data=pdf_bytes, file_name=f"Complaint_{pincode}.pdf")

    recipient = st.text_input("Authority Email:", value=st.session_state.suggested_email)

    if st.button("📧 2. Send Email Now"):
        if recipient:
            with st.spinner("Sending..."):
                try:
                    msg = EmailMessage()
                    msg.set_content(st.session_state.letter)
                    msg['Subject'] = f"CIVIC COMPLAINT: {pincode} - {user_name}"
                    msg['From'] = SENDER_EMAIL
                    msg['To'] = recipient
                    if uploaded_files:
                        for f in uploaded_files:
                            msg.add_attachment(f.read(), maintype='application', subtype='octet-stream', filename=f.name)
                    
                    smtp = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                    smtp.login(SENDER_EMAIL, APP_PASSWORD)
                    smtp.send_message(msg)
                    smtp.quit()
                    
                    # Log to GSheets
                    new_entry = pd.DataFrame([{"Timestamp": datetime.now(), "Name": user_name, "Pincode": pincode, "Issue": issue[:100], "Recipient": recipient}])
                    try:
                        existing = conn.read()
                        updated = pd.concat([existing, new_entry], ignore_index=True)
                        conn.update(data=updated)
                    except:
                        conn.create(data=new_entry)

                    st.success("Sent & Recorded!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error: {e}")