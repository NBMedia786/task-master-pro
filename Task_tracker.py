import streamlit as st
import pandas as pd
import datetime
import uuid
import pytz
import time
import random
from streamlit_gsheets import GSheetsConnection

# --- Configuration ---
st.set_page_config(page_title="Task Master Pro", page_icon="⚡", layout="wide")
TIMEZONE = 'Asia/Kolkata' 

# --- Professional UI & CSS Styling ---
st.markdown("""
    <style>
    /* --- ANIMATIONS & GLOBAL --- */
    @keyframes slideIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .block-container { padding-top: 2rem; padding-bottom: 5rem; }
    
    /* --- METRICS & DASHBOARD --- */
    div[data-testid="metric-container"] {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
        transition: transform 0.2s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
    }
    @media (prefers-color-scheme: dark) {
        div[data-testid="metric-container"] {
            background-color: #1e293b;
            border-color: #334155;
        }
    }

    /* --- TASK CARD DESIGN --- */
    .task-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        
        /* Smooth Animation */
        animation: slideIn 0.4s ease-out forwards;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        
        display: flex;
        flex-direction: column;
    }
    .task-card:hover {
        transform: translateY(-3px) scale(1.005);
        box-shadow: 0 10px 20px rgba(0,0,0,0.08);
        border-color: #cbd5e1;
    }
    
    /* Priority Borders */
    .border-high { border-left: 4px solid #ef4444 !important; }
    .border-medium { border-left: 4px solid #f59e0b !important; }
    .border-low { border-left: 4px solid #10b981 !important; }
    
    @media (prefers-color-scheme: dark) {
        .task-card { 
            background-color: #1e293b; 
            border-color: #334155; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);
        }
        .task-card:hover {
            background-color: #26334d;
            box-shadow: 0 10px 20px rgba(0,0,0,0.4);
        }
    }

    /* --- BADGES --- */
    .badge {
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        display: inline-block;
        margin-right: 6px;
    }
    .badge-high { color: #dc2626; background-color: #fee2e2; border: 1px solid #fecaca; }
    .badge-medium { color: #d97706; background-color: #fef3c7; border: 1px solid #fde68a; }
    .badge-low { color: #059669; background-color: #d1fae5; border: 1px solid #a7f3d0; }
    .badge-promo { color: #b45309; background-color: #ffedd5; border: 1px dashed #fdba74; }

    /* --- TYPOGRAPHY --- */
    .task-text {
        font-size: 1.05rem;
        font-weight: 500;
        color: #0f172a;
        margin-bottom: 6px;
        display: block;
        font-family: 'Inter', sans-serif;
    }
    @media (prefers-color-scheme: dark) {
        .task-text { color: #f1f5f9; }
    }
    
    /* --- INPUT AREA (Glassmorphism) --- */
    .input-wrapper {
        background: rgba(255, 255, 255, 0.8);
        backdrop-filter: blur(10px);
        padding: 20px;
        border-radius: 16px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.3);
        margin-bottom: 30px;
    }
    @media (prefers-color-scheme: dark) {
        .input-wrapper {
            background: rgba(30, 41, 59, 0.7);
            border-color: rgba(255, 255, 255, 0.05);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
        }
    }

    /* --- COMPACT SIDEBAR HISTORY --- */
    .history-card {
        padding: 10px;
        background-color: transparent;
        border-bottom: 1px solid #e2e8f0;
        transition: background 0.2s;
        border-radius: 6px;
    }
    .history-card:hover {
        background-color: #f1f5f9;
    }
    .history-text {
        color: #94a3b8;
        text-decoration: line-through;
        font-size: 0.85rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    @media (prefers-color-scheme: dark) {
        .history-card { border-bottom-color: #334155; }
        .history-card:hover { background-color: #334155; }
    }
    
    /* --- BUTTONS --- */
    div[data-testid="column"] button {
        border-radius: 6px;
        padding: 0px 4px;
        height: 32px;
        min-height: 32px;
        border: none;
        background: transparent;
        transition: all 0.2s;
    }
    div[data-testid="column"] button:hover {
        background: rgba(100, 116, 139, 0.1);
        transform: scale(1.1);
    }
    </style>
""", unsafe_allow_html=True)

# --- Helpers ---
def get_current_time():
    tz = pytz.timezone(TIMEZONE)
    return datetime.datetime.now(tz)

