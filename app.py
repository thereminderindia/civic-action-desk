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
import json

def local_css():
    st.markdown("""
    <style>
    /* Global Styles */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', 'Noto Sans Devanagari', 'Noto Sans Bengali', sans-serif;
    }

    /* Main Container Padding */
    .main .block-container {
        padding-top: 2rem;
        max-width: 900px;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        /* Removed the hardcoded white background so it matches your theme */
        border-right: 1px solid #333333; 
    }

    /* Professional Button Styling */
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 3em;
        background-color: #1E3A8A; /* Civic Blue */
        color: white;
        border: none;
        font-weight: 600;
        transition: all 0.3s ease;
    }

    .stButton>button:hover {
        background-color: #1D4ED8;
        border: none;
        color: white;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }

    /* Secondary Action Button (Clear/Reset) */
    div[data-testid="stVerticalBlock"] > div:last-child .stButton>button {
        background-color: transparent;
        color: #ef4444;
        border: 1px solid #ef4444;
    }

    /* Input Fields */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea {
        border-radius: 10px;
        border: 1px solid #d1d5db;
    }

    /* Success/Warning Box Styling */
    .stAlert {
        border-radius: 12px;
        border: none;
    }

    /* Header Styling */
    h1 {
        color: #1E3A8A;
        font-weight: 800;
        letter-spacing: -0.02em;
    }
    
    h2, h3 {
        color: #374151;
        font-weight: 600;
    }

    /* Mobile responsiveness for the logo */
    [data-testid="stSidebarNav"]::before {
        content: "THE REMINDER INDIA";
        padding-left: 20px;
        font-family: 'Inter';
        font-weight: 800;
        font-size: 1.2rem;
        color: #1E3A8A;
    }
    </style>
    """, unsafe_allow_html=True)

# 1. SETUP & AUTHENTICATION
st.set_page_config(page_title="The Reminder India", page_icon="🏛️", layout="wide")

# Call the CSS function at the start
local_css()

# Header with Logo
col1, col2 = st.columns([1, 4])
with col1:
    # Ensure your logo is actually named 'logo.png' and is inside the 'assets' folder
    if os.path.exists("assets/logo.png"):
        st.image("assets/logo.png", width=100)
with col2:
    st.title("The Reminder India")

# --- INITIALIZE RESET COUNTER ---
if "reset_counter" not in st.session_state:
    st.session_state.reset_counter = 0

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

# --- PDF ENGINE (Updated for Unicode) ---
FONT_MAP = {
    "Hindi (हिन्दी)": "NotoSansDevanagari-Regular.ttf",
    "Bengali (বাংলা)": "NotoSansBengali_Condensed-Regular.ttf",
    # Add your other downloaded fonts here...
    "English": "NotoSans-Regular.ttf"
}

def create_pdf(text, language):
    try:
        pdf = FPDF()
        pdf.add_page()
        
        font_filename = FONT_MAP.get(language, "NotoSans-Regular.ttf")
        font_path = os.path.join("assets", font_filename)
        font_family_name = font_filename.split("-")[0].split("_")[0]
        
        if os.path.exists(font_path):
            pdf.add_font(font_family_name, style="", fname=font_path)
            pdf.set_font(font_family_name, size=11)
        else:
            pdf.set_font("Helvetica", size=11) 
            
        line_height = 6
        for line in text.split('\n'):
            if line.strip() == "":
                pdf.ln(line_height)
            elif current_date in line:
                pdf.cell(0, line_height, text=line, new_x="LMARGIN", new_y="NEXT", align='R')
            else:
                pdf.multi_cell(0, line_height, text=line, align='L')
                
        return bytes(pdf.output()) 
    except Exception as e:
        st.error(f"PDF Generation Error: {e}")
        return None

