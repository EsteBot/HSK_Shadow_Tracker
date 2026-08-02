import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from streamlit_autorefresh import st_autorefresh

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="BWF HSK Hub", 
    page_icon="🧼", 
    layout="wide",
)

# --- GLOBAL STYLING ---
st.markdown("""
    <style>
    /* Remove artificial max-width constraint for responsive layout */
    /* Force symmetrical left/right margins and prevent sidebar offset skew */
    .block-container { 
        padding-top: 2rem !important; 
        padding-bottom: 2rem !important;
        padding-left: 10rem !important;
        padding-right: 10rem !important;
        max-width: 96% !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }

    /* Keep inner main content strictly centered */
    [data-testid="stMainBlockContainer"] {
        margin: 0 auto !important;
    }
    
    /* Consistent divider margins */
    hr { 
        margin-top: 0.8rem; 
        margin-bottom: 0.8rem; 
    }

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

    /* 🔵 SPEC 3: Turn V and S buttons BLUE when actively selected */
    div[class*="_vswitch"] button[kind="primary"],
    div[class*="_sswitch"] button[kind="primary"] {
        background-color: #1565C0 !important;
        border-color: #1565C0 !important;
        color: white !important;
    }

    /* Target Streamlit's bordered container wrapper directly for chunkier spacing */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        margin-bottom: 1.25rem !important;
    }
    </style>
""", unsafe_allow_html=True)

# Run a silent refresh every 10 seconds to sync multi-device changes automatically
st_autorefresh(interval=10000, key="global_board_sync")

# Initialize the live Google Sheets Pipeline
conn = st.connection("gsheets", type=GSheetsConnection)

# --- HEADER & HELP SECTION ---
head_col1, head_col2 = st.columns([0.8, 0.2])

with head_col1:
    st.title("🥷 Shadow HSK Board")

with head_col2:
    with st.popover("ℹ️ SOPs & Help"):
        st.markdown("### 📖 Visual Matrix Export SOP")
        st.markdown("""
        1. Switch user to **Housekeeping**  
        2. Select **Room Assign** ➔ **Room Assignment**  
        3. Assign rooms & click **Floppy Disk** icon to save  
        4. Go to **Reports** ➔ **Assignment Report**  
        5. Click **Export** ➔ **Excel**
        """)
        st.divider()
        st.markdown("### ❓ Quick Guide")
        st.markdown("""
        * **🔴 V/D:** Check-outs needing clean.
        * **🔵 S/O:** Stayovers / Occupied clean.
        * **🟢 V/C:** Clean & ready.
        """)
        st.caption("Originally created for Best Western at Firestone")
        st.caption("By Esteban C Loetz")

st.divider()

# --- DATA EXTRACTION HELPER ---
def process_uploaded_file(uploaded_file):
    try:
        all_sheets = pd.read_excel(
            uploaded_file,
            sheet_name=None,
            header=None,
            dtype=str
        )
        
        file_inventory = {}
        
        for sheet_name, df in all_sheets.items():
            if df.shape[0] < 14:
                continue
                
            header_row_idx = 10
            df_clean = df.iloc[header_row_idx + 3:].copy()
            
            if df_clean.shape[1] < 11:
                continue
                
            df_clean = df_clean.iloc[:, [0, 4, 10]]
            df_clean.columns = ['RM', 'RM Type', 'Status']
            
            consecutive_blanks = 0
                
            for idx, row in df_clean.iterrows():
                raw_rm = str(row['RM']).strip()
                
                if not raw_rm or raw_rm.lower() == 'nan' or raw_rm == '':
                    consecutive_blanks += 1
                    if consecutive_blanks >= 3: 
                        break
                    continue
                
                consecutive_blanks = 0
                
                if not raw_rm.isdigit():
                    continue
                    
                pms_status = str(row['Status']).strip().upper()
                
                if pms_status == "STAY":
                    occupancy_code, cleanliness_code, workload_code = "O", "D", "S"
                elif pms_status == "C/O":
                    occupancy_code, cleanliness_code, workload_code = "V", "D", "F"
                else:
                    occupancy_code, cleanliness_code, workload_code = "O", "D", "F"
                    
                file_inventory[raw_rm] = {
                    "type": str(row['RM Type']).strip(),
                    "occupancy": occupancy_code,   
                    "cleanliness": cleanliness_code, 
                    "workload": workload_code,
                    "dnd": "No",
                    "comment": "",
                    "Vm_Flipped": "No"
                }
                
        if not file_inventory:
            st.error("⚠️ Processed the file but found 0 rooms. Check spreadsheet format.")
            return

        df_to_upload = pd.DataFrame.from_dict(file_inventory, orient='index').reset_index()
        df_to_upload.columns = ['RM', 'Type', 'Occupancy', 'Cleanliness', 'Workload', 'DnD', 'Comment', 'Vm_Flipped']
        
        conn.update(worksheet="Sheet1", data=df_to_upload)
        st.session_state.just_uploaded = True
        st.rerun()
        
    except Exception as e:
        st.error(f"Error parsing file: {str(e)}")