def get_today_str():
    return get_current_time().strftime('%Y-%m-%d')

@st.cache_resource
def get_gsheets_conn():
    return st.connection("gsheets", type=GSheetsConnection)

def retry_operation(func, retries=5):
    """Retries a function if it hits a rate limit error."""
    for i in range(retries):
        try:
            return func()
        except Exception as e:
            error_str = str(e)
            if any(x in error_str for x in ["429", "RESOURCE_EXHAUSTED", "Quota exceeded", "500", "503"]):
                wait_time = (2 ** i) + random.uniform(0, 1)
                time.sleep(wait_time)
                continue
            else:
                raise e 
    raise Exception("Server is busy. Please wait a few seconds and reload.")

# --- Optimized Data Handling ---
def sync_to_cloud():
    """Writes the CURRENT session state dataframe to the cloud."""
    if 'tasks_df' not in st.session_state: return
    
    df = st.session_state['tasks_df']
    conn = get_gsheets_conn()
    
    def write_op(): conn.update(worksheet='Tasks', data=df)
    
    try:
        retry_operation(write_op)
        st.cache_data.clear() # Clear cache so next hard refresh gets new data
    except Exception as e:
        st.toast(f"⚠️ Cloud sync failed (Local data is preserved): {e}")

def load_data(force_refresh=False):
    """Loads data into Session State. Uses local cache if available for SPEED."""
    
    # If we already have data and not forcing refresh, skip the download!
    if 'tasks_df' in st.session_state and not force_refresh:
        return st.session_state['tasks_df']

    conn = get_gsheets_conn()
    cols = ['id', 'text', 'priority', 'completed', 'created_at', 'completed_at', 'was_auto_promoted', 'custom_sort_index']
    
    try:
        def read_op(): return conn.read(worksheet='Tasks', usecols=list(range(len(cols))), ttl=0)
        df = retry_operation(read_op)
        
        if df is None: df = pd.DataFrame(columns=cols)
        if df.empty: df = pd.DataFrame(columns=cols) if df.columns.empty else df

        for col in cols:
            if col not in df.columns: df[col] = None
        
        # Schema Validation
        if df['custom_sort_index'].isnull().all() and not df.empty:
            df['custom_sort_index'] = range(len(df), 0, -1)
        elif df['custom_sort_index'].isnull().any():
            max_val = df['custom_sort_index'].max()
            if pd.isna(max_val): max_val = 0
            df['custom_sort_index'] = df['custom_sort_index'].fillna(max_val)

        df['id'] = df['id'].astype(str)
        df['custom_sort_index'] = pd.to_numeric(df['custom_sort_index'], errors='coerce').fillna(0)

        def clean_bool(x):
            if isinstance(x, bool): return x
            if isinstance(x, (int, float)): return bool(x)
            return str(x).lower() in ['true', '1', 'yes']

        if 'completed' in df.columns: df['completed'] = df['completed'].apply(clean_bool)
        if 'was_auto_promoted' in df.columns: df['was_auto_promoted'] = df['was_auto_promoted'].apply(clean_bool)
        df['created_at'] = df['created_at'].astype(str).replace('nan', '')
        df['completed_at'] = df['completed_at'].astype(str).replace('nan', None)
        
        # Store in Session State
        st.session_state['tasks_df'] = df
        return df
        
    except Exception as e:
        if "WorksheetNotFound" in str(e):
            df_new = pd.DataFrame(columns=cols)
            st.session_state['tasks_df'] = df_new
            sync_to_cloud()
            return df_new
        st.error(f"Unable to load data: {e}")
        st.stop()

def run_auto_promote():
    if 'tasks_df' not in st.session_state: return
    if 'auto_promote_ran' in st.session_state: return
    
    df = st.session_state['tasks_df']
    if df.empty: st.session_state['auto_promote_ran'] = True; return
    
    today_str = get_today_str()
    updates = 0
    
    mask_promote = ((df['completed'] == False) & (df['priority'] != 'High') & (df['created_at'].str[:10] < today_str) & (df['created_at'].str[:10] != ''))
    if mask_promote.any():
        df.loc[mask_promote, 'priority'] = 'High'
        df.loc[mask_promote, 'was_auto_promoted'] = True
        current_max = df['custom_sort_index'].max()
        if pd.isna(current_max): current_max = 0
        df.loc[mask_promote, 'custom_sort_index'] = current_max + 1
        updates += 1
    
    mask_carried = ((df['completed'] == False) & (df['priority'] == 'High') & (df['was_auto_promoted'] == False) & (df['created_at'].str[:10] < today_str) & (df['created_at'].str[:10] != ''))
    if mask_carried.any():
        df.loc[mask_carried, 'was_auto_promoted'] = True
        updates += 1
    
    if updates > 0:
        st.session_state['tasks_df'] = df
        sync_to_cloud() # Push changes
        if mask_promote.sum() > 0: st.toast(f"🚀 Promoted {mask_promote.sum()} tasks!")
    
    st.session_state['auto_promote_ran'] = True

