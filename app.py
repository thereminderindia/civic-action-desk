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
import base64
import os

# --- INITIALIZE RESET COUNTER ---
if "reset_counter" not in st.session_state:
    st.session_state.reset_counter = 0

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

# --- NEW HEADER BANNER WITH CUSTOM BACKGROUND IMAGE ---
def get_base64_of_bin_file(bin_file):
    if os.path.exists(bin_file):
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return None

banner_base64 = get_base64_of_bin_file("banner.jpg")

if banner_base64:
    header_banner_html = f"""
    <div style="margin-bottom: 2em; text-align: center;">
        <img src="data:image/jpeg;base64,{banner_base64}" 
             style="width: 100%; height: auto; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.3); border: 2px solid #ffffff;">
    </div>
    """
else:
    header_banner_html = """
    <div style="background-color: #1E1E1E; padding: 2em; border-radius: 12px; text-align: center; margin-bottom: 2em;">
        <h1 style="color: white; margin:0;">🏛️ The Reminder India</h1>
        <h3 style="color: #aaaaaa; margin:0;">National Civic Action Desk</h3>
    </div>
    """

st.markdown(header_banner_html, unsafe_allow_html=True)
# --- END OF NEW HEADER BLOCK ---

# 4. STEP 1: LANGUAGE & LOCATION
st.markdown("---")
st.subheader("📍 Step 1: Language & Location")
lang_col, pin_col, details_col = st.columns([2, 2, 4])

with lang_col:
    target_language = st.selectbox("Select Letter Language:", key=f"lang_{st.session_state.reset_counter}", options=
        ["English", "Hindi (हिन्दी)", "Bengali (বাংলা)", "Marathi (मराठी)", 
         "Telugu (తెలుగు)", "Tamil (தமிழ்)", "Gujarati (ગુજરાતી)", 
         "Urdu (اردو)", "Kannada (କನ್ನಡ)", "Odia (ଓଡ଼ିଆ)", 
         "Malayalam (മലയാളം)", "Punjabi (ਪੰਜਾਬੀ)", "Assamese (অসমੀয়া)", 
         "Maithili (मैथिली)", "Santali (संताली)", "Kashmiri (کٲशُر)", 
         "Nepali (नेपाली)", "Konkani (कोंकਣੀ)", "Sindhi (سنڌي)", 
         "Dogri (डोगरी)", "Manipuri (মৈতৈলোন)", "Bodo (बर')", "Sanskrit (संस्कृतम्)"])

with pin_col:
    user_pin = st.text_input("Enter 6-Digit PIN:", value="", max_chars=6, key=f"pin_{st.session_state.reset_counter}")
    if user_pin and (not user_pin.isdigit() or len(user_pin) != 6):
        st.error("⚠️ Pincode must be exactly 6 digits.")

selected_loc = None
if user_pin and len(user_pin) == 6 and pincode_df is not None:
    matches = pincode_df[pincode_df['pincode'] == str(user_pin)]
    if not matches.empty:
        with details_col:
            office_list = matches['officename'].unique().tolist()
            chosen_office = st.selectbox("Confirm Town/City:", office_list, key=f"office_{st.session_state.reset_counter}")
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
    if st.button("🛰️ Capture Exact GPS", key=f"gps_{st.session_state.reset_counter}"):
        loc = streamlit_js_eval(data_key='pos', func_name='getCurrentPosition', want_output=True)
        if loc:
            lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
            st.session_state.maps_link = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}&travelmode=driving"
            st.success(f"✅ GPS Captured! Navigation Link generated.")

with col_files:
    uploaded_files = st.file_uploader("Attach Evidence (Photos/Videos):", accept_multiple_files=True, key=f"evidence_{st.session_state.reset_counter}")
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
user_name = st.text_input("Full Name (Sender):", key=f"sender_name_{st.session_state.reset_counter}")