# --- DATA INITIALIZATION ---
try:
    live_df = conn.read(ttl="2s")
except Exception as e:
    st.error("⚠️ Unable to connect to Google Sheets. Check network or connection secrets.")
    st.stop()

if live_df.empty:
    st.info("ℹ️ The Shadow Board is currently empty. Upload a sheet via Admin Options to populate.")
    st.stop()

if 'Note' not in live_df.columns:
    live_df['Note'] = ''

if 'Vm_Flipped' not in live_df.columns:
    live_df['Vm_Flipped'] = 'No'

# --- ADMIN SAFEGUARD ---
with st.expander("⚙️ Admin Options / Load New Day's Assignment Sheet"):
    st.caption("⚠️ Use this section at the start of a new shift to load a fresh Visual Matrix export.")
    
    admin_uploaded_file = st.file_uploader(
        "Upload Today's Assignment File (.xls, .xlsx)", 
        type=['xls', 'xlsx'],
        key="admin_day_reset_uploader"
    )
    
    if admin_uploaded_file is not None:
        st.warning("⚠️ Loading a new file will OVERWRITE all active room progress for today!")
        confirm_reset = st.checkbox("I understand this will wipe today's live board.", key="chk_confirm_reset")
        
        if st.button("🚀 Overwrite & Initialize New Day", disabled=not confirm_reset, type="primary", key="btn_admin_reset"):
            with st.spinner("Processing new assignment sheet..."):
                process_uploaded_file(admin_uploaded_file)

# --- HELPER FUNCTIONS ---
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

def update_room_state(target_rm, new_cln=None, new_occ=None, new_workload=None, toggle_dnd=False):
    target_rm_str = str(target_rm).strip().replace('.0', '')
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
    note_text = str(data.get('Note', '')).strip()
    if note_text in ['nan', 'None', 'NoneType']:
        note_text = ""

    note_badge_html = f'<div style="margin-top:6px; font-size:0.85rem; font-weight:bold; color:#d93025; background:#ffffff; padding:3px 8px; border-radius:4px; display:inline-block; border:1px solid #ffcdd2;">📝 {note_text}</div>' if note_text else ''

    st.markdown(f"""
    <div style="padding:12px; border-radius:8px; margin-bottom:10px; {card_style}">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <strong style="font-size:1.2rem;">Room {rm}</strong>
            <span style="font-size:0.8rem; font-weight:bold; background:rgba(255,255,255,0.75); padding:2px 8px; border-radius:4px;">{badge_text}</span>
        </div>
        <small style="opacity:0.9;">Type: {data.get('Type', 'STD')}</small>
        {note_badge_html}
    </div>
    """, unsafe_allow_html=True)
    
    return note_text