# --- Actions (Modify Local State -> Sync -> Rerun) ---
def add_task(text, priority):
    df = st.session_state['tasks_df']
    max_idx = df['custom_sort_index'].max()
    if pd.isna(max_idx): max_idx = 0
    new_row = pd.DataFrame([{
        'id': str(uuid.uuid4()), 'text': text, 'priority': priority, 'completed': False,
        'created_at': str(get_current_time()), 'completed_at': None, 'was_auto_promoted': False,
        'custom_sort_index': max_idx + 1
    }])
    st.session_state['tasks_df'] = pd.concat([df, new_row], ignore_index=True)
    sync_to_cloud()

def move_task(task_id, direction):
    df = st.session_state['tasks_df']
    df = df.sort_values(by='custom_sort_index', ascending=False).reset_index(drop=True)
    try: current_idx = df[df['id'] == str(task_id)].index[0]
    except IndexError: return

    swap_idx = None
    if direction == 'up' and current_idx > 0: swap_idx = current_idx - 1
    elif direction == 'down' and current_idx < len(df) - 1: swap_idx = current_idx + 1
        
    if swap_idx is not None:
        val_curr = df.at[current_idx, 'custom_sort_index']
        val_swap = df.at[swap_idx, 'custom_sort_index']
        if val_curr == val_swap: val_swap += 1
        df.at[current_idx, 'custom_sort_index'] = val_swap
        df.at[swap_idx, 'custom_sort_index'] = val_curr
        
        st.session_state['tasks_df'] = df
        sync_to_cloud()

def toggle_complete(task_id, current_val):
    df = st.session_state['tasks_df']
    target_id = str(task_id)
    if target_id not in df['id'].values: return
    
    mask = df['id'] == target_id
    new_val = not current_val
    df.loc[mask, 'completed'] = new_val
    df.loc[mask, 'completed_at'] = str(get_current_time()) if new_val else None
    
    st.session_state['tasks_df'] = df
    sync_to_cloud()

def update_task_details(task_id, new_text, new_priority):
    df = st.session_state['tasks_df']
    target_id = str(task_id)
    if target_id not in df['id'].values: return
    
    mask = df['id'] == target_id
    df.loc[mask, 'text'] = new_text
    df.loc[mask, 'priority'] = new_priority
    df.loc[mask, 'was_auto_promoted'] = False
    
    st.session_state['tasks_df'] = df
    sync_to_cloud()

def delete_task(task_id):
    df = st.session_state['tasks_df']
    target_id = str(task_id)
    if target_id not in df['id'].values: return
    
    df = df[df['id'] != target_id]
    st.session_state['tasks_df'] = df
    sync_to_cloud()

# --- Execution ---
# 1. Load Data (from Cache if exists, or Cloud)
load_data(force_refresh=False)

# 2. Run Logic
run_auto_promote()

# 3. Get Data for UI
all_tasks = st.session_state['tasks_df'].to_dict('records')

