import streamlit as st
from openai import OpenAI
import smtplib
from email.message import EmailMessage

# Instead of typing passwords here, we tell the app to look in a secret vault
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"]) 
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
APP_PASSWORD = st.secrets["APP_PASSWORD"]

# The "Database" mapping locations to official emails
official_directory = {
    "Kandhla": ["papa95491@gmail.com"], # Replace with real emails later
    "Shamli": ["farhad.khan34@gmail.com"],
    "Default": ["papa95491@gmail.com"]
}

# ==========================================
# 2. APP INTERFACE & MEMORY
# ==========================================
st.set_page_config(page_title="Civic Action Desk", page_icon="📝")
st.title("The Reminder India - Civic Action Desk")

# This tells the app to "remember" the letter after it generates it
if "generated_letter" not in st.session_state:
    st.session_state.generated_letter = None

issue = st.text_area("Describe the problem:", value="The main drain has been overflowing for three weeks and the garbage is uncleaned, creating a health hazard.")
location = st.text_input("Location / Ward:", value="Main Market, Kandhla")
user_name = st.text_input("Your Name / Organization:", value="The Reminder India Team")

# ==========================================
# 3. GENERATE BUTTON LOGIC
# ==========================================
if st.button("1. Generate Official Letter"):
    if not issue or not location:
        st.error("Please fill in both the issue and location.")
    else:
        with st.spinner("Drafting your letter..."):
            system_prompt = """
            You are an expert civic advocate in India. The user will provide a rough description of a local issue. 
            Draft a formal, polite, authoritative complaint letter addressed to the Executive Officer (EO) of the local municipality. 
            Keep it concise, urgent, and ready to print or email.
            """
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Name: {user_name}\nLocation: {location}\nIssue: {issue}"}
                ],
                temperature=0.7
            )
            
            # Save the generated letter to the app's memory
            st.session_state.generated_letter = response.choices[0].message.content

# ==========================================
# 4. DISPLAY AND SEND LOGIC
# ==========================================
# If a letter exists in memory, show it on the screen and show the Send button
if st.session_state.generated_letter:
    st.success("Letter Generated Successfully!")
    st.text_area("Your Official Complaint:", value=st.session_state.generated_letter, height=300)
    
    st.divider()
    st.subheader("Send to Authorities")
    
    # Look up the emails for the typed location
    recipients = official_directory.get(location, official_directory["Default"])
    st.info(f"**Target Officials for {location}:** {', '.join(recipients)}")
    
    if st.button("2. Send Email Now"):
        with st.spinner("Connecting to email server..."):
            try:
                msg = EmailMessage()
                msg.set_content(st.session_state.generated_letter)
                msg['Subject'] = f"URGENT: Infrastructure & Health Hazard Report - {location}"
                msg['From'] = SENDER_EMAIL
                msg['To'] = ", ".join(recipients)

                # Connect to Gmail and send
                server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                server.login(SENDER_EMAIL, APP_PASSWORD)
                server.send_message(msg)
                server.quit()
                
                st.success(f"✅ Official complaint successfully sent to: {msg['To']}")
                st.balloons() # Adds a little celebration animation!
                
            except Exception as e:
                st.error("Error sending email. Did you add your real Gmail App Password?")