user_phone = st.text_input("Contact Number (Optional):", max_chars=10, key=f"sender_phone_{st.session_state.reset_counter}")
if user_phone:
    if not user_phone.isdigit():
        st.error("⚠️ Phone number must contain numbers only.")
    elif len(user_phone) < 10:
        st.warning("⚠️ Please enter the full 10-digit number.")

issue_category = st.selectbox("Quick Issue Select (Optional):", key=f"category_{st.session_state.reset_counter}", options=
    ["", "Uncollected Garbage", "Broken Road / Pothole", "Clogged Drainage", "Non-functional Streetlight", "Contaminated Water", "Other"])

issue_details = st.text_area("Describe the local problem (Specific details, location, etc.):", key=f"details_{st.session_state.reset_counter}")

issue = f"Category: {issue_category}\nDetails: {issue_details}" if issue_category else issue_details

# 6. STEP 3: GENERATION
if st.button("🚀 1. Generate Official Letter", key=f"gen_{st.session_state.reset_counter}"):
    if "letter" in st.session_state:
        del st.session_state["letter"]
        
    if not user_name or not selected_loc or not issue.strip() or len(user_pin) != 6:
        st.error("⚠️ Please complete all fields correctly.")
    else:
        with st.spinner(f"Drafting formal petition in {target_language}..."):
            p_val = user_phone.strip()
            maps_url = st.session_state.get('maps_link', "")
            has_evidence = True if uploaded_files and len(uploaded_files) > 0 else False

            # 💡 NEW LOGIC: Force perfect civic labels for Hindi
            from_label = "प्रेषक" if "Hindi" in target_language else f"the translation of 'From' in {target_language}"
            to_label = "सेवा में" if "Hindi" in target_language else f"the translation of 'To' in {target_language}"

            system_prompt = f"""
            You are an expert bilingual civic assistant. Your task is to write a formal civic complaint letter ENTIRELY in {target_language}.
            
            CRITICAL RULE: You MUST translate or transliterate ALL English names, dates, cities, and structural elements into the native script of {target_language}. Do not leave any English words unless {target_language} is English.

            Here is the raw data for the letter:
            - Date: {current_date} (Translate the month and format appropriately for {target_language})
            - Sender Name: {user_name} (Transliterate to {target_language} script)
            - Sender Phone: {p_val}
            - Recipient Title: The Municipal Commissioner
            - City/Town: {selected_loc['Town']} (Transliterate to {target_language} script)
            - District: {selected_loc['District']} (Transliterate to {target_language} script)
            - PIN Code: {selected_loc['PIN']}
            - Issue Category & Details: {issue}
            - GPS Link Available: {maps_url}
            - Evidence Attached: {'Yes' if has_evidence else 'No'}

            FORMAT INSTRUCTIONS (Generate everything below in {target_language}):
            1. Date at the top.
            2. The "From" section (Sender name and phone). You MUST use '{from_label}' as the exact label for this section.
            3. The "To" section (Recipient title, City, District, PIN). You MUST use '{to_label}' as the exact label for this section.
            4. A clear, formal Subject line.
            5. A formal Salutation (e.g., Respected Sir/Madam).
            6. Write 2-3 professional paragraphs explaining the issue. 
               - If a GPS Link is provided, write a sentence mentioning the exact location can be tracked via the map link.
               - If Evidence Attached is 'Yes', write a sentence stating that photo/video evidence is attached to this email.
            7. A formal closing (e.g., Sincerely) and the Sender's name.
            8. The sign-off: "Supported by The Reminder India community." (Translate this phrase completely).

            ---
            FINAL RULES: 
            - Output RAW TEXT ONLY. NO markdown formatting like backticks (```) or bolding (**).
            - END WITH: 'SUGGESTED_EMAIL: ' (This specific keyword MUST remain exactly 'SUGGESTED_EMAIL:' in English, followed by the exact official email if you know it, otherwise leave blank).
            """
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": issue}]
            )
            res_content = response.choices[0].message.content.replace("```", "").strip()
            st.session_state.letter = res_content.split("SUGGESTED_EMAIL:")[0].strip()
            
            raw_email = res_content.split("SUGGESTED_EMAIL:")[1].strip() if "SUGGESTED_EMAIL:" in res_content else ""
            if "[email protected]" in raw_email:
                raw_email = ""
                
            st.session_state.sug_email = raw_email.replace("`", "").replace("'", "").strip()