# --- AI LETTER GENERATION ENGINE ---
def generate_official_letter(user_details, issue_description, location_info, global_language, current_date, maps_url, has_evidence):
    """
    Wraps the OpenAI call using the Senior Civic Advocate persona, user dictionaries, 
    and handles the translation formatting required by the app.
    """
    from_label = "प्रेषक" if "Hindi" in global_language else f"the translation of 'From' in {global_language}"
    to_label = "सेवा में" if "Hindi" in global_language else f"the translation of 'To' in {global_language}"

    # This is the "Voice" of the app
    system_prompt = f"""
    You are a Senior Civic Advocate in India. Draft a formal petition to the Municipal Commissioner regarding a public grievance. 
    Use a professional, firm, and legalistic tone.
    
    CRITICAL RULE: You MUST translate or transliterate ALL English names, dates, cities, and structural elements into the native script of {global_language}. Do not leave any English words unless {global_language} is English.
    """
    
    # This is the "Data" from the user mapped to formatting rules
    user_prompt = f"""
    Here is the raw data for the letter:
    - Date: {current_date}
    - Reporter Name: {user_details['name']}
    - Reporter Phone: {user_details['phone']}
    - Recipient Title: The Municipal Commissioner
    - Location: {location_info['town']}, District: {location_info['district']}, PIN: {location_info['pin']}
    - Issue Category: {user_details['category']}
    - Description of Issue: {issue_description['text']}
    - GPS Link Available: {maps_url}
    - Evidence Attached: {'Yes' if has_evidence else 'No'}

    FORMAT INSTRUCTIONS (Generate everything below in {global_language}):
    1. Date at the top.
    2. The "From" section (Sender name and phone). You MUST use '{from_label}' as the exact label for this section.
    3. The "To" section (Recipient title, City, District, PIN). You MUST use '{to_label}' as the exact label for this section.
    4. A clear, formal Subject line.
    5. A formal Salutation (e.g., Respected Sir/Madam).
    6. Write a full letter with 2-3 professional paragraphs explaining the issue. Include a strong 7-day resolution demand.
    7. A formal closing (e.g., Sincerely) and the Sender's name.
    8. The sign-off: "Supported by The Reminder India community." 

    FINAL RULES: 
    - Output RAW TEXT ONLY. NO markdown formatting like backticks (```) or bolding (**).
    - END WITH: 'SUGGESTED_EMAIL: ' (This specific keyword MUST remain exactly 'SUGGESTED_EMAIL:' in English, followed by the exact official email if you know it, otherwise leave blank).
    """
    
    # Call the AI model
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt}, 
            {"role": "user", "content": user_prompt}
        ]
    )
    return response.choices[0].message.content


# --- LOCAL TRANSLATION ENGINE FOR UI ---
@st.cache_data
def get_translated_ui(language):
    lang_map = {
        "English": "en_slides.json",
        "Hindi (हिन्दी)": "hi_slides.json",
        "Bengali (বাংলা)": "bn_slides.json",
        "Marathi (मराठी)": "mr_slides.json",
        "Telugu (తెలుగు)": "te_slides.json",
        "Tamil (தமிழ்)": "ta_slides.json",
        "Gujarati (ગુજરાતી)": "gu_slides.json",
        "Urdu (اردو)": "ur_slides.json",
        "Kannada (ಕನ್ನಡ)": "kn_slides.json",
        "Odia (ଓଡ଼ିଆ)": "or_slides.json",
        "Malayalam (മലയാളം)": "ml_slides.json",
        "Punjabi (ਪੰਜਾਬੀ)": "pa_slides.json",
        "Assamese (অসমীয়া)": "as_slides.json",
        "Maithili (मैथिली)": "mai_slides.json",
        "Santali (संताली)": "sat_slides.json",
        "Kashmiri (کأشُر)": "ks_slides.json",
        "Nepali (नेपाली)": "ne_slides.json",
        "Konkani (कोंकणी)": "kok_slides.json",
        "Sindhi (سنڌي)": "sd_slides.json",
        "Dogri (डोगरी)": "doi_slides.json",
        "Manipuri (মণিপুরী)": "mni_slides.json",
        "Bodo (बर')": "brx_slides.json",
        "Sanskrit (संस्कृतम्)": "sa_slides.json"
    }
    file_key = lang_map.get(language, "en")
    file_path = os.path.join("locales", f"{file_key}.json")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        try:
             with open(os.path.join("locales", "en.json"), 'r', encoding='utf-8') as f:
                 return json.load(f)
        except FileNotFoundError:
             st.error("Critical Error: Core UI translation file (en.json) missing from locales folder.")
             return {}

