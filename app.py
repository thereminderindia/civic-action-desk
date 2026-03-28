import streamlit as st
from openai import OpenAI
import smtplib
from email.message import EmailMessage

# 1. Setup
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
APP_PASSWORD = st.secrets["APP_PASSWORD"]

# 2. Interface
st.set_page_config(page_title="Civic Action Desk", page_icon="🏛️")
st.title("The Reminder India - National Civic Desk")

if "generated_letter" not in st.session_state:
    st.session_state.generated_letter = None

# New Input Fields for Scalability
col1, col2 = st.columns(2)
with col1:
    pincode = st.text_input("Enter Pincode:", placeholder="e.g. 110091")
with col2:
    user_name = st.text_input("Your Name:", value="A Concerned Citizen")

issue = st.text_area("Describe the local problem:", placeholder="Broken streetlights, uncleaned garbage, etc.")

# 3. Logic
if st.button("1. Generate Formal Letter"):
    if not pincode or not issue:
        st.error("Please enter both Pincode and Issue.")
    else:
        with st.spinner("Identifying authorities and drafting..."):
            # The AI now acts as a researcher to find the right office
            system_prompt = f"""
            You are a senior Indian Civic Advocate. 
            The user is reporting an issue in Pincode: {pincode}.
            
            TASKS:
            1. Determine the likely Municipal Body (e.g., MCD for Delhi, BMC for Mumbai, NPP for UP towns).
            2. Address the letter to the specific 'Executive Officer' or 'Commissioner'.
            3. Draft a formal, sharp, and urgent complaint letter.
            4. Include a line: 'CC: District Magistrate Office'.
            """
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Issue: {issue}"}
                ]
            )
            st.session_state.generated_letter = response.choices[0].message.content

# 4. Sending Section
if st.session_state.generated_letter:
    st.divider()
    st.text_area("Final Draft:", value=st.session_state.generated_letter, height=350)
    
    recipient_email = st.text_input("Enter Authority Email:", placeholder="e.g. commissioner@mcd.nic.in")
    st.caption("Tip: Search 'Official Email [Your City] Municipality' to find the address.")

    if st.button("2. Send Email Now"):
        if not recipient_email:
            st.warning("Please enter a recipient email.")
        else:
            try:
                msg = EmailMessage()
                msg.set_content(st.session_state.generated_letter)
                msg['Subject'] = f"CIVIC COMPLAINT: Pincode {pincode}"
                msg['From'] = SENDER_EMAIL
                msg['To'] = recipient_email

                server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                server.login(SENDER_EMAIL, APP_PASSWORD)
                server.send_message(msg)
                server.quit()
                st.success("Sent Successfully!")
                st.balloons()
            except Exception as e:
                st.error(f"Error: {e}")