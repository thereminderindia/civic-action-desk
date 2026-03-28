import st
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
    st.sidebar.error("Check GSheets Secrets.")

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
logo_url = "https://www.facebook.com/photo/?fbid=122097222099239425&set=pb.61587182761969.-2207520000" 

col1, col2 = st.columns([1, 4])
with col1:
    st.image(logo_url, width=80)
with col2:
    st.title("The Reminder India")
    st.subheader("National Civic Action Desk")

# 4. LOCATION LOGIC (NEW)
st.markdown("### 📍 Location Details")
loc_col1, loc_col2 = st.columns([2, 1])

with loc_col2:
    # This button triggers the phone's GPS
    if st.button("🛰️ Use GPS"):
        location = streamlit_js_eval(data_key='pos', func_name='getCurrentPosition', want_output=True)
        if location:
            lat = location['coords']['latitude']
            lon = location['coords']['longitude']
            st.session_state.lat_lon = f"{lat}, {lon}"
            st.success("Location Captured!")
        else:
            st.warning("Please allow location access in your browser.")

with loc_col1:
    # Pincode can be entered manually or remains blank if GPS is used
    pincode = st.text_input("Enter 6-Digit Pincode:", value=st.session_state.get('pincode', ""), max_chars=6)

# 5. User Inputs
user_name = st.text_input("Full Name (Sender):")
user_phone = st.text_input("Contact Number (Optional):")
uploaded_files = st.file_uploader("Attach Evidence:", type=["jpg", "png", "jpeg", "mp4", "mov"], accept_multiple_files=True)
issue = st.text_area("Describe the local problem:")

# 6. Smart AI Generation
if st.button("🚀 1. Generate Official Letter"):
    # Check if we have EITHER a pincode OR GPS coordinates
    loc_data = st.session_state.get('lat_lon', pincode)
    
    if not loc_data or not issue:
        st.error("Please provide a location (Pincode or GPS) and describe the issue.")
    else:
        with st.spinner("Analyzing location and drafting..."):
            system_prompt = f"""
            You are a Senior Civic Advocate. Draft a formal complaint based on these rules:
            
            LOCATION DATA: {loc_data}
            - If GPS coordinates are provided, identify the City, State, and Pincode.
            - If Pincode 247775 is used, it is KANDHLA, UTTAR PRADESH.
            
            SENDER SECTION:
            - Name: {user_name}
            - Contact: {user_phone if user_phone else 'Not provided'}
            - NO street address. NO sender email.
            
            CONTENT:
            - DATE: {current_date}
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

# 7. Review & Send
if "letter" in st.session_state:
    st.divider()
    st.text_area("Final Letter Draft:", value=st.session_state.letter, height=400)
    pdf_bytes = create_pdf(st.session_state.letter)
    st.download_button("📥 Download PDF", data=pdf_bytes, file_name=f"Complaint_Letter.pdf")

    recipient = st.text_input("Authority Email:", value=st.session_state.suggested_email)

    if st.button("📧 2. Send Email Now"):
        if recipient:
            with st.spinner("Sending..."):
                try:
                    msg = EmailMessage()
                    msg.set_content(st.session_state.letter)
                    msg['Subject'] = f"CIVIC COMPLAINT: Reported by {user_name}"
                    msg['From'] = SENDER_EMAIL
                    msg['To'] = recipient
                    if uploaded_files:
                        for f in uploaded_files:
                            msg.add_attachment(f.read(), maintype='application', subtype='octet-stream', filename=f.name)
                    
                    smtp = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                    smtp.login(SENDER_EMAIL, APP_PASSWORD)
                    smtp.send_message(msg)
                    smtp.quit()

                    # Database Log
                    new_entry = pd.DataFrame([{"Timestamp": datetime.now(), "Name": user_name, "Pincode": pincode, "Issue": issue[:100], "Recipient": recipient}])
                    # Get existing data and update (logic simplified for clarity)
                    try:
                        existing = conn.read()
                        updated = pd.concat([existing, new_entry], ignore_index=True)
                        conn.update(data=updated)
                    except:
                        conn.create(data=new_entry)

                    st.success("Sent & Recorded Successfully!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error: {e}")