# --- LOCAL TRANSLATION ENGINE FOR SLIDESHOW ---
@st.cache_data
def get_translated_slides(language):
    lang_map = {
        "English": "en_slides.json",
        "Hindi (हिन्दी)": "hi_slides.json",
        "Bengali (বাংলা)": "bn_slides.json",
        "Marathi (मराठी)": "mr_slides.json",
        "Telugu (తెలుగు)": "te_slides.json",
        "Tamil (தமிழ்)": "ta_slides.json",
        "Gujarati (ગુજરાતી)": "gu_slides.json",
        "Urdu (اردو)": "ur_slides.json",
        "Kannada (ಕನ್ನಡ)": "kn_slides.json",
        "Odia (ଓଡ଼ିଆ)": "or_slides.json",
        "Malayalam (മലയാളം)": "ml_slides.json",
        "Punjabi (ਪੰਜਾਬੀ)": "pa_slides.json",
        "Assamese (অসমীয়া)": "as_slides.json",
        "Maithili (मैथिली)": "mai_slides.json",
        "Santali (संताली)": "sat_slides.json",
        "Kashmiri (کأشُر)": "ks_slides.json",
        "Nepali (नेपाली)": "ne_slides.json",
        "Konkani (कोंकणी)": "kok_slides.json",
        "Sindhi (سنڌي)": "sd_slides.json",
        "Dogri (डोगरी)": "doi_slides.json",
        "Manipuri (মণিপুরী)": "mni_slides.json",
        "Bodo (बर')": "brx_slides.json",
        "Sanskrit (संस्कृतम्)": "sa_slides.json"
    }
    file_key = lang_map.get(language, "en_slides")
    file_path = os.path.join("locales", f"{file_key}.json")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        try:
             with open(os.path.join("locales", "en_slides.json"), 'r', encoding='utf-8') as f:
                 return json.load(f)
        except FileNotFoundError:
             return []


# 3. INTERFACE & SIDEBAR
st.markdown("""
    <style>
        div[data-testid="InputInstructions"] {
            display: none !important;
        }
    </style>
""", unsafe_allow_html=True)

st.sidebar.subheader("🌐 App Settings / ऐप सेटिंग्स")
global_language = st.sidebar.selectbox("Select Language:", options=
    ["English", "Hindi (हिन्दी)", "Bengali (বাংলা)", "Marathi (मराठी)", 
     "Telugu (తెలుగు)", "Tamil (தமிழ்)", "Gujarati (ગુજરાતી)", 
     "Urdu (اردو)", "Kannada (କನ್ನಡ)", "Odia (ଓଡ଼ିଆ)", 
     "Malayalam (മലയാളം)", "Punjabi (ਪੰਜਾਬੀ)", "Assamese (অসমੀয়া)", 
     "Maithili (मैथिली)", "Santali (संताली)", "Kashmiri (کٲशُر)", 
     "Nepali (नेपाली)", "Konkani (कोंकਣੀ)", "Sindhi (سنڌي)", 
     "Dogri (डोगरी)", "Manipuri (মৈতৈলোন)", "Bodo (बर')", "Sanskrit (संस्कृतम्)"])

# LOAD LOCAL TRANSLATED UI DICTIONARY
ui = get_translated_ui(global_language)

# Guard clause in case UI fails to load
if not ui:
    st.stop()

