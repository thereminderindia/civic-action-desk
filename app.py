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
        
        # Set a normal line height (6 is standard single-spacing for 11pt font)
        line_height = 6
        
        for line in text.split('\n'):
            if line.strip() == "":
                # When the AI creates a paragraph break (an empty line), 
                # this adds a perfectly sized blank space in the PDF
                pdf.ln(line_height)
            elif current_date in line:
                # Keep the date neatly aligned to the right
                pdf.cell(0, line_height, txt=line, ln=True, align='R')
            else:
                # Print standard text with natural text-wrapping
                pdf.multi_cell(0, line_height, txt=line, align='L')
                
        return pdf.output(dest='S').encode('latin-1', 'ignore')
    except Exception as e:
        return None

# --- AI TRANSLATION ENGINE FOR UI ---
@st.cache_data(show_spinner=False)
def get_translated_ui(language):
    base_ui = {
        "app_settings": "🌐 App Settings",
        "connect": "📲 Connect with TRI",
        "tools": "🛠️ Tools",
        "legal": "⚖️ Legal & Trust",
        "header_title": "🏛️ Speak Up. We’ll Handle the Draft.",
        "header_desc": "The Reminder India is your AI-powered civic assistant, bridging the gap between local problems and official solutions.",
        "header_special": "What makes us special?",
        "header_special_desc": "We transform simple descriptions into powerful, formal petitions instantly. Draft in your native language, attach GPS evidence, and route complaints directly to authorities via Email, WhatsApp, or X.",
        "header_action": "Don't just complain. Demand accountability.",
        "tutorial_expander": "📖 First time here? View the step-by-step guide",
        "step1": "📍 Step 1: Location Details",
        "pin": "Enter 6-Digit PIN:",
        "town": "Confirm Town/City:",
        "find_email": "🔍 Find Official Email",
        "gps": "🛰️ Capture Exact GPS",
        "evidence": "Attach Evidence (Photos/Videos):",
        "step2": "📝 Step 2: Reporter Details",
        "name": "Full Name (Sender):",
        "phone": "Contact Number (Optional):",
        "category": "Quick Issue Select (Optional):",
        "desc": "Describe the local problem (Specific details, location, etc.):",
        "gen_btn": "🚀 1. Generate Official Letter",
        "step4": "📬 Step 4: Final Review & Email Controls",
        "letter_content": "Letter Content:",
        "email_routing": "📨 Email Routing",
        "email_missing_warning": "⚠️ We couldn't auto-find the official email for this location. Please enter it manually or use the '🔍 Find Official Email' tool in the left sidebar to search Google!",
        "to": "To (Primary Official):",
        "cc": "CC (Public Copy):",
        "bcc": "BCC (Secret Archive):",
        "receipt": "Your Email (For Receipt Copy):",
        "dl_pdf": "📥 Download Print PDF",
        "dl_txt": "📥 Download Letter",
        "send_btn": "📧 Send Official Email Now",
        "wa_routing": "🟢 WhatsApp Routing (Direct Message)",
        "wa_instruction": "If you know the official WhatsApp numbers for your local departments, enter them below separated by commas (e.g., 9876543210, 8877665544).",
        "wa_num": "Official 10-Digit WhatsApp Number(s):",
        "x_routing": "🐦 Public Amplification (X / Twitter)",
        "x_handle": "Official's X Handle (e.g., @KandhlaPalika):",
        "x_btn": "🐦 Post Summary to X (Twitter)",
        "clear_btn": "🔄 Clear Form & Start New"
    }
    
    if language == "English":
        return base_ui

    with st.spinner(f"🌐 Translating App Interface to {language}..."):
        try:
            sys_prompt = f"You are a professional software localization expert. Translate the values of the provided JSON object into {language}. Keep emojis intact. Return a valid JSON object."
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": json.dumps(base_ui)}
                ],
                response_format={ "type": "json_object" } 
            )
            translated_ui = json.loads(response.choices[0].message.content)
            
            # Ensure all keys exist in case AI missed one
            for key in base_ui:
                if key not in translated_ui:
                    translated_ui[key] = base_ui[key]
            return translated_ui
        except Exception as e:
            return base_ui


