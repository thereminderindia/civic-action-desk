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

# 1. SETUP & AUTHENTICATION
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
APP_PASSWORD = st.secrets["APP_PASSWORD"]
current_date = datetime.now().strftime("%B %d, %Y")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except:
    st.sidebar.error("Database connection issue.")

# 2. LOCAL CSV ENGINE (Mapped to your specific columns)
@st.cache_data
def load_pincode_db():
    try:
        # Load your CSV from the GitHub repo
        df = pd.read_csv("pincodes.csv")
        # Clean column names (lowercase/no spaces) to match your request
        df.columns = [c.strip().lower() for c in df.columns]
        df['pincode'] = df['pincode'].astype(str)
        return df
    except Exception as e:
        st.error(f"Error loading pincodes.csv: {e}")
        return None

def create_pdf(text):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for line in text.split('\n'):
        pdf.multi_cell(0, 10, txt=line, align='L')
    return pdf.output(dest='S').encode('latin-1', 'ignore')

# 3. INTERFACE & SIDEBAR
st.set_page_config(page_title="The Reminder India", page_icon="🏛️", layout="wide")

# Sidebar: Social Media
st.sidebar.title("📲 Connect with TRI")
st.sidebar.link_button("📺 YouTube", "https://youtube.com/@TheReminderIndia")
st.sidebar.link_button("🔵 Facebook", "https://facebook.com/TheReminderIndia")
st.sidebar.link_button("📸 Instagram", "https://instagram.com/TheReminderIndia")
st.sidebar.markdown("---")
st.sidebar.title("🛠️ Tools")
st.sidebar.link_button("🔍 Official Pincode Verify", "https://www.indiapost.gov.in/VAS/Pages/findpincode.aspx")

pincode_df = load_pincode_db()

# Branding Header
logo_url = "https://www.facebook.com/photo/?fbid=122097222099239425&set=pb.61587182761969.-2207520000" 
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.image(logo_url, width=90)
with col_title:
    st.title("The Reminder India")
    st.subheader("National Civic Action Desk")

# 4. LOCATION & LANGUAGE (Dynamic Mapping)
st.markdown("---")
lang_col, pin_col, details_col = st.columns([2, 2, 3])

with lang_col:
    target_language = st.selectbox("Select Language:", 
        ["English", "Hindi (हिन्दी)", "Bengali (বাংলা)", "Marathi (मराठी)", 
         "Telugu (తెలుగు)", "Tamil (தமிழ்)", "Punjabi (ਪੰਜਾਬੀ)", "Urdu (اردو)"])

with pin_col:
    user_pin = st.text_input("Enter 6-Digit PIN:", value="", max_chars=6, placeholder="e.g. 110006")

# Dynamic Logic for CSV Columns
selected_loc = None
with details_col:
    if user_pin and pincode_df is not None:
        # Search the CSV
        matches = pincode_df[pincode_df['pincode'] == str(user_pin)]
        
        if not matches.empty:
            # User chooses the specific 'officename' (Town/City)
            office_list = matches['officename'].unique().tolist()
            chosen_office = st.selectbox("Select Town/City (from Officename):", office_list)
            
            # Map the rest of the columns for that selection
            final_match = matches[matches['officename'] == chosen_office].iloc[0]
            selected_loc = {
                "Town": final_match['officename'], 
                "District": final_match['district'], 
                "State": final_match['circlename'], 
                "PIN": user_pin
            }
            # Visual Confirmation for User
            st.success(f"✅ Found: {selected_loc['Town']}, {selected_loc['District']}, {selected_loc['State']}")
        else:
            st.error("❌ PIN not found in database.")

# 5. USER INPUTS
user_name = st.text_input("Full Name (Sender):")
user_phone = st.text_input("Contact Number (Optional):")
issue = st.text_area("Describe the local problem:")

# 6. STEP 1: GENERATE LETTER
if st.button("🚀 1. Generate Official Letter"):
    if not user_name or not selected_loc or not issue:
        st.error("⚠️ Please provide Name, valid PIN/Town, and Issue.")
    else:
        with st.spinner("Drafting formal letter..."):
            contact_line = f"Contact: {user_phone}" if user_phone.strip() else ""
            
            system_prompt = f"""
            Draft a formal complaint in {target_language}.
            
            SENDER: {user_name}, PIN: {selected_loc['PIN']}
            {contact_line}
            DATE: {current_date}

            LOCATION FACTS:
            - Town/City: {selected_loc['Town']}
            - District: {selected_loc['District']}
            - State: {selected_loc['State']}

            STRICT RULES:
            1. RECIPIENT: Start with 'To,'. Address it to the Municipal Commissioner of {selected_loc['Town']}.
            2. DATE: Always include {current_date} at the top.
            3. No guesses. Only use the Town, District, and State provided above.
            4. SIGN-OFF: Sincerely, {user_name}. Supported by The Reminder India community.
            
            END WITH: 'SUGGESTED_EMAIL: ' (Likely municipal email).
            """
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": issue}]
            )
            res_content = response.choices[0].message.content
            st.session_state.letter = res_content.split("SUGGESTED_EMAIL:")[0].strip()
            st.session_state.suggested_email = res_content.split("SUGGESTED_EMAIL:")[1].strip() if "SUGGESTED_EMAIL:" in res_content else ""

# 7. STEP 2: REVIEW & EMAIL CONTROLS
if "letter" in st.session_state:
    st.divider()
    st.subheader("📝 Review & Recipients")
    st.text_area("Final Letter Draft:", value=st.session_state.letter, height=350)
    
    col_to, col_cc, col_bcc = st.columns(3)
    with col_to:
        rec_to = st.text_input("To (Primary):", value=st.session_state.suggested_email)
    with col_cc:
        rec_cc = st.text_input("CC (Public):", placeholder="news@media.com")
    with col_bcc:
        rec_bcc = st.text_input("BCC (Private):", placeholder="archive@tri.com")

    # Download PDF
    pdf_bytes = create_pdf(st.session_state.letter)
    st.download_button("📥 Download PDF", data=pdf_bytes, file_name=f"Complaint_{user_pin}.pdf")

    if st.button("📧 2. Send Official Email"):
        if not rec_to:
            st.error("❌ Recipient email is required.")
        else:
            with st.spinner("Sending..."):
                try:
                    msg = EmailMessage()
                    msg.set_content(st.session_state.letter)
                    msg['Subject'] = f"CIVIC COMPLAINT: {selected_loc['Town']} - {user_name}"
                    msg['From'] = SENDER_EMAIL
                    msg['To'] = rec_to
                    if rec_cc: msg['Cc'] = rec_cc
                    if rec_bcc: msg['Bcc'] = rec_bcc
                    
                    smtp = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                    smtp.login(SENDER_EMAIL, APP_PASSWORD)
                    smtp.send_message(msg)
                    smtp.quit()
                    
                    # Log to Sheets
                    new_entry = pd.DataFrame([{"Timestamp": datetime.now(), "Name": user_name, "Town": selected_loc['Town'], "PIN": user_pin}])
                    all_data = pd.concat([conn.read(), new_entry], ignore_index=True)
                    conn.update(data=all_data)

                    st.success("✅ Sent Successfully!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error: {e}")