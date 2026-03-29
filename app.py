import streamlit as st
from openai import OpenAI
import smtplib
from email.message import EmailMessage
from fpdf import FPDF
import pandas as pd
import re
import mimetypes
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
from streamlit_js_eval import streamlit_js_eval
import urllib.parse

# 1. SETUP & AUTHENTICATION
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
APP_PASSWORD = st.secrets["APP_PASSWORD"]
current_date = datetime.now().strftime("%d %B, %Y")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except:
    st.sidebar.error("Database connection issue.")

# EMAIL VALIDATION HELPER
def is_valid_email(email_str):
    if not email_str.strip():
        return True 
    emails = [e.strip() for e in email_str.split(',')]
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return all(re.match(pattern, e) for e in emails if e)

# 2. LOCAL CSV ENGINE
@st.cache_data
def load_pincode_db():
    try:
        df = pd.read_csv("pincodes.csv")
        df.columns = [c.strip().lower() for c in df.columns]
        df['pincode'] = df['pincode'].astype(str)
        return df
    except:
        return None

# PDF ENGINE
def create_pdf(text):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=11)
        for line in text.split('\n'):
            if current_date in line:
                pdf.cell(0, 10, txt=line, ln=True, align='R')
            else:
                pdf.multi_cell(0, 10, txt=line, align='L')
        return pdf.output(dest='S').encode('latin-1', 'ignore')
    except Exception as e:
        return None

# 3. INTERFACE & SIDEBAR
st.set_page_config(page_title="The Reminder India", page_icon="🏛️", layout="wide")

st.markdown("""
    <style>
        div[data-testid="InputInstructions"] {
            display: none !important;
        }
    </style>
""", unsafe_allow_html=True)

st.sidebar.title("📲 Connect with TRI")
st.sidebar.link_button("📺 YouTube", "https://youtube.com/@TheReminderIndia")
st.sidebar.link_button("🔵 Facebook", "https://facebook.com/TheReminderIndia")
st.sidebar.link_button("📸 Instagram", "https://instagram.com/TheReminderIndia")
st.sidebar.markdown("---")
st.sidebar.title("🛠️ Tools")
st.sidebar.link_button("🔍 Pincode Verify", "https://www.indiapost.gov.in/VAS/Pages/findpincode.aspx")

pincode_df = load_pincode_db()

# The fixed code using your own file
col_logo, col_title = st.columns([1, 5])
with col_logo:
    # Make sure "logo.png" matches the exact name of your file!
    st.image("logo.png", width=90) 
with col_title:
    st.title("The Reminder India")
    st.subheader("National Civic Action Desk")

# 4. STEP 1: LANGUAGE & LOCATION
st.markdown("---")
st.subheader("📍 Step 1: Language & Location")
lang_col, pin_col, details_col = st.columns([2, 2, 4])

with lang_col:
    target_language = st.selectbox("Select Letter Language:", 
        ["English", "Hindi (हिन्दी)", "Bengali (বাংলা)", "Marathi (मराठी)", 
         "Telugu (తెలుగు)", "Tamil (தமிழ்)", "Gujarati (ગુજરાતી)", 
         "Urdu (اردو)", "Kannada (କನ್ನಡ)", "Odia (ଓଡ଼ିଆ)", 
         "Malayalam (മലയാളം)", "Punjabi (ਪੰਜਾਬੀ)", "Assamese (অসমੀয়া)", 
         "Maithili (मैथिली)", "Santali (संताली)", "Kashmiri (کٲशُر)", 
         "Nepali (नेपाली)", "Konkani (कोंकਣੀ)", "Sindhi (سنڌي)", 
         "Dogri (डोगरी)", "Manipuri (মৈতৈলোন)", "Bodo (बर')", "Sanskrit (संस्कृतम्)"])

with pin_col:
    user_pin = st.text_input("Enter 6-Digit PIN:", value="", max_chars=6)
    if user_pin and (not user_pin.isdigit() or len(user_pin) != 6):
        st.error("⚠️ Pincode must be exactly 6 digits.")