# --- AI TRANSLATION ENGINE FOR SLIDESHOW ---
@st.cache_data(show_spinner=False)
def get_translated_slides(language):
    base_slides = [
        {"image": "1st.png", "title": "Welcome to The Reminder India", "text": "Welcome to the ultimate civic action tool. Getting started is easy: just open your browser on any device and visit thereminderindia.streamlit.app. No downloads required. Let's draft your first official complaint!"},
        {"image": "2.png", "title": "Step 1: Speak Your Language", "text": "We believe you shouldn't need to be fluent in formal English to demand action. Click the 'Select Language' dropdown in the sidebar. Choose from Hindi, Bengali, Tamil, Marathi, and over a dozen other native languages. Our AI will automatically translate and format your letter perfectly."},
        {"image": "3.png", "title": "Step 1: Enter Your PIN", "text": "Type in the 6-digit PIN code of the area where the problem is located. The system will automatically search our national post office database to find the relevant local authorities."},
        {"image": "4.png", "title": "Step 1: Target the Exact Municipality", "text": "Select the exact Town/City from the 'Confirm' dropdown. This step is crucial to ensure your final letter is addressed to the correct local municipal commissioner."},
        {"image": "6.png", "title": "Step 1: Lock in the Coordinates", "text": "Once you see the green confirmation box, your location is set! \n\n**Pro Tip:** Standing right next to the pothole or broken streetlight? Click 'Capture Exact GPS' on your mobile device to attach a Google Maps link directly inside your complaint letter."},
        {"image": "7.png", "title": "Step 1: Show, Don't Just Tell", "text": "Words are good, but pictures demand action. Use the 'Attach Evidence' box to upload photos or short video clips of the issue (up to 20MB). These files will be securely attached to the final email sent to the authorities."},
        {"image": "8.png", "title": "Step 2: Reporter Details", "text": "Now, tell us who is sending the letter. Enter your Full Name so the petition can be formally signed. Your Contact Number is optional, but highly recommended so officials can reach you directly if they need more details about the issue."},
        {"image": "9.png", "title": "Step 2: Categorize the Problem", "text": "Use the 'Quick Issue Select' dropdown to categorize the problem. Options include Uncollected Garbage, Broken Roads, Clogged Drainage, and more. Don't see your specific issue? Just select 'Other' or leave it blank—our AI is smart enough to figure it out from your description!"},
        {"image": "10.png", "title": "Step 2: Describe the Issue Naturally", "text": "This is where the magic happens. You don't need to write a formal letter here. Just type out the specific details naturally. Tell the AI exactly where the problem is (like nearby landmarks). When you're ready, click 'Generate Official Letter' and watch the AI instantly turn your simple text into a powerful, formal petition!"},
        {"image": "11.png", "title": "Step 4: Review Your Formal Petition", "text": "Within seconds, your simple description is transformed into a highly professional, fully formatted civic petition. Notice how the AI automatically includes the correct date, a strong subject line, formal salutations, and weaves your specific landmarks directly into the text. Need to make a tweak? You can use the edit button to make changes before sending!"},
        {"image": "12.png", "title": "Step 4: Route & Dispatch Your Complaint", "text": "We don't just write the letter; we deliver it. The AI will attempt to suggest the official's email automatically, but you can paste the exact To, CC, and BCC addresses here. Enter your own email to get a receipt copy! \n\nClick 'Send Official Email Now' to dispatch it instantly via our secure servers, OR click 'Download Print PDF' if you want a physical copy."},
        {"image": "13.png", "title": "Direct WhatsApp Routing", "text": "Many modern municipal departments now use WhatsApp for grievance redressal. Simply type in the 10-digit official WhatsApp number. Click the generated green button, and your entire formal letter will be instantly copied into your personal WhatsApp app, ready to send directly to the official!"},
        {"image": "14.png", "title": "Public Amplification on X (Twitter)", "text": "Sometimes, public visibility is the fastest way to get things fixed. Enter the official X/Twitter handle of your local authority. Click the button, and the app will generate a punchy, character-limit-friendly summary of your issue, complete with hashtags, ready for you to post and apply public pressure."},
        {"image": "16.png", "title": "Your Toolkit & Starting Fresh", "text": "Look at the left sidebar at any time for helpful tools. Don't know the official's email? Click the search link to automatically run a targeted Google search for government contacts in your area. \n\nDone with your complaint? Hit the blue 'Clear Form & Start New' button at the bottom of the page to securely wipe your data and start a brand new report!"}
    ]

    if language == "English":
        return base_slides

    with st.spinner(f"🌐 Translating setup guide to {language}..."):
        try:
            text_only_slides = [{"id": i, "title": s["title"], "text": s["text"]} for i, s in enumerate(base_slides)]
            
            sys_prompt = f"You are a professional translator. Translate the 'title' and 'text' values of the provided JSON array into {language}. Return a valid JSON object with a single root key called 'slides' containing the translated array."
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": json.dumps({"slides": text_only_slides})}
                ],
                response_format={ "type": "json_object" } 
            )
            
            translated_data = json.loads(response.choices[0].message.content)
            
            translated_slides = []
            for i, trans_slide in enumerate(translated_data["slides"]):
                translated_slides.append({
                    "image": base_slides[i]["image"],
                    "title": trans_slide["title"],
                    "text": trans_slide["text"]
                })
            return translated_slides
            
        except Exception as e:
            return base_slides


