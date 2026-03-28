import streamlit as st
from openai import OpenAI
import smtplib
from email.message import EmailMessage
import re

# 1. Setup from Streamlit Secrets
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
APP_PASSWORD = st.secrets["APP_PASSWORD"]

# 2. Top 10 Cities Directory
city_directory = {
    "Select a City (Optional)": "",
    "Delhi (MCD)": "commissioner@mcd.nic.in",
    "Mumbai (BMC)": "mc@mcgm.gov.in",
    "Bangalore (BBMP)": "comm@bbmp.gov.in",
    "Chennai (GCC)": "commissioner@chennaicorporation.gov.in",
    "Hyderabad (GHMC)": "commissioner@ghmc.gov.in",
    "Kolkata (KMC)": "mc@kmcgov.in",
    "Pune (PMC)": "commissioner@punecorporation.gov.in",
    "Ahmedabad (AMC)": "commissioner@ahmedabadcity.gov.in",
    "Lucknow (LMC)": "nnlko@nic.in",
    "Jaipur (JMC)": "commissioner.jmc@rajasthan.gov.in",
    "Kandhla (NPP)": "info@nppkandhla.co.in"
}

# 3. Interface Design
st.set_page_config(page_title="Civic Action Desk", page_icon="🏛️", layout="centered")

# Branding for The Reminder India
st.image("https://via.placeholder.com/150x50?text=THE+REMINDER+INDIA", width=200) # Optional: Add your logo URL here
st.title("National Civic Action Desk")
st.markdown("---")

if "generated_letter" not in st.session_state:
    st.session_state.generated_letter = None

# Input Fields
user_name = st.text_input("Full Name:", placeholder="Enter your name")
pincode = st.text_input("Enter 6-Digit Pincode:", max_chars=6, placeholder="e.g. 110091")

# Pincode Validation
if pincode and (not pincode.isdigit() or len(pincode) != 6):
    st.warning("⚠️ Please enter a valid 6-digit Pincode.")

issue = st.text_area("Describe the local problem in detail:", 
                    placeholder="Example: The streetlights in Ward 4 are broken for 2 weeks, making it unsafe at night.")

# 4. AI Generation Logic
if st.button("🚀 1. Generate Official Letter"):
    if not (pincode and len(pincode) == 6) or not issue:
        st.error("Please provide a valid 6-digit Pincode and describe the issue.")
    else:
        with st.spinner("Analyzing location and drafting..."):
            # The AI identifies the authority based on the Pincode
            system_prompt = f"""
            You are a Senior Civic Advocate. The user is reporting an issue at Pincode: {pincode}.
            
            1. Identify the likely Municipal Body for this Pincode (e.g. MCD for Delhi, BMC for Mumbai).
            2. Address the letter to the specific authority (e.g. 'The Zonal Commissioner' or 'The Executive Officer').
            3. Draft a formal, authoritative, and urgent complaint letter.
            4. Add a closing line: 'This issue is being monitored by The Reminder India community.'
            """
            
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Issue: {issue}\nReported by: {user_name}"}
                    ]
                )
                st.session_state.generated_letter = response.choices[0].message.content
            except Exception as e:
                st.error("AI connection failed. Check your API key.")

# 5. Review and Send
if st.session_state.generated_letter:
    st.success("✅ Letter drafted successfully!")
    st.text_area("Review your letter:", value=st.session_state.generated_letter, height=350)
    
    st.markdown("### Step 2: Choose Recipient")
    selected_city = st.selectbox("Quick Select Major City:", list(city_directory.keys()))
    
    # Logic: Use city email if selected, otherwise let user type
    default_email = city_directory[selected_city]
    recipient_email = st.text_input("Recipient Email (Verify this for your local area):", value=default_email)

    if st.button("📧 2. Send Official Email Now"):
        if not recipient_email:
            st.error("Please enter a recipient email address.")
        else:
            with st.spinner("Sending..."):
                try:
                    msg = EmailMessage()
                    msg.set_content(st.session_state.generated_letter)
                    msg['Subject'] = f"URGENT CIVIC COMPLAINT: {pincode} - Reported by {user_name}"
                    msg['From'] = SENDER_EMAIL
                    msg['To'] = recipient_email

                    server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                    server.login(SENDER_EMAIL, APP_PASSWORD)
                    server.send_message(msg)
                    server.quit()
                    
                    st.success(f"Sent successfully to {recipient_email}!")
                    st.balloons()
                except Exception as e:
                    st.error("Failed to send. Check your App Password settings.")