st.sidebar.markdown("---")
st.sidebar.subheader(ui.get("connect", "Connect"))
st.sidebar.link_button("📺 YouTube", "[https://youtube.com/@TheReminderIndia](https://youtube.com/@TheReminderIndia)")
st.sidebar.link_button("🔵 Facebook", "[https://facebook.com/TheReminderIndia](https://facebook.com/TheReminderIndia)")
st.sidebar.link_button("📸 Instagram", "[https://instagram.com/TheReminderIndia](https://instagram.com/TheReminderIndia)")

search_container = st.sidebar.container()

st.sidebar.markdown("---")
st.sidebar.subheader(ui.get("tools", "Tools"))
st.sidebar.link_button("🔍 Pincode Verify", "[https://www.indiapost.gov.in/VAS/Pages/findpincode.aspx](https://www.indiapost.gov.in/VAS/Pages/findpincode.aspx)")
st.sidebar.markdown("---")
st.sidebar.caption(ui.get("legal", "Legal"))
st.sidebar.link_button("📄 Privacy Policy", "[https://sites.google.com/view/httpsthereminderindia-streamli/home](https://sites.google.com/view/httpsthereminderindia-streamli/home)")

pincode_df = load_pincode_db()

# --- HEADER BLOCK ---
col_text, col_img = st.columns([6, 4], gap="large")

with col_text:
    st.markdown(f"## {ui.get('header_title', '')}")
    st.markdown(f"{ui.get('header_desc', '')}")
    st.markdown(f"**{ui.get('header_special', '')}** {ui.get('header_special_desc', '')}")
    st.markdown(f"*{ui.get('header_action', '')}*")
    
with col_img:
    # We changed the name here to force Streamlit to load it fresh!
    banner_path = os.path.join("assets", "main_banner.png")
    
    if os.path.exists(banner_path):
        try:
            st.image(banner_path, use_container_width=True)
        except Exception as e:
            st.error(f"Image found, but couldn't be loaded. Error: {e}")
    else:
        st.info("Banner image not found. Please ensure 'main_banner.png' is in the 'assets' folder.")
        
st.markdown("<br>", unsafe_allow_html=True)

# --- INTERACTIVE APP TUTORIAL (SLIDESHOW) ---
st.markdown("---")

with st.expander(ui.get("tutorial_expander", "Tutorial"), expanded=False):
    if "slide_idx" not in st.session_state:
        st.session_state.slide_idx = 0

    tutorial_slides = get_translated_slides(global_language)

    slide_container = st.container(border=True)
    
    if tutorial_slides:
        current_slide = tutorial_slides[st.session_state.slide_idx]
        col_img_slide, col_text_slide = st.columns([1.2, 1], gap="large")
        
        with col_img_slide:
            if os.path.exists(current_slide["image"]):
                st.image(current_slide["image"], use_container_width=True)
            else:
                st.warning(f"⚠️ Missing image: {current_slide['image']}")
                
        with col_text_slide:
            st.markdown(f"### {current_slide['title']}")
            st.write(current_slide["text"])
            st.markdown("<br>", unsafe_allow_html=True)
            st.caption(f"**Step {st.session_state.slide_idx + 1} of {len(tutorial_slides)}**")

        st.markdown("<hr style='margin: 1em 0;'>", unsafe_allow_html=True)
        nav_spacer, nav_prev, nav_next = st.columns([4, 1, 1])
        
        with nav_prev:
            if st.button("⬅️ Back", disabled=(st.session_state.slide_idx == 0), use_container_width=True):
                st.session_state.slide_idx -= 1
                st.rerun()
                
        with nav_next:
            if st.session_state.slide_idx < len(tutorial_slides) - 1:
                if st.button("Next ➡️", use_container_width=True):
                    st.session_state.slide_idx += 1
                    st.rerun()
            else:
                if st.button("✅ Finish", use_container_width=True):
                    st.session_state.slide_idx = 0
                    st.toast("🎉 Tutorial complete! You are ready to start. Close this panel to begin.")
                    st.rerun()

