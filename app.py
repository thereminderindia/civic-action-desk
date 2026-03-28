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
except:
    st.sidebar.error("GSheets Secret not found. Check your Settings > Secrets.")

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
# Replace with your actual YouTube Logo Link
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
    st.sidebar.metric("Total Complaints Filed", len(existing_data))
except:
    st.sidebar.info("Database connecting...")

# 4. User Inputs
user_name = st.text_input("Full Name:", placeholder="Enter your name")
pincode = st.text_input("6-Digit Pincode:", max_chars=6, placeholder="e.g. 110091")
uploaded_files = st.file_uploader("Attach Evidence:", type=["jpg", "png", "jpeg", "mp4", "mov"], accept_multiple_files=True)
issue = st.text_area("Describe the local problem:")

# 5. Smart AI Generation
if st.button("🚀 1. Generate Official Letter"):
    if not (pincode and len(pincode) == 6) or not issue:
        st.error("Please enter a valid Pincode and Issue.")
    else:
        with st.spinner("Drafting letter and identifying authority..."):
            # We tell the AI the Date and your Email to fill the placeholders
            system_prompt = f"""
            You are a Senior Civic Advocate. 
            DATE: {current_date}
            SENDER_EMAIL: {SENDER_EMAIL}
            
            TASKS:
            1. Write a formal complaint for Pincode {pincode}.
            2. Use the DATE provided above. Do not use [Insert Date].
            3. Sign off with '{user_name}' and the SENDER_EMAIL provided.
            4. At the VERY END of your response, on a new line, write 'SUGGESTED_EMAIL: ' followed by the 
               official municipal email address for this pincode (e.g., commissioner@mcd.nic.in for Delhi).
            """
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system_prompt},
                          {"role": "user", "content": f"Issue: {issue}"}]
            )
            
            full_res = response.choices[0].message.content
            
            # Extract the Suggested Email from the AI's response
            if "SUGGESTED_EMAIL:" in full_res:
                letter_text = full_res.split("SUGGESTED_EMAIL:")[0].strip()
                suggested_email = full_res.split("SUGGESTED_EMAIL:")[1].strip()
            else:
                letter_text = full_res
                suggested_email = ""

            st.session_state.letter = letter_text
            st.session_state.suggested_email = suggested_email

# 6. Review & Send
if "letter" in st.session_state:
    st.divider()
    st.text_area("Final Letter:", value=st.session_state.letter, height=350)
    
    # PDF Download
    pdf_bytes = create_pdf(st.session_state.letter)
    st.download_button("📥 Download PDF", data=pdf_bytes, file_name=f"Complaint_{pincode}.pdf")

    st.markdown("### Step 2: Send to Authority")
    
    # This box now automatically fills with the AI's suggestion
    recipient = st.text_input("Authority Email Address:", value=st.session_state.suggested_email)
    st.caption("Check [lgdirectory.gov.in](https://lgdirectory.gov.in/) to verify this email.")

    if st.button("📧 2. Send Email Now"):
        if not recipient:
            st.error("Please enter a recipient email.")
        else:
            with st.spinner("Sending..."):
                try:
                    msg = EmailMessage()
                    msg.set_content(st.session_state.letter)
                    msg['Subject'] = f"URGENT: Civic Complaint - Pincode {pincode}"
                    msg['From'] = SENDER_EMAIL
                    msg['To'] = recipient
                    
                    if uploaded_files:
                        for f in uploaded_files:
                            msg.add_attachment(f.read(), maintype='application', subtype='octet-stream', filename=f.name)

                    smtp = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                    smtp.login(SENDER_EMAIL, APP_PASSWORD)
                    smtp.send_message(msg)
                    smtp.quit()
                    
                    # Log to Google Sheets
                    new_entry = pd.DataFrame([{
                        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Name": user_name,
                        "Pincode": pincode,
                        "Issue": issue[:100],
                        "Recipient": recipient
                    }])
                    updated_df = pd.concat([existing_data, new_entry], ignore_index=True)
                    conn.update(data=updated_df)

                    st.success("Sent Successfully!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error: {e}")