import streamlit as st
from openai import OpenAI
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
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
st.sidebar.markdown("---")
st.sidebar.caption("⚖️ Legal & Trust")
st.sidebar.link_button("📄 Privacy Policy", "https://sites.google.com/view/thereminderindia/home")

pincode_df = load_pincode_db()

# Ensure you have your logo.jpg in the same folder!
col_logo, col_title = st.columns([1, 5])
with col_logo:
    try:
        st.image("logo.jpg", width=90)
    except:
        st.title("🏛️")
with col_title:
    st.title("The Reminder India")
    st.subheader("National Civic Action Desk")

# 4. STEP 1: LANGUAGE & LOCATION
st.markdown("---")
st.subheader("📍 Step 1: Language & Location")
lang_col, pin_col, details_col = st.columns([2, 2, 4])

with lang_col:
    # ADDED KEY HERE
    target_language = st.selectbox("Select Letter Language:", key="lang", options=
        ["English", "Hindi (हिन्दी)", "Bengali (বাংলা)", "Marathi (मराठी)", 
         "Telugu (తెలుగు)", "Tamil (தமிழ்)", "Gujarati (ગુજરાતી)", 
         "Urdu (اردو)", "Kannada (କನ್ನಡ)", "Odia (ଓଡ଼ିଆ)", 
         "Malayalam (മലയാളം)", "Punjabi (ਪੰਜਾਬੀ)", "Assamese (অসমੀয়া)", 
         "Maithili (मैथिली)", "Santali (संताली)", "Kashmiri (کٲशُر)", 
         "Nepali (नेपाली)", "Konkani (कोंकਣੀ)", "Sindhi (سنڌي)", 
         "Dogri (डोगरी)", "Manipuri (মৈতৈলোন)", "Bodo (बर')", "Sanskrit (संस्कृतम्)"])

with pin_col:
    # ADDED KEY HERE
    user_pin = st.text_input("Enter 6-Digit PIN:", value="", max_chars=6, key="pin")
    if user_pin and (not user_pin.isdigit() or len(user_pin) != 6):
        st.error("⚠️ Pincode must be exactly 6 digits.")

selected_loc = None
if user_pin and len(user_pin) == 6 and pincode_df is not None:
    matches = pincode_df[pincode_df['pincode'] == str(user_pin)]
    if not matches.empty:
        with details_col:
            office_list = matches['officename'].unique().tolist()
            # ADDED KEY HERE
            chosen_office = st.selectbox("Confirm Town/City:", office_list, key="office")
            row = matches[matches['officename'] == chosen_office].iloc[0]
            selected_loc = {"Town": row['officename'], "District": row['district'], "State": row['circlename'], "PIN": user_pin}
            st.success(f"✅ Area: {selected_loc['Town']}, {selected_loc['District']}")
            
            st.sidebar.markdown("---")
            st.sidebar.subheader("🔍 Find Official Email")
            search_query = f"official email municipal commissioner {selected_loc['Town']} {selected_loc['District']} site:.gov.in OR site:.nic.in"
            google_url = f"https://www.google.com/search?q={urllib.parse.quote(search_query)}"
            st.sidebar.link_button(f"🌐 Search for {selected_loc['Town']} Email", google_url)

# --- THE BULLETPROOF MOBILE UPLOADER ---
col_gps, col_files = st.columns(2)
with col_gps:
    if st.button("🛰️ Capture Exact GPS"):
        loc = streamlit_js_eval(data_key='pos', func_name='getCurrentPosition', want_output=True)
        if loc:
            lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
            st.session_state.maps_link = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}&travelmode=driving"
            st.success(f"✅ GPS Captured! Navigation Link generated.")

with col_files:
    # ADDED KEY HERE
    uploaded_files = st.file_uploader("Attach Evidence (Photos/Videos):", accept_multiple_files=True, key="evidence")
    st.caption("💡 Tip: Try to include a nearby landmark or street sign in your photo so officials can locate the issue faster.")
    
    if uploaded_files:
        st.session_state.file_vault = [] 
        st.markdown("📄 **Attached Previews:**")
        
        preview_cols = st.columns(2)
        
        for i, f in enumerate(uploaded_files):
            raw_bytes = f.getvalue() 
            file_mime = f.type if f.type else ""
            file_name_lower = f.name.lower()
            
            is_video = 'video' in file_mime or file_name_lower.endswith(('.mp4', '.mov', '.avi', '.webm'))
            is_image = not is_video 

            st.session_state.file_vault.append({
                "name": f.name,
                "mime": file_mime if file_mime else 'application/octet-stream',
                "bytes": raw_bytes
            })
            
            with preview_cols[i % 2]:
                try:
                    if is_video:
                        st.video(raw_bytes)
                        st.caption(f"🎥 {f.name}")
                    else:
                        st.image(raw_bytes, use_container_width=True)
                        st.caption(f"📸 {f.name}")
                except Exception:
                    st.success(f"📎 Safely Attached: {f.name}")
    else:
        st.session_state.file_vault = []
# ---------------------------------------

# 5. STEP 2: REPORTER DETAILS   
st.markdown("---")
st.subheader("📝 Step 2: Reporter Details")
# ADDED KEY HERE
user_name = st.text_input("Full Name (Sender):", key="sender_name")

# ADDED KEY HERE
user_phone = st.text_input("Contact Number (Optional):", max_chars=10, key="sender_phone")
if user_phone:
    if not user_phone.isdigit():
        st.error("⚠️ Phone number must contain numbers only.")
    elif len(user_phone) < 10:
        st.warning("⚠️ Please enter the full 10-digit number.")