# --- Main Layout ---
# Sidebar first for mobile responsiveness
with st.sidebar:
    c_title, c_ref = st.columns([3, 1])
    with c_title: st.title("📜 History")
    with c_ref: 
        if st.button("🔄", help="Force Sync from Cloud"):
            load_data(force_refresh=True)
            st.rerun()

    st.markdown("---")
    
    completed = [t for t in all_tasks if t['completed']]
    completed = sorted(completed, key=lambda x: x['completed_at'] if x['completed_at'] else '0', reverse=True)

    if not completed:
        st.markdown("<p style='color:gray; font-size:0.9rem;'>No completed tasks.</p>", unsafe_allow_html=True)
        
    for task in completed:
        # Compact History Row with Icon Buttons
        st.markdown(f"""
        <div class="history-card">
            <div class="history-text">{task['text']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        c_spacer, c_undo, c_del = st.columns([2, 1, 1])
        with c_undo:
            if st.button("↩️", key=f"u_{task['id']}", help="Restore to list"):
                toggle_complete(task['id'], True); st.rerun()
        with c_del:
            if st.button("✕", key=f"d_{task['id']}", help="Delete permanently"):
                delete_task(task['id']); st.rerun()

col_main = st.container()

# --- Main Content ---
with col_main:
    st.title("Task Master Pro")
    st.markdown(f"<p style='color:#64748b; margin-top:-15px;'>{get_current_time().strftime('%A, %B %d')}</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # 1. Metrics Dashboard
    active = [t for t in all_tasks if not t['completed']]
    m1, m2, m3 = st.columns(3)
    m1.metric("Pending Tasks", len(active))
    m2.metric("Done Today", len([t for t in completed if t['completed_at'] and t['completed_at'][:10] == get_today_str()]))
    m3.metric("Total Tasks", len(all_tasks))

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Add Task (Glassmorphism Wrapper)
    st.markdown('<div class="input-wrapper">', unsafe_allow_html=True)
    with st.form("add_form", clear_on_submit=True, border=False):
        c1, c2, c3 = st.columns([3, 1.2, 0.8])
        txt = c1.text_input("New Task", placeholder="✨ Add a new task...", label_visibility="collapsed")
        prio = c2.selectbox("Priority", ["High", "Medium", "Low"], label_visibility="collapsed")
        if c3.form_submit_button("Add", type="primary", use_container_width=True):
            if txt: add_task(txt, prio); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # 3. Task List
    sorted_active = sorted(active, key=lambda x: x.get('custom_sort_index', 0), reverse=True)

    if not sorted_active:
        st.markdown("""
        <div style='text-align: center; padding: 40px; background: #f8fafc; border-radius: 12px; color: #64748b; margin-top:20px;'>
            <h3>🎉 All Clean!</h3>
            <p>You have zero pending tasks. Enjoy your day!</p>
        </div>
        """, unsafe_allow_html=True)

    for i, task in enumerate(sorted_active):
        p_class = f"border-{task['priority'].lower()}"
        b_class = f"badge-{task['priority'].lower()}"
        
        # We use a container to act as the 'card'
        with st.container():
            # Columns: Checkbox | Content | Sort | Actions
            c_check, c_content, c_move, c_edit = st.columns([0.3, 4, 0.6, 0.3])
            
            # Checkbox
            c_check.write("")
            c_check.write("")
            c_check.checkbox("", key=f"c_{task['id']}", on_change=toggle_complete, args=(task['id'], False))
            
            # Card Content (HTML)
            badges = f'<span class="badge {b_class}">{task["priority"]}</span>'
            if task['was_auto_promoted']: badges += '<span class="badge badge-promo">⚠️ Carried Over</span>'
            
            c_content.markdown(f"""
            <div class="task-card {p_class}">
                <span class="task-text">{task['text']}</span>
                <div>{badges}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Move Buttons (Up/Down) - Minimal UI
            with c_move:
                st.write("")
                st.write("")
                if i > 0:
                    if st.button("↑", key=f"up_{task['id']}", help="Move Up"):
                        move_task(task['id'], 'up'); st.rerun()
                if i < len(sorted_active) - 1:
                    if st.button("↓", key=f"dn_{task['id']}", help="Move Down"):
                        move_task(task['id'], 'down'); st.rerun()

            # Menu (Edit/Delete)
            with c_edit:
                st.write("")
                st.write("")
                with st.popover("⋮"):
                    st.caption("Edit Task")
                    e_txt = st.text_input("Name", task['text'], key=f"e_{task['id']}")
                    
                    opts = ["High", "Medium", "Low"]
                    curr = task['priority'] if task['priority'] in opts else "Medium"
                    e_prio = st.selectbox("Priority", opts, index=opts.index(curr), key=f"ep_{task['id']}")
                    
                    if st.button("💾 Save", key=f"sv_{task['id']}", type="primary", use_container_width=True):
                        update_task_details(task['id'], e_txt, e_prio); st.rerun()
                    
                    st.divider()
                    if st.button("🗑️ Delete", key=f"dl_{task['id']}", use_container_width=True):
                        delete_task(task['id']); st.rerun()