selected_loc = None
if user_pin and len(user_pin) == 6 and pincode_df is not None:
    matches = pincode_df[pincode_df['pincode'] == str(user_pin)]
    if not matches.empty:
        with details_col:
            office_list = matches['officename'].unique().tolist()
            chosen_office = st.selectbox("Confirm Town/City:", office_list)
            row = matches[matches['officename'] == chosen_office].iloc[0]
            selected_loc = {"Town": row['officename'], "District": row['district'], "State": row['circlename'], "PIN": user_pin}
            st.success(f"✅ Area: {selected_loc['Town']}, {selected_loc['District']}")
            
            st.sidebar.markdown("---")
            st.sidebar.subheader("🔍 Find Official Email")
            search_query = f"official email municipal commissioner {selected_loc['Town']} {selected_loc['District']} site:.gov.in OR site:.nic.in"
            google_url = f"https://www.google.com/search?q={urllib.parse.quote(search_query)}"
            st.sidebar.link_button(f"🌐 Search for {selected_loc['Town']} Email", google_url)

# GPS & File Uploads
col_gps, col_files = st.columns(2)
with col_gps:
    if st.button("🛰️ Capture Exact GPS"):
        loc = streamlit_js_eval(data_key='pos', func_name='getCurrentPosition', want_output=True)
        if loc:
            lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
            st.session_state.maps_link = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}&travelmode=driving"
            st.success(f"✅ GPS Captured! Navigation Link generated.")

with col_files:
    uploaded_files = st.file_uploader("Attach Evidence (Photos/Videos):", accept_multiple_files=True)

# 5. STEP 2: REPORTER DETAILS
st.markdown("---")
st.subheader("📝 Step 2: Reporter Details")
user_name = st.text_input("Full Name (Sender):")

user_phone = st.text_input("Contact Number (Optional):", max_chars=10)
if user_phone:
    if not user_phone.isdigit():
        st.error("⚠️ Phone number must contain numbers only.")
    elif len(user_phone) < 10:
        st.warning("⚠️ Please enter the full 10-digit number.")

issue = st.text_area("Describe the local problem:")

# 6. STEP 3: GENERATION
if st.button("🚀 1. Generate Official Letter"):
    if "letter" in st.session_state:
        del st.session_state["letter"]
        
    if not user_name or not selected_loc or not issue or len(user_pin) != 6:
        st.error("⚠️ Please complete all fields correctly.")
    else:
        with st.spinner(f"Drafting formal petition..."):
            p_val = user_phone.strip()
            contact_line = f"Contact Number: {p_val}" if p_val else ""
            
            maps_url = st.session_state.get('maps_link', "")
            gps_line = f"The exact location of this issue can be navigated to via Google Maps: {maps_url}" if maps_url else ""
            
            evidence_line = "I have attached photographic/video evidence to this email for your reference." if uploaded_files and len(uploaded_files) > 0 else ""

            system_prompt = f"""
            You are a professional assistant drafting a formal civic complaint letter in {target_language}.
            Write a flowing, natural letter. DO NOT output bullet points like "BODY:" or "SIGN-OFF:".
            
            Format the letter exactly like this:

            {current_date}

            From,
            {user_name}
            {contact_line}

            To,
            The Municipal Commissioner,
            {selected_loc['Town']}, {selected_loc['District']}.
            PIN: {selected_loc['PIN']}

            Subject: [Generate a clear, concise subject line]

            Dear Sir/Madam,

            [Write 2 to 3 professional paragraphs explaining this issue: "{issue}".]
            
            {gps_line}
            {evidence_line}
            [Smoothly weave the location and evidence sentences into the text if they are provided above. If they are empty, do not mention them at all.]

            Sincerely,
            {user_name}
            Supported by The Reminder India community.

            ---
            RULES: 
            - RAW TEXT ONLY. NO markdown formatting like backticks (```) or bolding (**).
            - Omit any empty fields completely.
            - END WITH: 'SUGGESTED_EMAIL: ' (Followed by the likely official email, or blank if unknown).
            """
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": issue}]
            )
            res_content = response.choices[0].message.content.replace("```", "").strip()
            st.session_state.letter = res_content.split("SUGGESTED_EMAIL:")[0].strip()
            raw_email = res_content.split("SUGGESTED_EMAIL:")[1].strip() if "SUGGESTED_EMAIL:" in res_content else ""
            st.session_state.sug_email = raw_email.replace("`", "").replace("'", "").strip()

