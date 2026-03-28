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
    return pdf.output(dest='S').encode('latin-1', 'ignore')

# 3. Interface & Branding
st.set_page_config(page_title="The Reminder India", page_icon="🏛️")
logo_url = "https://scontent.fbek1-1.fna.fbcdn.net/v/t39.30808-6/622269601_1826245688085334_2578928589940005936_n.jpg?_nc_cat=105&ccb=1-7&_nc_sid=2a1932&_nc_ohc=wmBzMONziXEQ7kNvwH6AUeO&_nc_oc=AdqeW4G6uqRckWCQ80jKbeZPsVHWo9tuDh2Mq5UEsJMqrQ00SJILnWidT7XQgVBs80Xnd-AKiVKZzNCJgEqL0d41&_nc_zt=23&_nc_ht=scontent.fbek1-1.fna&_nc_gid=tZbtmbxF6DqH6Zoa2KT_xA&_nc_ss=7a32e&oh=00_AfwuRHj1dp4Zh6MqWK4-54tm1J6YT3CB-T3tFb1gKeRkmw&oe=69CE0649" 

col1, col2 = st.columns([1, 4])
with col1:
    st.image(logo_url, width=80)
with col2:
    st.title("The Reminder India")
    st.subheader("National Civic Action Desk")

# 4. SETTINGS SECTION
st.markdown("---")
lang_col, loc_col = st.columns(2)

with lang_col:
    target_language = st.selectbox("Choose Language for Letter:", 
        ["English", "Hindi (हिन्दी)", "Punjabi (ਪੰਜਾਬੀ)", "Bengali (বাংলা)", 
         "Marathi (मराठी)", "Tamil (தமிழ்)", "Telugu (తెలుగు)", 
         "Spanish (Español)", "French (Français)"])

with loc_col:
    pincode = st.text_input("6-Digit Pincode:", value="247775", max_chars=6)

# GPS Button
if st.button("🛰️ Capture Current Location via GPS"):
    location = streamlit_js_eval(data_key='pos', func_name='getCurrentPosition', want_output=True)
    if location:
        st.session_state.lat_lon = f"Lat: {location['coords']['latitude']}, Lon: {location['coords']['longitude']}"
        st.success("GPS Captured!")

# 5. User Inputs
user_name = st.text_input("Full Name (Sender):")
user_phone = st.text_input("Contact Number (Optional):")
uploaded_files = st.file_uploader("Attach Evidence:", accept_multiple_files=True)
issue = st.text_area("Describe the local problem (Type in your mother tongue):")

# 6. Smart Multi-Language Generation & Translation
if st.button("🚀 1. Generate Official Letter"):
    if user_phone and (not user_phone.isdigit() or len(user_phone) != 10):
        st.error("⚠️ Contact number must be exactly 10 digits.")
    elif not user_name or not issue:
        st.error("⚠️ Please provide your Name and describe the Issue.")
    else:
        with st.spinner(f"Processing in {target_language}..."):
            # SYSTEM PROMPT: Now requests two outputs
            system_prompt = f"""
            You are a Senior Civic Advocate. 
            
            TASK 1: Draft a formal complaint letter in {target_language}.
            - SENDER: {user_name}, Pincode: {pincode}
            - {f"CONTACT: {user_phone}" if user_phone else ""}
            - DATE: {current_date}
            - RECIPIENT: Municipal Authorities, Kandhla, UP (if 247775).
            - BODY: Urgent 3-paragraph letter regarding the issue.
            - SIGN-OFF: Sincerely, {user_name}. Supported by The Reminder India.

            TASK 2: Provide a 1-sentence English translation of the user's issue description.
            
            FORMAT:
            [LETTER_START]
            (Write the full letter here)
            [LETTER_END]
            [ENGLISH_SUMMARY]: (Write the English translation here)
            [SUGGESTED_EMAIL]: (Write the official email here)
            """
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system_prompt},
                          {"role": "user", "content": f"Issue: {issue}"}]
            )
            
            full_res = response.choices[0].message.content
            
            # Parsing the Multi-part response
            try:
                st.session_state.letter = full_res.split("[LETTER_START]")[1].split("[LETTER_END]")[0].strip()
                st.session_state.eng_summary = full_res.split("[ENGLISH_SUMMARY]:")[1].split("[SUGGESTED_EMAIL]:")[0].strip()
                st.session_state.suggested_email = full_res.split("[SUGGESTED_EMAIL]:")[1].strip()
            except:
                st.session_state.letter = full_res
                st.session_state.eng_summary = "Translation failed."
                st.session_state.suggested_email = ""

# 7. Review & Send
if "letter" in st.session_state:
    st.divider()
    st.subheader(f"Generated Letter ({target_language})")
    st.text_area("Final Draft:", value=st.session_state.letter, height=400)
    
    if target_language != "English":
        st.info(f"📋 **Admin Translation for Database:** {st.session_state.eng_summary}")

    recipient = st.text_input("Authority Email:", value=st.session_state.suggested_email)

    if st.button("📧 2. Send Email Now"):
        if recipient:
            with st.spinner("Sending and Logging..."):
                try:
                    # Email Logic
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
                    
                    # Log to GSheets (Using English Summary for your records!)
                    new_entry = pd.DataFrame([{
                        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Name": user_name,
                        "Pincode": pincode,
                        "Issue_Original": issue[:50],
                        "Issue_English": st.session_state.eng_summary,
                        "Recipient": recipient
                    }])
                    
                    try:
                        existing = conn.read()
                        updated = pd.concat([existing, new_entry], ignore_index=True)
                        conn.update(data=updated)
                    except:
                        conn.create(data=new_entry)

                    st.success(f"Sent successfully! Issue logged in English for TRI records.")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error: {e}")