# 7. STEP 4: REVIEW & MULTI-SEND
if "letter" in st.session_state:
    st.divider()
    st.subheader("📬 Step 4: Final Review & Email Controls")
    st.text_area("Letter Content:", value=st.session_state.letter, height=400, key=f"review_text_{st.session_state.reset_counter}")
    
    st.markdown("##### 📨 Email Routing")
    col_to, col_cc = st.columns(2)
    with col_to:
        rec_to = st.text_input("To (Primary Official):", value=st.session_state.sug_email, key=f"rec_to_{st.session_state.reset_counter}")
    with col_cc:
        rec_cc = st.text_input("CC (Public Copy):", value="", key=f"rec_cc_{st.session_state.reset_counter}")
        
    col_bcc, col_me = st.columns(2)
    with col_bcc:
        rec_bcc = st.text_input("BCC (Secret Archive):", value="", key=f"rec_bcc_{st.session_state.reset_counter}")
    with col_me:
        user_receipt = st.text_input("Your Email (For Receipt Copy):", value="", key=f"user_receipt_{st.session_state.reset_counter}")

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
                st.download_button("📥 Download Print PDF (With Dispatch Log)", data=pdf_bytes, file_name=f"TRI_Report_{user_pin}.pdf", mime="application/pdf", key=f"dl_pdf_{st.session_state.reset_counter}")
            else:
                st.error("Error generating PDF.")
        else:
            txt_bytes = final_download_text.encode('utf-8')
            st.download_button("📥 Download Letter (With Dispatch Log)", data=txt_bytes, file_name=f"TRI_Report_{user_pin}.txt", mime="text/plain", key=f"dl_txt_{st.session_state.reset_counter}")

    with col_btn2:
        st.caption("By clicking send, you agree to our [Privacy Policy](https://sites.google.com/view/thereminderindia/home).")
        
        if st.button("📧 Send Official Email Now", key=f"send_email_{st.session_state.reset_counter}"):
            combined_bcc_list = []
            if rec_bcc: combined_bcc_list.append(rec_bcc)
            if user_receipt: combined_bcc_list.append(user_receipt)
            final_bcc_string = ", ".join(combined_bcc_list)

            if not is_valid_email(rec_to) or not is_valid_email(rec_cc) or not is_valid_email(final_bcc_string):
                st.error("❌ Invalid email format detected.")
            elif not rec_to:
                st.error("❌ Primary Recipient (To) is required.")
            else:
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
                                        clean_filename += ext if ext else ".jpg" 
                                            
                                    part = MIMEBase(maintype, subtype)
                                    part.set_payload(file_bytes)
                                    
                                    encoders.encode_base64(part) 
                                    part.add_header('Content-Disposition', f'attachment; filename="{clean_filename}"')
                                    
                                    msg.attach(part)
                            
                            smtp = smtplib.SMTP_SSL('smtp.gmail.com', 465)
                            smtp.login(SENDER_EMAIL, APP_PASSWORD)
                            smtp.send_message(msg)
                            smtp.quit()
                            
                            st.success("✅ Official Letter Sent! Please check your email (and Spam folder) for your receipt. If the issue is not resolved in 7 days, we encourage you to follow up.")
                            st.balloons()
                        except Exception as e:
                            st.error(f"Error sending email: {e}")

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("---")
    col_spacer, col_clear = st.columns([3, 1])
    with col_clear:
        if st.button("🔄 Clear Form & Start New", key=f"clear_btn_{st.session_state.reset_counter}"):
            keys_to_delete = [k for k in st.session_state.keys() if k != 'reset_counter']
            for k in keys_to_delete:
                del st.session_state[k]
            st.session_state.reset_counter += 1
            st.rerun()