# 7. STEP 4: REVIEW & MULTI-SEND
if "letter" in st.session_state:
    st.divider()
    st.subheader("📬 Step 4: Final Review & Email Controls")
    st.text_area("Letter Content:", value=st.session_state.letter, height=400)
    
    st.markdown("##### 📨 Email Routing")
    col_to, col_cc = st.columns(2)
    with col_to:
        rec_to = st.text_input("To (Primary Official):", value=st.session_state.sug_email)
    with col_cc:
        rec_cc = st.text_input("CC (Public Copy):", value="")
        
    col_bcc, col_me = st.columns(2)
    with col_bcc:
        rec_bcc = st.text_input("BCC (Secret Archive):", value="")
    with col_me:
        user_receipt = st.text_input("Your Email (For Receipt Copy):", value="")

    dispatch_log = f"\n\n{'-'*40}\nOFFICIAL DISPATCH RECORD\n{'-'*40}\n"
    dispatch_log += f"Sent To: {rec_to if rec_to else 'Pending'}\n"
    dispatch_log += f"CC: {rec_cc if rec_cc else 'None'}\n"
    dispatch_log += f"BCC: {rec_bcc if rec_bcc else 'None'}\n"
    if user_receipt:
        dispatch_log += f"Receipt Sent To: {user_receipt}\n"
    dispatch_log += f"{'-'*40}"
    
    final_download_text = st.session_state.letter + dispatch_log

    st.markdown("<br>", unsafe_allow_html=True)
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        if target_language == "English":
            pdf_bytes = create_pdf(final_download_text)
            if pdf_bytes:
                st.download_button("📥 Download Print PDF (With Dispatch Log)", data=pdf_bytes, file_name=f"TRI_Report_{user_pin}.pdf", mime="application/pdf")
            else:
                st.error("Error generating PDF.")
        else:
            txt_bytes = final_download_text.encode('utf-8')
            st.download_button("📥 Download Letter (With Dispatch Log)", data=txt_bytes, file_name=f"TRI_Report_{user_pin}.txt", mime="text/plain")

    with col_btn2:
        # Add this tiny disclaimer right above your send button
        st.caption("By clicking send, you agree to our [Privacy Policy](https://sites.google.com/view/thereminderindia/home?authuser=4).")
        if st.button("📧 Send Official Email Now"):
            combined_bcc_list = []
            if rec_bcc: combined_bcc_list.append(rec_bcc)
            if user_receipt: combined_bcc_list.append(user_receipt)
            final_bcc_string = ", ".join(combined_bcc_list)

            if not is_valid_email(rec_to) or not is_valid_email(rec_cc) or not is_valid_email(final_bcc_string):
                st.error("❌ Invalid email format detected in one of the fields.")
            elif not rec_to:
                st.error("❌ Primary Recipient (To) is required.")
            else:
                total_size = 0
                if uploaded_files:
                    total_size = sum([f.size for f in uploaded_files])
                
                # Lowered the limit slightly to 20MB because email encoding adds 30% extra invisible weight to files!
                if total_size > 20 * 1024 * 1024:
                    st.error("⚠️ Attachments are too large! Please compress your video or use a photo instead (Max 20MB).")
                else:
                    with st.spinner("Sending Email with Attachments..."):
                        try:
                            msg = EmailMessage()
                            msg.set_content(st.session_state.letter)
                            msg['Subject'] = f"CIVIC COMPLAINT: {selected_loc['Town']} - {user_name}"
                            msg['From'] = SENDER_EMAIL
                            msg['To'] = rec_to
                            if rec_cc: msg['Cc'] = rec_cc
                            if final_bcc_string: msg['Bcc'] = final_bcc_string
                            
                            # --- NEW BULLETPROOF ATTACHMENT LOGIC ---
                            if uploaded_files:
                                for f in uploaded_files:
                                    # 1. Safely grab the raw bytes (Streamlit's preferred method)
                                    file_data = f.getvalue() 
                                    
                                    # 2. Grab the exact MIME type directly from the mobile browser (e.g., 'image/jpeg')
                                    mime_type = f.type 
                                    
                                    # 3. Fallback just in case the mobile browser is being stubborn
                                    if not mime_type or '/' not in mime_type:
                                        mime_type = 'application/octet-stream'
                                        
                                    maintype, subtype = mime_type.split('/', 1)
                                    
                                    # 4. Clean the filename to prevent mobile path errors
                                    clean_filename = f.name.split("/")[-1].split("\\")[-1]
                                    
                                    msg.add_attachment(file_data, maintype=maintype, subtype=subtype, filename=clean_filename)
                            # ----------------------------------------
                            
                            smtp = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                            smtp.login(SENDER_EMAIL, APP_PASSWORD)
                            smtp.send_message(msg)
                            smtp.quit()
                            
                            st.success("✅ Reported Successfully! Check your email for the receipt.")
                            st.balloons()
                        except Exception as e:
                            st.error(f"Error sending email: {e}")

    # --- THE NEW CLEAR FORM BUTTON ---
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("---")
    col_spacer, col_clear = st.columns([3, 1])
    with col_clear:
        if st.button("🔄 Clear Form & Start New"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()