# ADDED KEY HERE
issue_category = st.selectbox("Quick Issue Select (Optional):", key="category", options=
    ["", "Uncollected Garbage", "Broken Road / Pothole", "Clogged Drainage", "Non-functional Streetlight", "Contaminated Water", "Other"])
# ADDED KEY HERE
issue_details = st.text_area("Describe the local problem (Specific details, location, etc.):", key="details")

# Combine the category and details seamlessly for the AI
issue = f"Category: {issue_category}\nDetails: {issue_details}" if issue_category else issue_details

# 6. STEP 3: GENERATION
if st.button("🚀 1. Generate Official Letter"):
    if "letter" in st.session_state:
        del st.session_state["letter"]
        
    if not user_name or not selected_loc or not issue.strip() or len(user_pin) != 6:
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
            - END WITH: 'SUGGESTED_EMAIL: ' (Followed by the exact official email if you are 100% certain. If you do not know it, or if your data says "[email protected]", you MUST leave it completely blank).
            """
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": issue}]
            )
            res_content = response.choices[0].message.content.replace("```", "").strip()
            st.session_state.letter = res_content.split("SUGGESTED_EMAIL:")[0].strip()
            
            # Extract the email and filter out the bot-protection text
            raw_email = res_content.split("SUGGESTED_EMAIL:")[1].strip() if "SUGGESTED_EMAIL:" in res_content else ""
            if "[email protected]" in raw_email:
                raw_email = ""
                
            st.session_state.sug_email = raw_email.replace("`", "").replace("'", "").strip()

# 7. STEP 4: REVIEW & MULTI-SEND
if "letter" in st.session_state:
    st.divider()
    st.subheader("📬 Step 4: Final Review & Email Controls")
    st.text_area("Letter Content:", value=st.session_state.letter, height=400)
    
    st.markdown("##### 📨 Email Routing")
    col_to, col_cc = st.columns(2)
    with col_to:
        # ADDED KEY HERE
        rec_to = st.text_input("To (Primary Official):", value=st.session_state.sug_email, key="rec_to")
    with col_cc:
        # ADDED KEY HERE
        rec_cc = st.text_input("CC (Public Copy):", value="", key="rec_cc")
        
    col_bcc, col_me = st.columns(2)
    with col_bcc:
        # ADDED KEY HERE
        rec_bcc = st.text_input("BCC (Secret Archive):", value="", key="rec_bcc")
    with col_me:
        # ADDED KEY HERE
        user_receipt = st.text_input("Your Email (For Receipt Copy):", value="", key="user_receipt")

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
        st.caption("By clicking send, you agree to our [Privacy Policy](https://sites.google.com/view/thereminderindia/home).")
        
        if st.button("📧 Send Official Email Now"):
            combined_bcc_list = []
            if rec_bcc: combined_bcc_list.append(rec_bcc)
            if user_receipt: combined_bcc_list.append(user_receipt)
            final_bcc_string = ", ".join(combined_bcc_list)

            if not is_valid_email(rec_to) or not is_valid_email(rec_cc) or not is_valid_email(final_bcc_string):
                st.error("❌ Invalid email format detected.")
            elif not rec_to:
                st.error("❌ Primary Recipient (To) is required.")
            else:
                # 1. Check size using the Server Vault, NOT the phone's memory
                vault_files = st.session_state.get("file_vault", [])
                total_size = sum([len(f["bytes"]) for f in vault_files]) if vault_files else 0
                
                if total_size > 20 * 1024 * 1024:
                    st.error("⚠️ Attachments are too large! Please compress your video or use a photo instead (Max 20MB).")
                else:
                    with st.spinner("Preparing secure attachments & sending email..."):
                        try:
                            msg = MIMEMultipart()
                            msg['Subject'] = f"CIVIC COMPLAINT: {selected_loc['Town']} - {user_name}"
                            msg['From'] = SENDER_EMAIL
                            msg['To'] = rec_to
                            if rec_cc: msg['Cc'] = rec_cc
                            if final_bcc_string: msg['Bcc'] = final_bcc_string
                            
                            msg.attach(MIMEText(st.session_state.letter, 'plain'))
                            
                            # 2. Attach files directly from the Server Vault
                            if vault_files:
                                for f_data in vault_files:
                                    file_bytes = f_data["bytes"]
                                    mime_type = f_data["mime"]
                                    
                                    if '/' not in mime_type:
                                        mime_type = 'application/octet-stream'
                                        
                                    maintype, subtype = mime_type.split('/', 1)
                                    clean_filename = f_data["name"].split("/")[-1].split("\\")[-1]
                                    
                                    if '.' not in clean_filename:
                                        ext = mimetypes.guess_extension(mime_type)
                                        clean_filename += ext if ext else ".jpg" # Force .jpg if phone completely hides format
                                            
                                    part = MIMEBase(maintype, subtype)
                                    part.set_payload(file_bytes)
                                    
                                    encoders.encode_base64(part) 
                                    part.add_header('Content-Disposition', f'attachment; filename="{clean_filename}"')
                                    
                                    msg.attach(part)
                            # --------------------------------------
                            
                            smtp = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                            smtp.login(SENDER_EMAIL, APP_PASSWORD)
                            smtp.send_message(msg)
                            smtp.quit()
                            
                            # 💡 ADDITION 3: The Enhanced Success Message
                            st.success("✅ Official Letter Sent! Please check your email (and Spam folder) for your receipt. If the issue is not resolved in 7 days, we encourage you to follow up.")
                            st.balloons()
                        except Exception as e:
                            st.error(f"Error sending email: {e}")

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("---")
    col_spacer, col_clear = st.columns([3, 1])
    with col_clear:
        # --- THE NUCLEAR CLEAR COMMAND ---
        if st.button("🔄 Clear Form & Start New"):
            st.session_state.clear()
            st.rerun()