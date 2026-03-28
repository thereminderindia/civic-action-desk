import streamlit as st
from openai import OpenAI
import smtplib
from email.message import EmailMessage
from fpdf import FPDF
import pandas as pd
from datetime import datetime
import os

# 1. Setup
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
APP_PASSWORD = st.secrets["APP_PASSWORD"]

# File to store history locally on the server
HISTORY_FILE = "complaint_history.csv"

# 2. Helper Functions
def save_to_history(name, pincode, issue, recipient):
    new_data = {
        "Timestamp": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        "Name": [name],
        "Pincode": [pincode],
        "Issue": [issue[:50] + "..."], # Store a summary
        "Recipient": [recipient]
    }
    df = pd.DataFrame(new_data)
    if not os.path.isfile(HISTORY_FILE):
        df.to_csv(HISTORY_FILE, index=False)
    else:
        df.to_csv(HISTORY_FILE, mode='a', header=False, index=False)

def create_pdf(text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for line in text.split('\n'):
        pdf.multi_cell(0, 10, txt=line, align='L')
    return pdf.output(dest='S').encode('latin-1')

# 3. Interface
st.set_page_config(page_title="Civic Action Desk", page_icon="🏛️")
st.title("National Civic Action Desk")
st.caption("Official Tool | The Reminder India")

if "generated_letter" not in st.session_state:
    st.session_state.generated_letter = None

# Sidebar for Impact Stats
if os.path.isfile(HISTORY_FILE):
    history_df = pd.read_csv(HISTORY_FILE)
    st.sidebar.metric("Total Complaints Filed", len(history_df))
    st.sidebar.subheader("Recent Activity")
    st.sidebar.dataframe(history_df.tail(5), hide_index=True)

# Main Inputs
user_name = st.text_input("Full Name:")
pincode = st.text_input("6-Digit Pincode:", max_chars=6)
uploaded_files = st.file_uploader("Upload Photos/Videos:", accept_multiple_files=True)
issue = st.text_area("Describe the issue:")

# 4. Action Logic
if st.button("🚀 1. Generate Letter"):
    if pincode and issue:
        with st.spinner("Drafting..."):
            system_prompt = f"Draft a formal Indian civic complaint for Pincode {pincode}. End with 'Supported by The Reminder India'."
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system_prompt},
                          {"role": "user", "content": f"Issue: {issue}\nName: {user_name}"}]
            )
            st.session_state.generated_letter = response.choices[0].message.content

if st.session_state.generated_letter:
    st.divider()
    st.text_area("Review Draft:", value=st.session_state.generated_letter, height=250)
    
    # PDF Download
    pdf_data = create_pdf(st.session_state.generated_letter)
    st.download_button("📥 Download PDF", data=pdf_data, file_name=f"Complaint_{pincode}.pdf")

    recipient_email = st.text_input("Recipient Email:", placeholder="Enter authority email")

    if st.button("📧 2. Send Email Now"):
        if recipient_email:
            with st.spinner("Sending and Logging..."):
                try:
                    # EMAIL LOGIC
                    msg = EmailMessage()
                    msg.set_content(st.session_state.generated_letter)
                    msg['Subject'] = f"CIVIC COMPLAINT: Pincode {pincode}"
                    msg['From'] = SENDER_EMAIL
                    msg['To'] = recipient_email
                    if uploaded_files:
                        for f in uploaded_files:
                            msg.add_attachment(f.read(), maintype='application', subtype='octet-stream', filename=f.name)
                    
                    server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                    server.login(SENDER_EMAIL, APP_PASSWORD)
                    server.send_message(msg)
                    server.quit()

                    # LOGGING LOGIC
                    save_to_history(user_name, pincode, issue, recipient_email)
                    
                    st.success("Sent & Logged in History!")
                    st.balloons()
                    st.rerun() # Refresh to update the sidebar count
                except Exception as e:
                    st.error(f"Error: {e}")