import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# Initialize the live Google Sheets Pipeline
conn = st.connection("gsheets", type=GSheetsConnection)

# --- UI Configuration ---
st.set_page_config(page_title="Hsk Shadow PMS", layout="centered", page_icon="🏨", initial_sidebar_state="expanded")

from streamlit_autorefresh import st_autorefresh
# Run a silent refresh every 10 seconds to sync multi-device changes automatically
st_autorefresh(interval=10000, key="global_board_sync")

# Custom CSS for high-density mobile list layout and button color shifting
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; max-width: 500px; }
    div[data-testid="stVerticalBlock"] > div { padding-bottom: 0px; }
    hr { margin-top: 0.4rem; margin-bottom: 0.4rem; }
    h3 { margin-bottom: 0rem !important; padding-bottom: 0rem !important; }
    .status-text { margin-top: -0.5rem; margin-bottom: 0.5rem; font-size: 0.95rem; }
    .center { display: flex; justify-content: center; text-align: center; }
    
    /* 🟢 SPEC 1: Turn toggles light green when Clean (_clean suffix) */
    div[class*="_clean"] button[kind="primary"] {
        background-color: #2e7d32 !important;
        border-color: #2e7d32 !important;
        color: white !important;
    }
    
    /* 🔘 SPEC 2: Turn toggles muted grey when DnD (_dnd suffix) */
    div[class*="_dnd"] button[kind="primary"] {
        background-color: #757575 !important;
        border-color: #757575 !important;
        color: white !important;
    }

    /* 🔵 SPEC 3: Turn V and S buttons BLUE when actively selected.
    These rules are declared AFTER SPEC 1/2 so they win the CSS
    cascade (same specificity, later rule wins) and override the
    green/grey room-level coloring specifically for V and S. */
    div[class*="_vswitch"] button[kind="primary"] {
        background-color: #1565C0 !important;
        border-color: #1565C0 !important;
        color: white !important;
    }
    div[class*="_sswitch"] button[kind="primary"] {
        background-color: #1565C0 !important;
        border-color: #1565C0 !important;
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- PYTHON WIZ MEETING DATA BIZ EXTRACTION ---
def process_uploaded_file(uploaded_file):
    try:
        # 1. Read ALL sheets as raw string grids
        all_sheets = pd.read_excel(
            uploaded_file,
            sheet_name=None,
            header=None,
            dtype=str
        )
        
        file_inventory = {}
        
        # Loop through whatever sheets exist ('Sheet1', 'Sheet2', etc.)
        for sheet_name, df in all_sheets.items():
            
            # Skip empty or corrupted sheets that don't even have data rows
            if df.shape[0] < 14:
                continue
                
            # 2. HARD-WIRED ANCHOR: Establish the exact baseline row index 
            # (Matches your hard-wired Excel Row 14 threshold requirement)
            header_row_idx = 10

            # 3. SURGICAL SLICE: Grab data 3 rows below the anchor, target Col A, E, and K
            df_clean = df.iloc[header_row_idx + 3:].copy()
            
            # Protect against sheets that don't have enough columns before slicing
            if df_clean.shape[1] < 11:
                continue
                
            df_clean = df_clean.iloc[:, [0, 4, 10]]
            df_clean.columns = ['RM', 'RM Type', 'Status']
            
            # 4. PARSE DATA ROWS FOR THIS SHEET INTO THE MASTER ENGINE
            consecutive_blanks = 0
                
            for idx, row in df_clean.iterrows():
                raw_rm = str(row['RM']).strip()
                
                # Safe bumper tracker per sheet to handle empty rows seamlessly
                if not raw_rm or raw_rm.lower() == 'nan' or raw_rm == '':
                    consecutive_blanks += 1
                    if consecutive_blanks >= 3: 
                        break
                    continue
                
                # Reset tracker when a valid room is found
                consecutive_blanks = 0
                
                if not raw_rm.isdigit():
                    continue
                    
                pms_status = str(row['Status']).strip().upper()
                
                # --- THE OPERATIONAL MATRIX MAPPING ---
                if pms_status == "STAY":
                    occupancy_code = "O"   # Occupied
                    cleanliness_code = "D" # Dirty
                    workload_code = "S"    # Stayover Service
                elif pms_status == "C/O":
                    occupancy_code = "V"   # Vacant! Guest already handed back the keys
                    cleanliness_code = "D" # Still Dirty
                    workload_code = "F"    # Flip Clean
                else:
                    # Catch-all for "DUE" or anything else out of the gate
                    occupancy_code = "O"   # Still technically occupied/checked in
                    cleanliness_code = "D" # Dirty
                    workload_code = "F"    # Flip Clean
                    
                # Append directly to the single master dictionary
                file_inventory[raw_rm] = {
                    "type": str(row['RM Type']).strip(),
                    "occupancy": occupancy_code,   
                    "cleanliness": cleanliness_code, 
                    "workload": workload_code,
                    "dnd": "No",
                    "comment": ""
                }
                
        # 🛠️ SAFETY CHECK: Verify inventory built successfully from the workbook
        if not file_inventory:
            st.error("⚠️ Processed the file but found 0 rooms. Check if the spreadsheet format has changed.")
            return

        # 🧹 6:00 AM NUKE: Convert the parsed data into a clean DataFrame
        df_to_upload = pd.DataFrame.from_dict(file_inventory, orient='index').reset_index()
        df_to_upload.columns = ['RM', 'Type', 'Occupancy', 'Cleanliness', 'Workload', 'DnD', 'Comment']
        
        # Overwrite the spreadsheet entirely, obliterating yesterday's data
        conn.update(worksheet="Sheet1", data=df_to_upload)
        
        # Set a session flag just to kick this specific user into Phase 2 immediately
        st.session_state.just_uploaded = True
        st.rerun()
        
    except Exception as e:
        # Temporarily raise the raw error so we can see the full stack trace
        raise e
        # st.error(f"Error parsing file: {str(e)}")

# ==============================================================================
# PHASE 1: THE ESTESTYLE LANDING & AUTOMATED FILE UPLOAD
# ==============================================================================
# Check the current live state of the sheet to decide which layout to route to
try:
    live_df = conn.read(ttl="2s")
except Exception:
    live_df = pd.DataFrame()

is_board_active = not live_df.empty

if not is_board_active:
    st.write(" ")
    st.markdown("<h2 class='center' style='color:rgb(70, 130, 255);'>An EsteStyle Streamlit Page<br>Where Python Wiz Meets Data Biz!</h2>", unsafe_allow_html=True)
    st.markdown("<img src='https://1drv.ms/i/s!ArWyPNkF5S-foZspwsary83MhqEWiA?embed=1&width=307&height=307' width='300' style='display: block; margin: 0 auto;'>", unsafe_allow_html=True)
    st.markdown("<h3 class='center' style='color: rgb(135, 206, 250);'>🏨 Originally created for Best Western at Firestone 🛎️</h3>", unsafe_allow_html=True)
    st.markdown("<h3 class='center' style='color: rgb(135, 206, 250);'>🤖 By Esteban C Loetz 📟</h3>", unsafe_allow_html=True)
    st.markdown("##")
    st.markdown("---")
    st.markdown("<h2 class='center' style='color: rgb(112, 128, 140);'>🧼 Shadow PMS Automator 📋</h2>", unsafe_allow_html=True)
    st.markdown("<h4 class='center'>Drop the daily data pull to activate the live whiteboard.</h4>", unsafe_allow_html=True)
    
    st.write("")
    st.markdown("""
    ### 🪜 Steps to Export Housekeeping Data on Visual Matrix:
    1. Change user from 'Front Office' to 'Housekeeping'.
    2. Select 'Room Assign' from ribbon.
    3. Select 'Room Assignment' from ribbon.
    4. Assign rooms.
    5. Click 'Floppy Disk' icon to save.
    6. Select 'Reports'
    7. Select 'Assignment Report' from dropdown.
    8. Click 'Export' button.
    9. Select 'Excel' from dropdown.
                
    ### How to Use the Shadow PMS:
    1. Upload the exported Excel file from the steps above.
    2. After successful processing, click the "Initialize Shadow Board" button.
    3. The live whiteboard will populate with all rooms and their statuses.
    4. Use the buttons to update occupancy, cleanliness, workload, and DnD status.
    5. Add operational notes in the text box for each room as needed.
    6. The board will auto-refresh every 10 seconds to sync changes across devices.
    7. To start a new day, click "Upload New Day File" to reset the board and upload a fresh Excel file.
    8. A new room can be added manually using the "Add Manual Room" section, specifying the room number and type.
    """)
    
    st.write('---')
    st.subheader("📊 Process File for Live Tracking:")
    
    # Wrap everything in a form to lock down the upload state until the button is clicked
    with st.form("hsk_upload_form", clear_on_submit=False):
        uploaded_file = st.file_uploader(label="Upload guest list Excel file", type=['xls', 'xlsx'], label_visibility="collapsed")
        submit_button = st.form_submit_button("🚀 Initialize Shadow Board", use_container_width=True)

        if submit_button and uploaded_file is not None:
            process_uploaded_file(uploaded_file)
        elif submit_button and uploaded_file is None:
            st.warning("⚠️ Please select a valid Excel file first before attempting to initialize.")

# ==============================================================================
# PHASE 2: THE LIVE WHITEBOARD APP
# ==============================================================================
else:
    st.write(" ")
    st.title("✨ Shadow PMS 🥷")
    
    # Create two columns up top to balance the layout
    top_c1, top_c2 = st.columns([1, 1])
    
    with top_c1:
        # DAILY RESET: Wipes out the rows in the Google Sheet, forcing the app back to Phase 1
        if st.button("🔄 Upload New Day File", use_container_width=True):
            conn.clear()
            st.rerun()
            
    # ➕ THE EASIEST METHOD: A clean, expandable drop-down for manual additions
    with top_c2:
        with st.expander("➕ Add Manual Room"):
            with st.form("manual_add_form", clear_on_submit=True):
                new_rm = st.text_input("Room #", placeholder="e.g., 204").strip()
                new_type = st.text_input("Type", placeholder="e.g., K / QQ").strip().upper()
                
                # Default presets for an ad-hoc mid-day add
                submit_new_rm = st.form_submit_button("Add to Board", use_container_width=True)
                
                if submit_new_rm:
                    if not new_rm:
                        st.error("Need a room number!")
                    # Check the live DataFrame for duplicates
                    elif str(new_rm) in live_df['RM'].astype(str).values:
                        st.warning(f"RM {new_rm} is already on the board!")
                    else:
                        # Append the new room row directly into the Google Sheet
                        new_row = pd.DataFrame([{
                            "RM": str(new_rm), "Type": new_type if new_type else "UNK",
                            "Occupancy": "O", "Cleanliness": "D", "Workload": "F",
                            "DnD": "No", "Comment": ""
                        }])
                        updated_df = pd.concat([live_df, new_row], ignore_index=True)
                        conn.update(data=updated_df)
                        st.rerun()
        
    st.markdown("<hr>", unsafe_allow_html=True)
    
    # Structure the Google Sheet DataFrame rows into our dictionary loop format
    live_df['RM'] = live_df['RM'].astype(str)
    inventory = live_df.set_index('RM').to_dict(orient='index')

    for room_num in sorted(inventory.keys(), key=lambda x: int(float(x))):
        room = inventory[room_num]
        
        # Track state tags for macro button key routing selectors
        if room["DnD"] == "DnD":
            state_suffix = "dnd"
        elif room["Cleanliness"] == "C":
            state_suffix = "clean"
        else:
            state_suffix = "normal"
        
        # Set clean text HTML status badge flags
        if room['DnD'] == "DnD":
            status_badge = "🔴 <b>DND ACTIVE</b>"
        elif room['Cleanliness'] == "C":
            status_badge = "✅ <b>READY</b>"
        else:
            status_badge = "⏳ <b>DIRTY</b>"

        # Single Row Layout per Room
        with st.container():
            # 1. Fetch the room type from your state dictionary safely
            room_type = room.get("Type", "UNK") # Defaults to Unknown if missing
            
            # 2. Render the primary Room Number
            st.markdown(f"### RM {room_num}")
            
            # 3. Render the Room Type right beneath it in a clean operational sub-label style
            st.markdown(f"<p style='color: #888888; font-size: 1.5rem; margin-top: -5px;'>{room_type}</p>", unsafe_allow_html=True)
            
            st.write(" ")  
            st.markdown(f"<div class='status-text'>{status_badge}</div>", unsafe_allow_html=True)
            st.write(" ")

            # Find the row index inside our DataFrame so we can overwrite it when clicked
            row_idx = live_df[live_df['RM'] == room_num].index[0]

            # --- The 4-Row Matrix Controller ---

            # Row 1: Cleanliness Toggles (D vs C)
            r1_c1, r1_c2, _ = st.columns([1, 1, 3])
            if r1_c1.button("Dirty / Sucio", key=f"D_{room_num}_{state_suffix}", type="primary" if room["Cleanliness"] == "D" else "secondary", use_container_width=True):
                live_df.at[row_idx, "Cleanliness"] = "D"
                conn.update(data=live_df)
                st.rerun()
            if r1_c2.button("Clean / Limpio", key=f"C_{room_num}_{state_suffix}", type="primary" if room["Cleanliness"] == "C" else "secondary", use_container_width=True):
                live_df.at[row_idx, "Cleanliness"] = "C"
                conn.update(data=live_df)
                st.rerun()
            
            # Row 2: Occupancy Toggles (O vs V)
            r2_c1, r2_c2, _ = st.columns([1, 1, 3])
            if r2_c1.button("Occupied / Ocupado", key=f"O_{room_num}_{state_suffix}", type="primary" if room["Occupancy"] == "O" else "secondary", use_container_width=True):
                live_df.at[row_idx, "Occupancy"] = "O"
                conn.update(data=live_df)
                st.rerun()
            v_key = f"V_{room_num}_{state_suffix}_vswitch" if state_suffix == "normal" else f"V_{room_num}_{state_suffix}"
            if r2_c2.button("Vacant / Disponible", key=v_key, type="primary" if room["Occupancy"] == "V" else "secondary", use_container_width=True):
                live_df.at[row_idx, "Occupancy"] = "V"
                conn.update(data=live_df)
                st.rerun()

            # Row 3: Workload Toggles (Flip vs Service)
            r3_c1, r3_c2, _ = st.columns([1, 1, 3])
            if r3_c1.button("Flip / Cambiarla", key=f"F_{room_num}_{state_suffix}", type="primary" if room["Workload"] == "F" else "secondary", use_container_width=True):
                live_df.at[row_idx, "Workload"] = "F"
                conn.update(data=live_df)
                st.rerun()

            s_key = f"S_{room_num}_{state_suffix}_sswitch" if state_suffix == "normal" else f"S_{room_num}_{state_suffix}"
            if r3_c2.button("Stay / Se Quedo", key=s_key, type="primary" if room["Workload"] == "S" else "secondary", use_container_width=True):
                live_df.at[row_idx, "Workload"] = "S"
                conn.update(data=live_df)
                st.rerun()
                
            # Row 4: Standalone DnD Toggle at the bottom
            r4_c1, _ = st.columns([2, 3])
            is_dnd_active = room["DnD"] == "DnD"
            dnd_button_label = "🛑 Do Not Disturb O" if is_dnd_active else "⚪ Set DnD Sign"
            if r4_c1.button(dnd_button_label, key=f"DnD_{room_num}", type="primary" if is_dnd_active else "secondary", use_container_width=True):
                live_df.at[row_idx, "DnD"] = "No" if is_dnd_active else "DnD"
                conn.update(data=live_df)
                st.rerun()

            # 💬 Row 5: Dynamic Operational Notes/Comments Field
            st.write(" ")
            
            # Fetch existing comment if it exists, default to empty string
            current_comment = str(room.get("Comment", ""))
            if current_comment.lower() == 'nan':
                current_comment = ""
            
            # Text input box that saves to session state instantly on pressing Enter
            updated_comment = st.text_input(
                "📋 Operational Notes:",
                value=current_comment,
                key=f"note_{room_num}",
                placeholder="Add notes / notas...",
                label_visibility="collapsed" # Keeps layout dense on mobile screens
            )
            
            # If the user edits the text, update the master database state silently
            if updated_comment != current_comment:
                live_df.at[row_idx, "Comment"] = updated_comment
                conn.update(data=live_df)
                st.rerun()

        st.markdown("<hr>", unsafe_allow_html=True)