# --- UNSCHEDULED ROOM ADDITION ---
with st.expander("➕ **Add Unscheduled Room (Early Checkout / Service Request)**"):
    c_rm, c_note, c_co, c_stay = st.columns([1.5, 2.5, 1.5, 1.5])
    
    with c_rm:
        add_rm = st.text_input("Room #", placeholder="e.g., 302", key="add_unscheduled_rm")
        
    with c_note:
        add_note = st.text_input("Special Note (Optional)", placeholder="e.g., Has dog / Towels only", key="add_unscheduled_note")
        
    with c_co:
        st.write(" ")
        if st.button("🚨 Early Checkout", key="btn_add_co", use_container_width=True):
            if add_rm:
                inject_unscheduled_room(add_rm, action_type='checkout', note=add_note)
                st.toast(f"Room {add_rm} added as Vacant Dirty Flip!", icon="🚨")
            else:
                st.warning("Enter a room # first!")

    with c_stay:
        st.write(" ")
        if st.button("🔵 Service Request", key="btn_add_stay", use_container_width=True):
            if add_rm:
                inject_unscheduled_room(add_rm, action_type='service', note=add_note)
                st.toast(f"Room {add_rm} added as Stayover Service!", icon="🔵")
            else:
                st.warning("Enter a room # first!")

st.divider()

# --- MAIN OPERATIONAL SHADOW BOARD ---
st.subheader("🛎️ Room List")

# Format Data & Allocate Buckets
live_df['RM'] = live_df['RM'].astype(str).str.replace('.0', '', regex=False)
inventory = live_df.drop_duplicates(subset=['RM'], keep='last').set_index('RM').to_dict(orient='index')

vd_rooms = [] 
od_rooms = [] 
vc_rooms = [] 

sorted_rooms = sorted(inventory.keys(), key=lambda x: int(float(x)))

for rm in sorted_rooms:
    room_data = inventory[rm]
    occ = str(room_data.get('Occupancy', 'V')).strip()
    cln = str(room_data.get('Cleanliness', 'D')).strip()
    
    if occ == 'V' and cln == 'C':
        vc_rooms.append((rm, room_data))
    elif occ == 'V' and cln == 'D':
        vd_rooms.append((rm, room_data))
    else:
        od_rooms.append((rm, room_data))

# Render Layout Columns
col_vd, col_od, col_vc = st.columns(3, gap="large")

# 1. VACANT DIRTY
with col_vd:
    st.markdown(f"### 🔴 V/D (`{len(vd_rooms)}`)")
    st.caption("Check-outs")
    st.write("")
    
    for rm, data in vd_rooms:
        card_style = "background-color: #ffebeb; color: #900; border-left: 6px solid #ff4d4d;"
        badge = "🚨 FLIP"

        # Enclose room + action button in a bordered container with vertical margin
        with st.container(border=True):
            note_text = render_room_card(rm, data, card_style, badge)
            
            with st.popover(f"⚙️ Action: Room {rm}", use_container_width=True):
                if st.button("✨ Mark Clean & Ready", key=f"cln_vd_{rm}", type="primary"):
                    update_room_state(rm, new_cln='C')
                
                st.divider()
    
                if st.button("↩️ Undo Checkout (Mark Occupied)", key=f"undo_co_{rm}"):
                    update_room_state(rm, new_occ='O', new_cln='D')
                    st.toast(f"Room {rm} reverted to Occupied!", icon="↩️")
    
                st.divider()
                
                updated_note = st.text_input("Room Note / Instruction", value=note_text, key=f"note_vd_{rm}")
                if st.button("💾 Save Note", key=f"save_vd_note_{rm}"):
                    idx = live_df[live_df['RM'] == str(rm)].index[0]
                    live_df.at[idx, 'Note'] = updated_note
                    conn.update(worksheet="Sheet1", data=live_df)
                    st.cache_data.clear()
                    st.rerun()

        st.html('<div style="height: 15px;"></div>')

