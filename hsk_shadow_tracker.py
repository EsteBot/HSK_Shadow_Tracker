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
        st.error(f"Error parsing file: {str(e)}")

# ==============================================================================
# PHASE 1: THE ESTESTYLE LANDING & AUTOMATED FILE UPLOAD
# ==============================================================================
# Check the current live state of the sheet to decide which layout to route to
try:
    live_df = conn.read(ttl="2s")
except Exception:
    live_df = pd.DataFrame()

is_board_active = not live_df.empty

if is_board_active:
    # STEP 1: Ensure the Note column exists in the active DataFrame
    if 'Note' not in live_df.columns:
        live_df['Note'] = ''

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
    
    # Create our 3 main operational swimlanes
    col_vd, col_od, col_vc = st.columns(3)

    # 1. VACANT DIRTY (FLIPS - HIGH PRIORITY)
    with col_vd:
        st.subheader("🔴 Vacant Dirty (V/D)")
        # Filter & render C/O rooms needing immediate turnover

    # 2. OCCUPIED DIRTY (SERVICING)
    with col_od:
        st.subheader("🔵 Occup'd Dirty (O/D)")
        # Filter & render Stayover / Due Out rooms

    # 3. VACANT CLEAN (READY TO RENT)
    with col_vc:
        st.subheader("🟢 Vacant Clean (V/C)")
        # Filter & render finished rooms

    # Updated Helper Function
    def inject_unscheduled_room(rm_num, action_type, note=""):
        rm_str = str(rm_num).strip().replace('.0', '')
        
        if action_type == 'checkout':
            new_occ, new_cln, new_workload = 'V', 'D', 'F'
        else:
            new_occ, new_cln, new_workload = 'O', 'D', 'S'

        if rm_str in live_df['RM'].values:
            idx = live_df[live_df['RM'] == rm_str].index[0]
            live_df.at[idx, 'Occupancy'] = new_occ
            live_df.at[idx, 'Cleanliness'] = new_cln
            if note:
                live_df.at[idx, 'Note'] = note
            conn.update(worksheet="Sheet1", data=live_df)
        else:
            new_row = {
                'RM': rm_str,
                'Type': 'STD',
                'Occupancy': new_occ,
                'Cleanliness': new_cln,
                'Workload': new_workload,
                'DnD': 'No',
                'Note': note
            }
            updated_df = pd.concat([live_df, pd.DataFrame([new_row])], ignore_index=True)
            conn.update(worksheet="Sheet1", data=updated_df)
            
        st.cache_data.clear()
        st.rerun()

    # --- UI COMPONENT: UNSCHEDULED ROOM ADDITION ---
    with st.expander("➕ **Add Unscheduled Room (Early Checkout or Service Request)**"):
        c_rm, c_note, c_co, c_stay = st.columns([1.5, 2.5, 1.5, 1.5])
        
        with c_rm:
            add_rm = st.text_input("Room #", placeholder="e.g., 302", key="add_unscheduled_rm")
            
        with c_note:
            add_note = st.text_input("Special Note (Optional)", placeholder="e.g., Has dog / Towels only", key="add_unscheduled_note")
            
        with c_co:
            st.write(" ") # Spacing shift for vertical alignment
            st.write(" ")
            if st.button("🚨 Early Checkout (Flip)", key="btn_add_co"):
                if add_rm:
                    inject_unscheduled_room(add_rm, action_type='checkout', note=add_note)
                    st.toast(f"Room {add_rm} added as Vacant Dirty Flip!", icon="🚨")
                else:
                    st.warning("Enter a room # first!")

        with c_stay:
            st.write(" ")
            st.write(" ")
            if st.button("🔵 Service Request (Stay)", key="btn_add_stay"):
                if add_rm:
                    inject_unscheduled_room(add_rm, action_type='service', note=add_note)
                    st.toast(f"Room {add_rm} added as Stayover Service!", icon="🔵")
                else:
                    st.warning("Enter a room # first!")
    
    # --- MAIN OPERATIONAL SHADOW BOARD ---
    st.markdown("## 🛎️ HSK Hub")

    # Strip accidental float decimals: '105.0' -> '105'
    live_df['RM'] = live_df['RM'].astype(str).str.replace('.0', '', regex=False)

    # Deduplicate by room number (keeping the latest updated row) before setting index
    inventory = live_df.drop_duplicates(subset=['RM'], keep='last').set_index('RM').to_dict(orient='index')

    # Group rooms into operational buckets dynamically
    vd_rooms = [] # Vacant Dirty
    od_rooms = [] # Occupied Dirty
    vc_rooms = [] # Vacant Clean

    # Sort room numbers cleanly
    sorted_rooms = sorted(inventory.keys(), key=lambda x: int(float(x)))

    for rm in sorted_rooms:
        room_data = inventory[rm]
        occ = str(room_data.get('Occupancy', 'V')).strip()
        cln = str(room_data.get('Cleanliness', 'D')).strip()
        
        # Bucket allocation logic
        if occ == 'V' and cln == 'C':
            vc_rooms.append((rm, room_data))
        elif occ == 'V' and cln == 'D':
            vd_rooms.append((rm, room_data))
        else:
            # Occupied rooms (both dirty & serviced) stay in this column
            od_rooms.append((rm, room_data))

    # Function to save state to Google Sheets and refresh app
    def update_room_state(target_rm, new_cln=None, new_occ=None, new_workload=None, toggle_dnd=False):
        target_rm_str = str(target_rm).strip().replace('.0', '')
        
        # Locate row index
        idx_list = live_df[live_df['RM'] == target_rm_str].index
        if len(idx_list) > 0:
            idx = idx_list[0]
            
            if new_cln:
                live_df.at[idx, 'Cleanliness'] = new_cln
            if new_occ:
                live_df.at[idx, 'Occupancy'] = new_occ
            if new_workload:
                live_df.at[idx, 'Workload'] = new_workload
            if toggle_dnd:
                current_dnd = live_df.at[idx, 'DnD']
                live_df.at[idx, 'DnD'] = 'No' if current_dnd == 'Yes' else 'Yes'
                
            conn.update(worksheet="Sheet1", data=live_df)
            st.cache_data.clear()
            st.rerun()

    def render_room_card(rm, data, card_style, badge_text):
        # Extract note safely
        note_text = str(data.get('Note', '')).strip()
        if note_text in ['nan', 'None', 'NoneType']:
            note_text = ""

        # Build note badge HTML if a note exists
        note_badge_html = f'<div style="margin-top:6px; font-size:0.85rem; font-weight:bold; color:#d93025; background:#ffffff; padding:3px 8px; border-radius:4px; display:inline-block; border:1px solid #ffcdd2;">📝 {note_text}</div>' if note_text else ''

        # Render Card HTML
        st.markdown(f"""
        <div style="padding:12px; border-radius:8px; margin-bottom:10px; {card_style}">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <strong style="font-size:1.3rem;">Room {rm}</strong>
                <span style="font-size:0.8rem; font-weight:bold; background:rgba(255,255,255,0.7); padding:2px 8px; border-radius:4px;">{badge_text}</span>
            </div>
            <small>Type: {data.get('Type', 'STD')}</small>
            {note_badge_html}
        </div>
        """, unsafe_allow_html=True)
        
        return note_text

    # Layout: 3 Operational Columns
    col_vd, col_od, col_vc = st.columns(3)

    # ==========================================
    # 1. VACANT DIRTY COLUMN (HIGH PRIORITY FLIPS)
    # ==========================================
    with col_vd:
        st.markdown(f"<h3 style='white-space: nowrap; margin-bottom: 0;'>🔴 V/D (<code>{len(vd_rooms)}</code>)</h3>", unsafe_allow_html=True)
        st.caption("Check-outs")
        
        for rm, data in vd_rooms:
            card_style = "background-color: #ffebeb; color: #900; border-left: 6px solid #ff4d4d;"
            badge = "🚨 FLIP"

            with st.container():
                # 1. Draw the whole card automatically & grab the note!
                # (Make sure to remove 'self.' if render_room_card isn't inside a class)
                note_text = render_room_card(rm, data, card_style, badge)
                
                # 2. Action Popover
                with st.popover(f"⚙️ Action: Room {rm}"):
                    if st.button("✨ Mark Clean & Ready", key=f"cln_vd_{rm}"):
                        update_room_state(rm, new_cln='C')
                    
                    st.divider()
                    
                    # 3. Note Editor
                    updated_note = st.text_input("Room Note / Instruction", value=note_text, key=f"note_vd_{rm}")
                    if st.button("💾 Save Note", key=f"save_vd_note_{rm}"):
                        idx = live_df[live_df['RM'] == str(rm)].index[0]
                        live_df.at[idx, 'Note'] = updated_note
                        conn.update(worksheet="Sheet1", data=live_df)
                        st.cache_data.clear()
                        st.rerun()

    # ==========================================
    # 2. OCCUPIED COLUMN (STAYS & DUES)
    # ==========================================
    with col_od:
        st.markdown(f"<h3 style='white-space: nowrap; margin-bottom: 0;'>🔵 O/D (<code>{len(od_rooms)}</code>)</h3>", unsafe_allow_html=True)
        st.caption("Due-outs & Stayovers")
        
        for rm, data in od_rooms:
            is_dnd = data.get('DnD') == 'Yes'
            cln = str(data.get('Cleanliness', 'D')).strip()
            workload = str(data.get('Workload', 'S')).strip()
            
            is_stayover = (workload == 'S')
            
            # Color state hierarchy
            if is_dnd and is_stayover:
                card_style = "background-color: #e0e0e0; color: #555; border-left: 6px solid #9e9e9e;"
                badge = "🔘 DnD"
            elif cln == 'C':
                card_style = "background-color: #e6f4ea; color: #137333; border-left: 6px solid #34a853;"
                badge = "🟢 SERVICED"
            elif is_stayover:
                card_style = "background-color: #eaf4ff; color: #004085; border-left: 6px solid #3399ff;"
                badge = "🔵 STAY"
            else:
                card_style = "background-color: #fff3cd; color: #856404; border-left: 6px solid #ffc107;"
                badge = "🟡 DUE OUT"

            with st.container():
                # 1. Draw Card with helper & capture note_text
                note_text = render_room_card(rm, data, card_style, badge)
                
                # 2. Action Popover
                with st.popover(f"⚙️ Action: Room {rm}"):
                    if is_stayover:
                        # STAYOVER ACTIONS (Includes DnD)
                        btn_clean_text = "✨ Mark Serviced" if cln != 'C' else "↩️ Mark Dirty"
                        new_status = 'C' if cln != 'C' else 'D'
                        if st.button(f"{btn_clean_text}", key=f"cln_od_{rm}"):
                            update_room_state(rm, new_cln=new_status)
                        
                        dnd_label = "Remove DnD" if is_dnd else "Set DnD"
                        if st.button(f"🚫 {dnd_label}", key=f"dnd_od_{rm}"):
                            update_room_state(rm, toggle_dnd=True)
                    else:
                        # DUE OUT ACTIONS
                        if st.button("🚪 Guest Checked Out", key=f"co_{rm}"):
                            update_room_state(rm, new_occ='V', new_cln='D')
                            
                        # 🔄 NEW: Extended Stay Override!
                        if st.button("🔄 Extended Stay (Convert to Stayover)", key=f"ext_{rm}"):
                            # Flips workload to Stayover ('S') and keeps as Occupied
                            update_room_state(rm, new_workload='S')
                            st.toast(f"Room {rm} converted to Stayover!", icon="🔄")

                    st.divider()
                    
                    # 3. Note Editor
                    updated_note = st.text_input("Room Note / Instruction", value=note_text, key=f"note_od_{rm}")
                    if st.button("💾 Save Note", key=f"save_od_note_{rm}"):
                        idx = live_df[live_df['RM'] == str(rm)].index[0]
                        live_df.at[idx, 'Note'] = updated_note
                        conn.update(worksheet="Sheet1", data=live_df)
                        st.cache_data.clear()
                        st.rerun()

    # ==========================================
    # 3. VACANT CLEAN COLUMN (READY TO RENT)
    # ==========================================
    with col_vc:
        st.markdown(f"<h3 style='white-space: nowrap; margin-bottom: 0;'>🟢 V/C (<code>{len(vc_rooms)}</code>)</h3>", unsafe_allow_html=True)
        st.caption("Clean & Ready")
        
        for rm, data in vc_rooms:
            card_style = "background-color: #e6f4ea; color: #137333; border-left: 6px solid #34a853;"
            badge = "🟢 READY"
            
            with st.container():
                # 1. Draw Card with helper & capture note_text
                note_text = render_room_card(rm, data, card_style, badge)
                
                # 2. Action Popover
                with st.popover(f"⚙️ Action: Room {rm}"):
                    if st.button("↩️ Re-open as Dirty", key=f"reopen_{rm}"):
                        update_room_state(rm, new_cln='D')

                    st.divider()
                    
                    # 3. Note Editor
                    updated_note = st.text_input("Room Note / Instruction", value=note_text, key=f"note_vc_{rm}")
                    if st.button("💾 Save Note", key=f"save_vc_note_{rm}"):
                        idx = live_df[live_df['RM'] == str(rm)].index[0]
                        live_df.at[idx, 'Note'] = updated_note
                        conn.update(worksheet="Sheet1", data=live_df)
                        st.cache_data.clear()
                        st.rerun()