# 4. STEP 1: LOCATION DETAILS
st.markdown("---")
st.subheader(ui.get("step1", "Step 1"))
pin_col, details_col = st.columns([2, 4])

with pin_col:
    user_pin = st.text_input(ui.get("pin", "PIN"), value="", max_chars=6, key=f"pin_{st.session_state.reset_counter}")
    if user_pin and (not user_pin.isdigit() or len(user_pin) != 6):
        st.error("⚠️ Pincode must be exactly 6 digits.")

selected_loc = None
if user_pin and len(user_pin) == 6 and pincode_df is not None:
    matches = pincode_df[pincode_df['pincode'] == str(user_pin)]
    if not matches.empty:
        with details_col:
            office_list = matches['officename'].unique().tolist()
            chosen_office = st.selectbox(ui.get("town", "Town"), office_list, key=f"office_{st.session_state.reset_counter}")
            row = matches[matches['officename'] == chosen_office].iloc[0]
            selected_loc = {"Town": row['officename'], "District": row['district'], "State": row['circlename'], "PIN": user_pin}
            st.success(f"✅ Area: {selected_loc['Town']}, {selected_loc['District']}")

col_gps, col_files = st.columns(2)
with col_gps:
    if st.button(ui.get("gps", "GPS"), key=f"gps_{st.session_state.reset_counter}"):
        loc = streamlit_js_eval(data_key='pos', func_name='getCurrentPosition', want_output=True)
        if loc:
            lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
            st.session_state.maps_link = f"[https://www.google.com/maps/dir/?api=1&destination=](https://www.google.com/maps/dir/?api=1&destination=){lat},{lon}&travelmode=driving"
            st.success(f"✅ GPS Captured! Navigation Link generated.")

with col_files:
    uploaded_files = st.file_uploader(ui.get("evidence", "Evidence"), accept_multiple_files=True, key=f"evidence_{st.session_state.reset_counter}")
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

# 5. STEP 2: REPORTER DETAILS  
st.markdown("---")
st.subheader(ui.get("step2", "Step 2"))
user_name = st.text_input(ui.get("name", "Name"), key=f"sender_name_{st.session_state.reset_counter}")

user_phone = st.text_input(ui.get("phone", "Phone"), max_chars=10, key=f"sender_phone_{st.session_state.reset_counter}")
if user_phone:
    if not user_phone.isdigit():
        st.error("⚠️ Phone number must contain numbers only.")
    elif len(user_phone) < 10:
        st.warning("⚠️ Please enter the full 10-digit number.")

issue_category = st.selectbox(ui.get("category", "Category"), key=f"category_{st.session_state.reset_counter}", options=
    ["", "Uncollected Garbage", "Broken Road / Pothole", "Clogged Drainage", "Non-functional Streetlight", "Contaminated Water", "Other"])

issue_details = st.text_area(ui.get("desc", "Description"), key=f"details_{st.session_state.reset_counter}")

if selected_loc:
    dept_keywords = "Municipal Commissioner OR Nagar Palika"
    if issue_category == "Uncollected Garbage":
        dept_keywords = "Nagar Nigam OR Municipal Corporation Sanitation"
    elif issue_category == "Broken Road / Pothole":
        dept_keywords = "PWD Executive Engineer OR Municipal Corporation"
    elif issue_category == "Clogged Drainage":
        dept_keywords = "Sanitary Inspector OR Nagar Nigam"
    elif issue_category == "Non-functional Streetlight":
        dept_keywords = "Electricity Department OR Junior Engineer JE"
    elif issue_category == "Contaminated Water":
        dept_keywords = "Water Supply Department OR Jal Board"

    search_query = f"official email {dept_keywords} {selected_loc['Town']} {selected_loc['District']} site:.gov.in OR site:.nic.in"
    google_url = f"[https://www.google.com/search?q=](https://www.google.com/search?q=){urllib.parse.quote(search_query)}"
    
    with search_container:
        st.markdown("---")
        st.subheader(ui.get("find_email", "Find Email"))
        st.link_button(f"🌐 Search for {selected_loc['Town']} Email", google_url)

