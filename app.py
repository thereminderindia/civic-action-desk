import streamlit as st
from openai import OpenAI
import smtplib
from email.message import EmailMessage
from fpdf import FPDF
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# 1. Setup
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
APP_PASSWORD = st.secrets["APP_PASSWORD"]
current_date = datetime.now().strftime("%B %d, %Y")

# Connect to Google Sheets
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.sidebar.error("GSheets Connection Error. Check your Secrets.")

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

# PASTE YOUR LOGO URL BETWEEN THE QUOTES BELOW
logo_url = "https://www.facebook.com/photo/?fbid=122097222099239425&set=pb.61587182761969.-2207520000" 

col1, col2 = st.columns([1, 4])
with col1:
    st.image(logo_url, width=80)
with col2:
    st.title("The Reminder India")
    st.subheader("National Civic Action Desk")

# Sidebar Stats
try:
    existing_data = conn.read(ttl="1m")
    if not existing_data.empty:
        st.sidebar.metric("Total Complaints Filed", len(existing_data))
except:
    st.sidebar.info("Database initializing...")

# 4. User Inputs
user_name = st.text_input("Full Name (Sender):", placeholder="Enter your name")
pincode = st.text_input("6-Digit Pincode:", max_chars=6, placeholder="e.g. 247775")
user_phone = st.text_input("Contact Number (Optional):", placeholder="Enter your phone or leave blank")
uploaded_files = st.file_uploader("Attach Evidence:", type=["jpg", "png", "jpeg", "mp4", "mov"], accept_multiple_files=True)
issue = st.text_area("Describe the local problem:")

# 5. Smart AI Generation with Your Specific Rules
if st.button("🚀 1. Generate Official Letter"):
    if not (pincode and len(pincode) == 6) or not issue:
        st.error("Please enter a valid 6-digit Pincode and Issue.")
    else:
        with st.spinner("Drafting letter..."):
            system_prompt = f"""
            You are a Senior Civic Advocate. Draft a formal complaint based on these EXACT rules:

            SENDER SECTION:
            - Name: {user_name}
            - Pincode: {pincode}
            - City/State: Identify the City and State automatically based on Pincode {pincode}.
            - Contact: If '{user_phone}' is provided, include it. If empty, REMOVE this line.
            - NO street address. NO sender email address in the text.

            RECIPIENT SECTION:
            - Address to 'Municipal Authorities'.
            - Include Pincode {pincode} for the Municipality.

            CONTENT:
            - DATE: {current_date}
            - Subject: Professional and urgent.
            - Sign off: 'Sincerely, {user_name}'. 
            - Mention: 'Supported by The Reminder India community.'
            
            END with 'SUGGESTED_EMAIL: ' followed by the likely municipal email.
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

# 6. Review & Send
if "letter" in st.session_state:
    st.divider()
    st.text_area("Final Letter Draft:", value=st.session_state.letter, height=400)
    
    pdf_bytes = create_pdf(st.session_state.letter)
    st.download_button("📥 Download PDF", data=pdf_bytes, file_name=f"Complaint_{pincode}.pdf")

    recipient = st.text_input("Authority Email:", value=st.session_state.suggested_email)

    if st.button("📧 2. Send Email Now"):
        if recipient:
            with st.spinner("Sending and Logging..."):
                try:
                    # Email Logic
                    msg = EmailMessage()
                    msg.set_content(st.session_state.letter)
                    msg['Subject'] = f"CIVIC COMPLAINT: Pincode {pincode} - {user_name}"
                    msg['From'] = SENDER_EMAIL
                    msg['To'] = recipient
                    if uploaded_files:
                        for f in uploaded_files:
                            msg.add_attachment(f.read(), maintype='application', subtype='octet-stream', filename=f.name)
                    
                    smtp = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                    smtp.login(SENDER_EMAIL, APP_PASSWORD)
                    smtp.send_message(msg)
                    smtp.quit()

                    # Database Logging
                    new_entry = pd.DataFrame([{
                        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Name": user_name,
                        "Pincode": pincode,
                        "Issue": issue[:100],
                        "Recipient": recipient
                    }])
                    
                    # Update Google Sheet
                    all_data = pd.concat([existing_data, new_entry], ignore_index=True)
                    conn.update(data=all_data)

                    st.success("Sent & Recorded Successfully!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error: {e}")