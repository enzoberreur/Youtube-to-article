import streamlit as st
import time
import gspread
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import json
import requests
from streamlit_js_eval import streamlit_js_eval

SERVICE_ACCOUNT_JSON = json.loads(st.secrets["google_service_account"]["credentials"])  # ✅ Correct JSON parsing

# 🔹 Fix private_key formatting
SERVICE_ACCOUNT_JSON["private_key"] = SERVICE_ACCOUNT_JSON["private_key"].replace("\\n", "\n")

MAKE_API_KEY = st.secrets["MAKE_API_KEY"]
SPREADSHEET_ID = st.secrets["SPREADSHEET_ID"]
SCENARIO_ID = st.secrets["SCENARIO_ID"]

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents.readonly"
]
creds = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_JSON, scope)
client = gspread.authorize(creds)

# 📌 Google Drive API
drive_service = build("drive", "v3", credentials=creds)
docs_service = build("docs", "v1", credentials=creds)

# 📌 Google Sheets Info
SPREADSHEET_ID = "1YXsVRezFHrjBvgsgC0vwV-_meN4sB6n2VwG0nQsRvr8"
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# 📌 Streamlit UI
st.title("YouTube To Article")

# 📌 Generate or Retrieve Unique User ID from Local Storage
user_id = streamlit_js_eval(js_expressions="localStorage.getItem('user_id') || (localStorage.setItem('user_id', Math.random().toString(36).substr(2, 9)), localStorage.getItem('user_id'))", key="user_id")

st.sidebar.write(f"📌 **Your Device ID:** `{user_id}`")  # Show user their ID

# 📌 Sidebar for User History
st.sidebar.title("📜 Your Recent History")


def extract_title_from_doc(doc_id):
    """
    Fetches the first line of content AFTER the first occurrence of '```' in a Google Doc.
    """
    try:
        doc = docs_service.documents().get(documentId=doc_id).execute()
        content = doc.get("body", {}).get("content", [])

        full_text = []
        for element in content:
            if "paragraph" in element:
                for text_run in element["paragraph"]["elements"]:
                    text = text_run.get("textRun", {}).get("content", "").strip()
                    if text:
                        full_text.append(text)  # Collect all text lines
        
        # Convert list to full text
        full_text_str = "\n".join(full_text)

        # Find the first occurrence of "```"
        if "```" in full_text_str:
            parts = full_text_str.split("```", 1)  # Split at first occurrence
            after_code = parts[1].strip().split("\n")  # Get text after "```"
            if after_code:  # Ensure there's text after "```"
                return after_code[0].strip()  # Return the first line after "```"

        # Fallback: return first line if "```" not found
        return full_text[0] if full_text else "Untitled Document"

    except HttpError as e:
        st.error(f"Error fetching Google Doc content: {e}")
    
    return "Untitled Document"  # Default title if no text found

def fetch_user_history():
    """
    Fetches history for the current user (last 5 entries).
    """
    try:
        data = sheet.get_all_values()  # Get all rows from the sheet
        user_history = [
            {"youtube_link": row[0], "doc_id": row[1], "user_id": row[2]}
            for row in data[1:] if len(row) >= 3 and row[2] == user_id  # Filter by user ID
        ]

        # Keep only last 5 entries
        return user_history[-10:]
    except Exception as e:
        st.sidebar.error(f"Error loading history: {e}")
        return []

# 📌 Load and display last 5 user history items
history = fetch_user_history()
for entry in history:
    if entry["doc_id"]:
        doc_link = f"https://docs.google.com/document/d/{entry['doc_id']}"
        doc_title = extract_title_from_doc(entry["doc_id"])  # Get title
        st.sidebar.markdown(f"📄 [{doc_title}]({doc_link})")  # Show clickable history


# 📌 Input Field for YouTube Link
youtube_link = st.text_input("🔗 Enter a YouTube Link:", "")

import requests

# Replace with your actual Make API Key
MAKE_API_KEY = "aa4049f5-55ff-4fb1-9b1e-0a145e238836"

# Use your Scenario ID from Make
SCENARIO_ID = "3702264"

# Make URL for EU2 region
MAKE_API_URL = f"https://eu2.make.com/api/v2/scenarios/{SCENARIO_ID}/run"

def trigger_make_scenario():
    """
    Triggers the Make scenario manually (like clicking 'Run Once').
    """
    headers = {
        "Authorization": f"Token {MAKE_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(MAKE_API_URL, headers=headers)
        if response.status_code == 200:
            print("✅ Make scenario triggered successfully!")
        elif response.status_code == 403:
            print("❌ Permission Denied: Check API Key permissions.")
        else:
            print(f"⚠️ Error triggering Make: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Failed to call Make API: {e}")


def add_link_to_sheet(youtube_link):
    """
    Adds the YouTube link to Google Sheets and manually triggers the Make scenario.
    """
    try:
        records = sheet.col_values(1)  # Get all values in Column A
        last_filled_row = len(records)  # Last non-empty row in Column A
        new_row_number = last_filled_row + 1  # Next available row

        # Add YouTube link to the correct row
        sheet.update(f"A{new_row_number}:C{new_row_number}", [[youtube_link, "", user_id]])  # Add YouTube link & User ID

        print(f"✅ YouTube link added to row {new_row_number}")

        time.sleep(2)
        # 📌 Immediately trigger Make scenario (like clicking 'Run Once')
        trigger_make_scenario()

        return new_row_number
    except Exception as e:
        print(f"❌ Error adding YouTube link: {e}")
        return None

def get_doc_id_for_last_link(row_number):
    """
    Gets the Google Doc ID from column B of the given row number.
    """
    try:
        cell_value = sheet.cell(row_number, 2).value  # Column B (Google Doc ID)
        return cell_value if cell_value else None
    except Exception as e:
        st.error(f"Error retrieving Google Doc ID: {e}")
        return None


if st.button("📩 Generate an article"):
    if youtube_link:
        st.write("✅ Convert Youtube video to text")
        row_number = add_link_to_sheet(youtube_link)

        if not row_number:
            st.error("⚠️ Error adding link to Google Sheets.")
        else:
            st.write(f"🔍 Waiting for Google Doc to be created... (30 to 60 seconds)")

            start_time = time.time()
            doc_link = None

            while time.time() - start_time < 300:  # Check for up to 5 minutes
                google_doc_id = get_doc_id_for_last_link(row_number)
                if google_doc_id and google_doc_id.strip():
                    doc_link = f"https://docs.google.com/document/d/{google_doc_id}"
                    break
                time.sleep(10)  # Wait 10 seconds before retrying

            if doc_link:
                st.success(f"📄 Google Doc: [Open Document]({doc_link})")
            else:
                st.warning("⚠️ No Google Doc ID found in Sheets. Please wait or try again.")
    else:
        st.warning("⚠️ Please enter a YouTube link.")