issue_parts = []
if issue_category and issue_category != "Other":
    issue_parts.append(f"Main Problem Category: {issue_category}")
if issue_details.strip():
    issue_parts.append(f"Specific Details, Landmarks & Extra Info: {issue_details.strip()}")

issue = "\n\n".join(issue_parts)

# 6. STEP 3: GENERATION
if st.button(ui.get("gen_btn", "Generate"), key=f"gen_{st.session_state.reset_counter}"):
    if "letter" in st.session_state:
        del st.session_state["letter"]
        
    if not user_name or not selected_loc or not issue.strip() or len(user_pin) != 6:
        st.error("⚠️ Please complete all fields correctly.")
    else:
        with st.spinner(f"Drafting formal petition in {global_language}..."):
            p_val = user_phone.strip()
            maps_url = st.session_state.get('maps_link', "")
            has_evidence = True if uploaded_files and len(uploaded_files) > 0 else False

            # Package the user data into the requested dictionaries
            user_details_dict = {"name": user_name, "phone": p_val, "category": issue_category}
            issue_description_dict = {"text": issue}
            location_info_dict = {"town": selected_loc['Town'], "district": selected_loc['District'], "pin": selected_loc['PIN']}

            try:
                # --- CALL THE NEW FUNCTION HERE ---
                res_content = generate_official_letter(
                    user_details=user_details_dict, 
                    issue_description=issue_description_dict, 
                    location_info=location_info_dict,
                    global_language=global_language,
                    current_date=current_date,
                    maps_url=maps_url,
                    has_evidence=has_evidence
                )
                
                res_content = res_content.replace("```", "").strip()
                st.session_state.letter = res_content.split("SUGGESTED_EMAIL:")[0].strip()
                
                raw_email = res_content.split("SUGGESTED_EMAIL:")[1].strip() if "SUGGESTED_EMAIL:" in res_content else ""
                if "[email protected]" in raw_email:
                    raw_email = ""
                    
                st.session_state.sug_email = raw_email.replace("`", "").replace("'", "").strip()
            except Exception as e:
                st.error(f"Error generating text: {e}")