# 3. INTERFACE & SIDEBAR
st.set_page_config(page_title="The Reminder India", page_icon="🏛️", layout="wide")

# --- CUSTOM CSS (Cleaned up to only hide the instructions, allowing Streamlit to naturally space the sidebar) ---
st.markdown("""
    <style>
        div[data-testid="InputInstructions"] {
            display: none !important;
        }
    </style>
""", unsafe_allow_html=True)

# Determine global language FIRST
st.sidebar.subheader("🌐 App Settings / ऐप सेटिंग्स")
global_language = st.sidebar.selectbox("Select Language:", options=
    ["English", "Hindi (हिन्दी)", "Bengali (বাংলা)", "Marathi (मराठी)", 
     "Telugu (తెలుగు)", "Tamil (தமிழ்)", "Gujarati (ગુજરાતી)", 
     "Urdu (اردو)", "Kannada (କನ್ನಡ)", "Odia (ଓଡ଼ିଆ)", 
     "Malayalam (മലയാളം)", "Punjabi (ਪੰਜਾਬੀ)", "Assamese (অসমੀয়া)", 
     "Maithili (मैथिली)", "Santali (संताली)", "Kashmiri (کٲशُر)", 
     "Nepali (नेपाली)", "Konkani (कोंकਣੀ)", "Sindhi (سنڌي)", 
     "Dogri (डोगरी)", "Manipuri (মৈতৈলোন)", "Bodo (बर')", "Sanskrit (संस्कृतम्)"])

# LOAD TRANSLATED UI DICTIONARY
ui = get_translated_ui(global_language)

st.sidebar.markdown("---")
st.sidebar.subheader(ui["connect"])
st.sidebar.link_button("📺 YouTube", "https://youtube.com/@TheReminderIndia")
st.sidebar.link_button("🔵 Facebook", "https://facebook.com/TheReminderIndia")
st.sidebar.link_button("📸 Instagram", "https://instagram.com/TheReminderIndia")

# --- NEW: DYNAMIC SEARCH CONTAINER PLACED HERE ---
# By creating a container here, we reserve this exact spot in the sidebar. 
# We will populate it with the search button later in the code after the user has selected their location and issue!
search_container = st.sidebar.container()
# ------------------------------------------------

st.sidebar.markdown("---")
st.sidebar.subheader(ui["tools"])
st.sidebar.link_button("🔍 Pincode Verify", "https://www.indiapost.gov.in/VAS/Pages/findpincode.aspx")
st.sidebar.markdown("---")
st.sidebar.caption(ui["legal"])
st.sidebar.link_button("📄 Privacy Policy", "https://sites.google.com/view/httpsthereminderindia-streamli/home")

pincode_df = load_pincode_db()

# --- HEADER BLOCK (Fixed HTML Issue) ---
col_text, col_img = st.columns([6, 4], gap="large")

with col_text:
    st.markdown(f"## {ui['header_title']}")
    st.markdown(f"{ui['header_desc']}")
    st.markdown(f"**{ui['header_special']}** {ui['header_special_desc']}")
    st.markdown(f"*{ui['header_action']}*")
    
