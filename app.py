import streamlit as st
from openai import OpenAI
import smtplib
from email.message import EmailMessage
from fpdf import FPDF
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
from streamlit_js_eval import streamlit_js_eval
import urllib.parse
import base64

# 1. SETUP & AUTH
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
APP_PASSWORD = st.secrets["APP_PASSWORD"]
current_date = datetime.now().strftime("%d %B, %Y")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except:
    st.sidebar.error("Database connection issue.")

# 2. HELPER FUNCTIONS
@st.cache_data
def load_pincode_db():
    try:
        df = pd.read_csv("pincodes.csv")
        df.columns = [c.strip().lower() for c in df.columns]
        df['pincode'] = df['pincode'].astype(str)
        return df
    except:
        return None

def create_pdf(text):
    """Creates a clean, formal PDF for printing."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    # Adding text to PDF line by line
    for line in text.split('\n'):
        # Checking if line is a Date line to align right in PDF
        if current_date in line:
            pdf.cell(0, 10, txt=line, ln=True, align='R')
        else:
            pdf.multi_cell(0, 10, txt=line, align='L')
    return pdf.output(dest='S').encode('latin-1', 'ignore')

# 3. INTERFACE & SIDEBAR
st.set_page_config(page_title="The Reminder India", page_icon="🏛️", layout="wide")

st.sidebar.title("📲 Connect with TRI")
st.sidebar.link_button("📺 YouTube", "https://youtube.com/@TheReminderIndia")
st.sidebar.link_button("🔵 Facebook", "https://facebook.com/TheReminderIndia")
st.sidebar.link_button("📸 Instagram", "https://instagram.com/TheReminderIndia")

pincode_df = load_pincode_db()

# Branding
logo_url = "https://www.facebook.com/photo/?fbid=122097222099239425&set=pb.61587182761969.-2207520000" 
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.image(logo_url, width=90)
with col_title:
    st.title("The Reminder India")
    st.subheader("National Civic Action Desk")

# 4. LOCATION & INPUTS
st.markdown("---")
lang_col, pin_col, details_col = st.columns([2, 2, 4])

with lang_col:
    target_language = st.selectbox("Language:", ["English", "Hindi (हिन्दी)", "Punjabi (ਪੰਜਾਬੀ)", "Tamil (தமிழ்)"])

with pin_col:
    user_pin = st.text_input("6-Digit PIN:", value="", max_chars=6)

selected_loc = None
with details_col:
    if user_pin and pincode_df is not None:
        matches = pincode_df[pincode_df['pincode'] == str(user_pin)]
        if not matches.empty:
            office_list = matches['officename'].unique().tolist()
            chosen_office = st.selectbox("Select Town/City:", office_list)
            row = matches[matches['officename'] == chosen_office].iloc[0]
            selected_loc = {"Town": row['officename'], "District": row['district'], "State": row['circlename'], "PIN": user_pin}
            st.success(f"📍 {selected_loc['Town']}, {selected_loc['District']}")

col_gps, col_files = st.columns(2)
with col_gps:
    if st.button("🛰️ Capture GPS"):
        loc = streamlit_js_eval(data_key='pos', func_name='getCurrentPosition', want_output=True)
        if loc:
            st.session_state.gps = f"Lat: {loc['coords']['latitude']}, Lon: {loc['coords']['longitude']}"
            st.success("GPS Captured!")

with col_files:
    uploaded_files = st.file_uploader("Evidence Photos/Videos:", accept_multiple_files=True)

user_name = st.text_input("Your Full Name:")
user_phone = st.text_input("Contact Number (Optional):")
issue = st.text_area("Describe the Problem:")

# 5. LETTER GENERATION
if st.button("🚀 1. Generate Official Letter"):
    if not user_name or not selected_loc or not issue:
        st.error("⚠️ Please provide all details.")
    else:
        with st.spinner("Drafting..."):
            contact_line = f"Contact: {user_phone}" if user_phone.strip() else ""
            gps_val = st.session_state.get('gps', "Not captured (On-ground verification requested)")
            evidence_count = len(uploaded_files) if uploaded_files else 0

            system_prompt = f"""
            Draft a formal complaint in {target_language}.
            
            STRICT FORMATTING:
            1. First Line (Right Aligned): {current_date}
            2. To, The Municipal Commissioner, {selected_loc['Town']}, {selected_loc['District']}.
            3. From: {user_name}, PIN: {selected_loc['PIN']}. {contact_line}
            4. Body: 3 Paragraphs. Paragraph 2 MUST mention GPS: {gps_val}. Paragraph 3 MUST mention {evidence_count} attachments.
            5. Sign-off: Sincerely, {user_name}. Supported by TRI.
            
            END WITH: 'SUGGESTED_EMAIL: ' (likely municipal email).
            """
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": issue}]
            )
            res = response.choices[0].message.content
            st.session_state.letter = res.split("SUGGESTED_EMAIL:")[0].strip()
            st.session_state.sug_email = res.split("SUGGESTED_EMAIL:")[1].strip() if "SUGGESTED_EMAIL:" in res else ""

# 6. ACTION SECTION (Review, Print, Send)
if "letter" in st.session_state:
    st.divider()
    st.subheader("📄 Step 2: Review, Print or Send")
    
    st.text_area("Final Letter Preview:", value=st.session_state.letter, height=400)
    
    col_print, col_send = st.columns(2)
    
    with col_print:
        st.write("### 🖨️ Physical Submission")
        pdf_data = create_pdf(st.session_state.letter)
        st.download_button(
            label="📥 Download Print-Ready PDF",
            data=pdf_data,
            file_name=f"TRI_Complaint_{user_pin}.pdf",
            mime="application/pdf"
        )
        st.caption("Download this PDF, print it, and submit it at the local Municipal Office.")

    with col_send:
        st.write("### 📧 Digital Submission")
        rec_to = st.text_input("To:", value=st.session_state.sug_email)
        rec_cc = st.text_input("CC (Optional):", placeholder="e.g. tri.desk@gmail.com")
        
        if st.button("📧 Send Email Now"):
            if rec_to:
                with st.spinner("Sending..."):
                    try:
                        msg = EmailMessage()
                        msg.set_content(st.session_state.letter)
                        msg['Subject'] = f"CIVIC COMPLAINT: {selected_loc['Town']} - {user_name}"
                        msg['From'] = SENDER_EMAIL
                        msg['To'] = rec_to
                        if rec_cc: msg['Cc'] = rec_cc
                        
                        if uploaded_files:
                            for f in uploaded_files:
                                msg.add_attachment(f.read(), maintype='application', subtype='octet-stream', filename=f.name)
                        
                        smtp = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                        smtp.login(SENDER_EMAIL, APP_PASSWORD)
                        smtp.send_message(msg)
                        smtp.quit()
                        
                        st.success("Sent Successfully!")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Error: {e}")