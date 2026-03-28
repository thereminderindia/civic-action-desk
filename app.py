import streamlit as st
import requests
from openai import OpenAI
import smtplib
from email.message import EmailMessage
from fpdf import FPDF
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import urllib.parse

# 1. AUTHENTICATION & SETUP
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
APP_PASSWORD = st.secrets["APP_PASSWORD"]
current_date = datetime.now().strftime("%B %d, %Y")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except:
    st.sidebar.error("GSheets connection error.")

# 2. THE VALIDATION GATEWAY
def get_official_post_office_data(pin):
    """Fetches real-time data from India Post. No AI guessing allowed here."""
    try:
        # We hit the official public records API
        response = requests.get(f"https://api.postalpincode.in/pincode/{pin}", timeout=5)
        data = response.json()
        
        if data[0]['Status'] == 'Success' and data[0]['PostOffice']:
            # We take the first reliable record from the official list
            office = data[0]['PostOffice'][0]
            return {
                "Area": office['Name'],
                "District": office['District'],
                "State": office['State']
            }
    except Exception as e:
        return {"error": "Connection to India Post failed. Try again in a moment."}
    return None

def create_pdf(text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for line in text.split('\n'):
        pdf.multi_cell(0, 10, txt=line, align='L')
    return pdf.output(dest='S').encode('latin-1', 'ignore')

# 3. INTERFACE
st.set_page_config(page_title="The Reminder India", page_icon="🏛️")
logo_url = "https://www.facebook.com/photo.php?fbid=122097222099239425&set=pb.61587182761969.-2207520000&type=3" 

col1, col2 = st.columns([1, 4])
with col1:
    st.image(logo_url, width=80)
with col2:
    st.title("The Reminder India")
    st.subheader("National Civic Action Desk")

# 4. INPUTS
st.markdown("---")
lang_col, loc_col = st.columns(2)
with lang_col:
    target_language = st.selectbox("Letter Language:", ["English", "Hindi (हिन्दी)", "Punjabi (ਪੰਜਾਬੀ)", "Bengali (বাংলা)", "Marathi (मराठी)", "Tamil (தமிழ்)", "Telugu (తెలుగు)"])
with loc_col:
    pincode = st.text_input("Enter 6-Digit Pincode:", value="", max_chars=6, placeholder="e.g. 247775")

user_name = st.text_input("Full Name (Sender):")
user_phone = st.text_input("Contact Number (Optional):", placeholder="10 digits")
issue = st.text_area("Describe the local problem:")

# 5. GENERATION LOGIC WITH DATA LOCK
if st.button("🚀 1. Generate Official Letter"):
    # STEP 1: Fetch Official Data (The Gatekeeper)
    official_data = get_official_post_office_data(pincode)

    if not pincode or len(pincode) != 6:
        st.error("⚠️ Please enter a valid 6-digit Pincode.")
    elif not official_data:
        st.error(f"❌ Pincode {pincode} not found in India Post Records. Please check and try again.")
    elif "error" in official_data:
        st.error(official_data["error"])
    elif not user_name or not issue:
        st.error("⚠️ Please provide your Name and Issue description.")
    else:
        # STEP 2: Pass ONLY official data to the AI
        with st.spinner(f"Official Record Found: {official_data['Area']}. Drafting letter..."):
            
            # Format the Sender Contact line
            contact_info = f"Contact: {user_phone}" if user_phone.strip() else ""
            
            # This prompt locks the AI into the official data
            system_prompt = f"""
            You are a Senior Civic Advocate. 
            
            STRICT LOCATION DATA (Provided by India Post):
            Area: {official_data['Area']}
            District: {official_data['District']}
            State: {official_data['State']}
            Pincode: {pincode}

            TASK: Draft a formal complaint in {target_language}.
            
            STRUCTURE:
            1. HEADER: {user_name}, Pincode: {pincode}. {contact_info}
            2. DATE: {current_date}
            3. RECIPIENT: 
               To,
               The Municipal Commissioner / Executive Officer,
               {official_data['Area']} Municipality,
               District: {official_data['District']}, {official_data['State']}.
            
            4. SUBJECT: Formal Complaint regarding {issue[:30]}...
            5. SIGN-OFF: Sincerely, {user_name}. Supported by The Reminder India community.

            STRICT RULES:
            - Start the recipient section with 'To,'.
            - Use ONLY the Location Data provided above. Do NOT suggest Nainital or any other city.
            - If contact info is missing, leave that line completely blank.
            - Entire body must be in {target_language}.
            
            At the end, add 'SUGGESTED_EMAIL: ' followed by the likely official email for {official_data['District']}.
            """
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": issue}]
            )
            
            full_res = response.choices[0].message.content
            try:
                st.session_state.letter = full_res.split("SUGGESTED_EMAIL:")[0].strip()
                st.session_state.suggested_email = full_res.split("SUGGESTED_EMAIL:")[1].strip()
            except:
                st.session_state.letter = full_res
                st.session_state.suggested_email = ""

# 6. REVIEW & SEND
if "letter" in st.session_state:
    st.divider()
    st.text_area("Review Official Draft:", value=st.session_state.letter, height=400)
    
    # PDF Download
    pdf_bytes = create_pdf(st.session_state.letter)
    st.download_button("📥 Download PDF", data=pdf_bytes, file_name=f"Complaint_{pincode}.pdf")

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
                    
                    smtp = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                    smtp.login(SENDER_EMAIL, APP_PASSWORD)
                    smtp.send_message(msg)
                    smtp.quit()
                    
                    # Log to GSheets
                    new_entry = pd.DataFrame([{"Timestamp": datetime.now(), "Name": user_name, "Pincode": pincode, "Issue": issue[:100], "Recipient": recipient}])
                    all_data = pd.concat([conn.read(), new_entry], ignore_index=True)
                    conn.update(data=all_data)

                    st.success("Sent Successfully!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error: {e}")