with col_img:
    if os.path.exists("banner.jpg"):
        st.image("banner.jpg", use_container_width=True)
    else:
        st.info("Banner image not found. Please ensure 'banner.jpg' is uploaded to your repository.")
        
st.markdown("<br>", unsafe_allow_html=True)

# --- INTERACTIVE APP TUTORIAL (SLIDESHOW) ---
st.markdown("---")

with st.expander(ui["tutorial_expander"], expanded=False):
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
                st.warning(f"⚠️ Missing image: {current_slide['image']}. Please ensure this exact file name is uploaded to your GitHub repository.")
                
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
            # Check if we are on the final slide to show the Finish button
            if st.session_state.slide_idx < len(tutorial_slides) - 1:
                if st.button("Next ➡️", use_container_width=True):
                    st.session_state.slide_idx += 1
                    st.rerun()
            else:
                if st.button("✅ Finish", use_container_width=True):
                    # Reset the slideshow index to the beginning
                    st.session_state.slide_idx = 0
                    st.toast("🎉 Tutorial complete! You are ready to start. Close this panel to begin.")
                    st.rerun()
# --------------------------------------------

# 4. STEP 1: LOCATION DETAILS
st.markdown("---")
st.subheader(ui["step1"])
pin_col, details_col = st.columns([2, 4])

with pin_col:
    user_pin = st.text_input(ui["pin"], value="", max_chars=6, key=f"pin_{st.session_state.reset_counter}")
    if user_pin and (not user_pin.isdigit() or len(user_pin) != 6):
        st.error("⚠️ Pincode must be exactly 6 digits.")

selected_loc = None
if user_pin and len(user_pin) == 6 and pincode_df is not None:
    matches = pincode_df[pincode_df['pincode'] == str(user_pin)]
    if not matches.empty:
        with details_col:
            office_list = matches['officename'].unique().tolist()
            chosen_office = st.selectbox(ui["town"], office_list, key=f"office_{st.session_state.reset_counter}")
            row = matches[matches['officename'] == chosen_office].iloc[0]
            selected_loc = {"Town": row['officename'], "District": row['district'], "State": row['circlename'], "PIN": user_pin}
            st.success(f"✅ Area: {selected_loc['Town']}, {selected_loc['District']}")

# --- THE BULLETPROOF MOBILE UPLOADER ---
col_gps, col_files = st.columns(2)
with col_gps:
    if st.button(ui["gps"], key=f"gps_{st.session_state.reset_counter}"):
        loc = streamlit_js_eval(data_key='pos', func_name='getCurrentPosition', want_output=True)
        if loc:
            lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
            st.session_state.maps_link = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}&travelmode=driving"
            st.success(f"✅ GPS Captured! Navigation Link generated.")

with col_files:
    uploaded_files = st.file_uploader(ui["evidence"], accept_multiple_files=True, key=f"evidence_{st.session_state.reset_counter}")
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
st.subheader(ui["step2"])
user_name = st.text_input(ui["name"], key=f"sender_name_{st.session_state.reset_counter}")

user_phone = st.text_input(ui["phone"], max_chars=10, key=f"sender_phone_{st.session_state.reset_counter}")
if user_phone:
    if not user_phone.isdigit():
        st.error("⚠️ Phone number must contain numbers only.")
    elif len(user_phone) < 10:
        st.warning("⚠️ Please enter the full 10-digit number.")

issue_category = st.selectbox(ui["category"], key=f"category_{st.session_state.reset_counter}", options=
    ["", "Uncollected Garbage", "Broken Road / Pothole", "Clogged Drainage", "Non-functional Streetlight", "Contaminated Water", "Other"])

issue_details = st.text_area(ui["desc"], key=f"details_{st.session_state.reset_counter}")


# --- POPULATE THE DYNAMIC SIDEBAR SEARCH CONTAINER ---
# Now that we know BOTH the Location (Step 1) and the Issue Category (Step 2),
# we can safely populate the sidebar container we created earlier!
if selected_loc:
    # 1. Determine the right department keywords based on the user's selected issue
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

    # 2. Build the highly targeted Google search URL
    search_query = f"official email {dept_keywords} {selected_loc['Town']} {selected_loc['District']} site:.gov.in OR site:.nic.in"
    google_url = f"https://www.google.com/search?q={urllib.parse.quote(search_query)}"
    
    # 3. Inject it into the sidebar container we reserved
    with search_container:
        st.markdown("---")
        st.subheader(ui["find_email"])
        st.link_button(f"🌐 Search for {selected_loc['Town']} Email", google_url)