# 2. OCCUPIED (STAYS & DUES)
with col_od:
    st.markdown(f"### 🔵 S/O (`{len(od_rooms)}`)")
    st.caption("Due-outs & Stayovers")
    st.write("")
    
    for rm, data in od_rooms:
        is_dnd = data.get('DnD') == 'Yes'
        cln = str(data.get('Cleanliness', 'D')).strip()
        workload = str(data.get('Workload', 'S')).strip()
        is_stayover = (workload == 'S')
    
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
    
        with st.container(border=True):
            note_text = render_room_card(rm, data, card_style, badge)
            
            with st.popover(f"⚙️ Action: Room {rm}", use_container_width=True):
                if is_stayover:
                    btn_clean_text = "✨ Mark Serviced" if cln != 'C' else "↩️ Mark Dirty"
                    new_status = 'C' if cln != 'C' else 'D'
                    if st.button(f"{btn_clean_text}", key=f"cln_od_{rm}"):
                        update_room_state(rm, new_cln=new_status)
                    
                    dnd_label = "Remove DnD" if is_dnd else "Set DnD"
                    if st.button(f"🚫 {dnd_label}", key=f"dnd_od_{rm}"):
                        update_room_state(rm, toggle_dnd=True)
                else:
                    if st.button("🚪 Guest Checked Out", key=f"co_{rm}", type="primary"):
                        update_room_state(rm, new_occ='V', new_cln='D')
                        
                    if st.button("🔄 Extended Stay (Convert to Stayover)", key=f"ext_{rm}"):
                        update_room_state(rm, new_workload='S')
                        st.toast(f"Room {rm} converted to Stayover!", icon="🔄")
    
                st.divider()
                
                updated_note = st.text_input("Room Note / Instruction", value=note_text, key=f"note_od_{rm}")
                if st.button("💾 Save Note", key=f"save_od_note_{rm}"):
                    idx = live_df[live_df['RM'] == str(rm)].index[0]
                    live_df.at[idx, 'Note'] = updated_note
                    conn.update(worksheet="Sheet1", data=live_df)
                    st.cache_data.clear()
                    st.rerun()

        st.html('<div style="height: 15px;"></div>')

# 3. VACANT CLEAN
with col_vc:
    st.markdown(f"### 🟢 V/C (`{len(vc_rooms)}`)")
    st.caption("Clean & Ready to Rent")
    st.write("")
    
    vc_rooms_sorted = sorted(vc_rooms, key=lambda x: 1 if x[1].get('Vm_Flipped') == 'Yes' else 0)
    
    for rm, data in vc_rooms_sorted:
        is_flipped = data.get('Vm_Flipped') == 'Yes'
    
        if is_flipped:
            card_style = "background-color: #f1f3f4; color: #5f6368; border-left: 6px solid #9aa0a6; opacity: 0.65;"
            badge = "✔️ IN VM"
        else:
            card_style = "background-color: #e6f4ea; color: #137333; border-left: 6px solid #34a853;"
            badge = "🟢 READY"
        
        with st.container(border=True):
            note_text = render_room_card(rm, data, card_style, badge)
            
            with st.popover(f"⚙️ Action: Room {rm}", use_container_width=True):
                if not is_flipped:
                    if st.button("💻 Mark Flipped in VM", key=f"flip_vm_{rm}", type="primary"):
                        idx = live_df[live_df['RM'] == str(rm)].index[0]
                        live_df.at[idx, 'Vm_Flipped'] = 'Yes'
                        conn.update(worksheet="Sheet1", data=live_df)
                        st.cache_data.clear()
                        st.toast(f"Room {rm} marked as Flipped in Visual Matrix!", icon="💻")
                        st.rerun()
                else:
                    if st.button("↩️ Unmark VM Status", key=f"unflip_vm_{rm}"):
                        idx = live_df[live_df['RM'] == str(rm)].index[0]
                        live_df.at[idx, 'Vm_Flipped'] = 'No'
                        conn.update(worksheet="Sheet1", data=live_df)
                        st.cache_data.clear()
                        st.rerun()
    
                st.divider()
    
                if st.button("↩️ Re-open as Dirty", key=f"reopen_{rm}"):
                    update_room_state(rm, new_cln='D')
    
                st.divider()
                
                updated_note = st.text_input("Room Note / Instruction", value=note_text, key=f"note_vc_{rm}")
                if st.button("💾 Save Note", key=f"save_vc_note_{rm}"):
                    idx = live_df[live_df['RM'] == str(rm)].index[0]
                    live_df.at[idx, 'Note'] = updated_note
                    conn.update(worksheet="Sheet1", data=live_df)
                    st.cache_data.clear()
                    st.rerun()
        st.html('<div style="height: 15px;"></div>')