# 7. STEP 4: REVIEW & MULTI-SEND
if "letter" in st.session_state:
    st.divider()
    st.subheader(ui.get("step4", "Step 4"))
    
    st.markdown(f"##### {ui.get('letter_content', 'Letter Content')}")
    st.info(st.session_state.letter) 
    
    with st.expander("✏️ Want to make manual edits? Click here."):
        edited_letter = st.text_area("Edit your letter:", value=st.session_state.letter, height=250, label_visibility="collapsed")
        if st.button("💾 Save Changes", key="save_edits"):
            st.session_state.letter = edited_letter
            st.rerun()
            
    st.markdown(f"##### {ui.get('email_routing', 'Email Routing')}")
    
    if not st.session_state.sug_email:
        st.warning(ui.get("email_missing_warning", "Email missing warning"))

    col_to, col_cc = st.columns(2)
    with col_to:
        rec_to = st.text_input(ui.get("to", "To"), value=st.session_state.sug_email, key=f"rec_to_{st.session_state.reset_counter}")
    with col_cc:
        rec_cc = st.text_input(ui.get("cc", "CC"), value="", key=f"rec_cc_{st.session_state.reset_counter}")
        
    col_bcc, col_me = st.columns(2)
    with col_bcc:
        rec_bcc = st.text_input(ui.get("bcc", "BCC"), value="", key=f"rec_bcc_{st.session_state.reset_counter}")
    with col_me:
        user_receipt = st.text_input(ui.get("receipt", "Receipt"), value="", key=f"user_receipt_{st.session_state.reset_counter}")

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
        if global_language == "English":
            pdf_bytes = create_pdf(final_download_text, global_language)
            if pdf_bytes:
                st.download_button(ui.get("dl_pdf", "Download PDF"), data=pdf_bytes, file_name=f"TRI_Report_{user_pin}.pdf", mime="application/pdf", key=f"dl_pdf_{st.session_state.reset_counter}")
            else:
                st.error("Error generating PDF.")
        else:
            txt_bytes = final_download_text.encode('utf-8')
            st.download_button(ui.get("dl_txt", "Download TXT"), data=txt_bytes, file_name=f"TRI_Report_{user_pin}.txt", mime="text/plain", key=f"dl_txt_{st.session_state.reset_counter}")
        
        st.caption("💡 **Want to post on Facebook or Instagram?** Download the letter above and attach it directly to your post!")

    with col_btn2:
        st.caption("By clicking send, you agree to our Privacy Policy.")
        
        if st.button(ui.get("send_btn", "Send"), key=f"send_email_{st.session_state.reset_counter}"):
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
                            
                            st.success("✅ Official Letter Sent! Please check your email (and Spam folder) for your receipt.")
                            st.balloons()
                        except Exception as e:
                            st.error(f"Error sending email: {e}")

    # --- MULTI-WHATSAPP ROUTING ---
    st.markdown("---")
    st.markdown(f"##### {ui.get('wa_routing', 'WA Routing')}")
    st.caption(ui.get("wa_instruction", ""))
    
    wa_numbers_input = st.text_input(ui.get("wa_num", "WA Num"), key=f"wa_multi_{st.session_state.reset_counter}")
    
    if wa_numbers_input:
        raw_numbers = [num.strip() for num in wa_numbers_input.split(',')]
        valid_numbers = []
        invalid_numbers = []
        
        for num in raw_numbers:
            if num.isdigit() and len(num) == 10:
                valid_numbers.append(num)
            elif num:
                invalid_numbers.append(num)
        
        if invalid_numbers:
            st.error(f"⚠️ These numbers are invalid (must be exactly 10 digits): {', '.join(invalid_numbers)}")
        
        if valid_numbers:
            encoded_letter = urllib.parse.quote(st.session_state.letter)
            btn_cols = st.columns(min(len(valid_numbers), 3)) 
            
            for i, num in enumerate(valid_numbers):
                wa_link = f"https://wa.me/91{num}?text={encoded_letter}"
                with btn_cols[i % 3]:
                    st.link_button(f"🟢 Send to {num}", wa_link, use_container_width=True)

    # --- SOCIAL MEDIA AMPLIFICATION (X / TWITTER) ---
    st.markdown("---")
    st.markdown(f"##### {ui.get('x_routing', 'X Routing')}")
    
    tw_handle = st.text_input(ui.get("x_handle", "X Handle"), value="@", key=f"tw_handle_{st.session_state.reset_counter}")
    
    display_category = issue_category if issue_category else "Local Infrastructure"
    tweet_text = f"🚨 Civic Alert: {selected_loc['Town']}, PIN {selected_loc['PIN']}\n"
    tweet_text += f"Issue: {display_category}\n\n"
    
    if tw_handle and tw_handle.strip() != "@":
        tweet_text += f"{tw_handle.strip()} Please take urgent action on this matter.\n\n"
        
    tweet_text += "#CivicAction #TheReminderIndia"
    
    encoded_tweet = urllib.parse.quote(tweet_text)
    tw_link = f"https://twitter.com/intent/tweet?text={encoded_tweet}"
    
    st.link_button(ui.get("x_btn", "Post to X"), tw_link, use_container_width=True)

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("---")
    col_spacer, col_clear = st.columns([3, 1])
    with col_clear:
        if st.button(ui.get("clear_btn", "Clear"), key=f"clear_btn_{st.session_state.reset_counter}"):
            keys_to_delete = [k for k in st.session_state.keys() if k != 'reset_counter']
            for k in keys_to_delete:
                del st.session_state[k]
            st.session_state.reset_counter += 1
            st.rerun()