# -----------------------------------------------------


# --- SMART ISSUE COMBINATION ---
issue_parts = []
if issue_category and issue_category != "Other":
    issue_parts.append(f"Main Problem Category: {issue_category}")
if issue_details.strip():
    issue_parts.append(f"Specific Details, Landmarks & Extra Info: {issue_details.strip()}")

issue = "\n\n".join(issue_parts)
# -------------------------------

# 6. STEP 3: GENERATION
if st.button(ui["gen_btn"], key=f"gen_{st.session_state.reset_counter}"):
    if "letter" in st.session_state:
        del st.session_state["letter"]
        
    if not user_name or not selected_loc or not issue.strip() or len(user_pin) != 6:
        st.error("⚠️ Please complete all fields correctly.")
    else:
        with st.spinner(f"Drafting formal petition in {global_language}..."):
            p_val = user_phone.strip()
            maps_url = st.session_state.get('maps_link', "")
            has_evidence = True if uploaded_files and len(uploaded_files) > 0 else False

            from_label = "प्रेषक" if "Hindi" in global_language else f"the translation of 'From' in {global_language}"
            to_label = "सेवा में" if "Hindi" in global_language else f"the translation of 'To' in {global_language}"

            system_prompt = f"""
            You are an expert bilingual civic assistant. Your task is to write a formal civic complaint letter ENTIRELY in {global_language}.
            
            CRITICAL RULE: You MUST translate or transliterate ALL English names, dates, cities, and structural elements into the native script of {global_language}. Do not leave any English words unless {global_language} is English.

            Here is the raw data for the letter:
            - Date: {current_date} (Translate the month and format appropriately for {global_language})
            - Sender Name: {user_name} (Transliterate to {global_language} script)
            - Sender Phone: {p_val}
            - Recipient Title: The Municipal Commissioner
            - City/Town: {selected_loc['Town']} (Transliterate to {global_language} script)
            - District: {selected_loc['District']} (Transliterate to {global_language} script)
            - PIN Code: {selected_loc['PIN']}
            - EXACT ISSUE DESCRIPTION: {issue}
            - GPS Link Available: {maps_url}
            - Evidence Attached: {'Yes' if has_evidence else 'No'}

            FORMAT INSTRUCTIONS (Generate everything below in {global_language}):
            1. Date at the top.
            2. The "From" section (Sender name and phone). You MUST use '{from_label}' as the exact label for this section.
            3. The "To" section (Recipient title, City, District, PIN). You MUST use '{to_label}' as the exact label for this section.
            4. A clear, formal Subject line.
            5. A formal Salutation (e.g., Respected Sir/Madam).
            6. Write 2-3 professional paragraphs explaining the issue. 
               - CRITICAL RULE FOR OPENING SENTENCE: You must smoothly introduce the problem in the first sentence.
               - IF a "Main Problem Category" is provided, combine it with the details (e.g., "I am writing to formally bring to your attention the issue of a [Main Category] in my locality, specifically [Specific Details].").
               - IF ONLY "Specific Details" are provided (no category), deduce the main issue from the user's text yourself and frame it naturally (e.g., "I am writing to formally bring to your attention a pressing issue in my locality regarding [Your deduced topic], specifically [Specific Details].").
               - Never list the details as bullet points. Weave everything into natural paragraphs.
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
    st.subheader(ui["step4"])
    
    # 1. BEAUTIFUL AUTO-ADJUSTING READ-ONLY VIEW
    st.markdown(f"##### {ui['letter_content']}")
    st.info(st.session_state.letter) 
    
    # 2. OPTIONAL MANUAL EDITING EXPANDER
    with st.expander("✏️ Want to make manual edits? Click here."):
        edited_letter = st.text_area("Edit your letter:", value=st.session_state.letter, height=250, label_visibility="collapsed")
        if st.button("💾 Save Changes", key="save_edits"):
            st.session_state.letter = edited_letter
            st.rerun()
            
    st.markdown(f"##### {ui['email_routing']}")
    
    # --- NEW: AUTO-DETECT MISSING EMAIL ---
    if not st.session_state.sug_email:
        st.warning(ui["email_missing_warning"])
    # --------------------------------------

    col_to, col_cc = st.columns(2)
    with col_to:
        rec_to = st.text_input(ui["to"], value=st.session_state.sug_email, key=f"rec_to_{st.session_state.reset_counter}")
    with col_cc:
        rec_cc = st.text_input(ui["cc"], value="", key=f"rec_cc_{st.session_state.reset_counter}")
        
    col_bcc, col_me = st.columns(2)
    with col_bcc:
        rec_bcc = st.text_input(ui["bcc"], value="", key=f"rec_bcc_{st.session_state.reset_counter}")
    with col_me:
        user_receipt = st.text_input(ui["receipt"], value="", key=f"user_receipt_{st.session_state.reset_counter}")

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
            pdf_bytes = create_pdf(final_download_text)
            if pdf_bytes:
                st.download_button(ui["dl_pdf"], data=pdf_bytes, file_name=f"TRI_Report_{user_pin}.pdf", mime="application/pdf", key=f"dl_pdf_{st.session_state.reset_counter}")
            else:
                st.error("Error generating PDF.")
        else:
            txt_bytes = final_download_text.encode('utf-8')
            st.download_button(ui["dl_txt"], data=txt_bytes, file_name=f"TRI_Report_{user_pin}.txt", mime="text/plain", key=f"dl_txt_{st.session_state.reset_counter}")
        
        st.caption("💡 **Want to post on Facebook or Instagram?** Download the letter above and attach it directly to your post!")

    with col_btn2:
        st.caption("By clicking send, you agree to our [Privacy Policy](https://sites.google.com/view/httpsthereminderindia-streamli/home).")
        
        if st.button(ui["send_btn"], key=f"send_email_{st.session_state.reset_counter}"):
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
    st.markdown(f"##### {ui['wa_routing']}")
    
    # This brings back your missing comma-separation instructions!
    st.caption(ui["wa_instruction"])
    
    wa_numbers_input = st.text_input(ui["wa_num"], key=f"wa_multi_{st.session_state.reset_counter}")
    
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
            # This creates a beautiful row of buttons for each valid number entered
            btn_cols = st.columns(min(len(valid_numbers), 3)) 
            
            for i, num in enumerate(valid_numbers):
                wa_link = f"https://wa.me/91{num}?text={encoded_letter}"
                with btn_cols[i % 3]:
                    st.link_button(f"🟢 Send to {num}", wa_link, use_container_width=True)

    # --- SOCIAL MEDIA AMPLIFICATION (X / TWITTER) ---
    st.markdown("---")
    st.markdown(f"##### {ui['x_routing']}")
    
    tw_handle = st.text_input(ui["x_handle"], value="@", key=f"tw_handle_{st.session_state.reset_counter}")
    
    display_category = issue_category if issue_category else "Local Infrastructure"
    tweet_text = f"🚨 Civic Alert: {selected_loc['Town']}, PIN {selected_loc['PIN']}\n"
    tweet_text += f"Issue: {display_category}\n\n"
    
    if tw_handle and tw_handle.strip() != "@":
        tweet_text += f"{tw_handle.strip()} Please take urgent action on this matter.\n\n"
        
    tweet_text += "#CivicAction #TheReminderIndia"
    
    encoded_tweet = urllib.parse.quote(tweet_text)
    tw_link = f"https://twitter.com/intent/tweet?text={encoded_tweet}"
    
    st.link_button(ui["x_btn"], tw_link, use_container_width=True)
    # ---------------------------------------

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("---")
    col_spacer, col_clear = st.columns([3, 1])
    with col_clear:
        if st.button(ui["clear_btn"], key=f"clear_btn_{st.session_state.reset_counter}"):
            keys_to_delete = [k for k in st.session_state.keys() if k != 'reset_counter']
            for k in keys_to_delete:
                del st.session_state[k]
            st.session_state.reset_counter += 1
            st.rerun()