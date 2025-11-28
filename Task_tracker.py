import streamlit as st
import pandas as pd
import datetime
import uuid
import pytz
import time
import random
from streamlit_gsheets import GSheetsConnection
from streamlit_sortables import sort_items

# --- Configuration ---
st.set_page_config(page_title="Task Master Pro", page_icon="⚡", layout="wide")
TIMEZONE = 'Asia/Kolkata' 

# --- Professional UI & CSS Styling ---
st.markdown("""
    <style>
    /* --- GLOBAL & BACKGROUND --- */
    .stApp {
        background-color: #0f172a; /* Slate 900 */
        background-image: 
            radial-gradient(at 0% 0%, rgba(56, 189, 248, 0.08) 0px, transparent 50%), 
            radial-gradient(at 100% 0%, rgba(99, 102, 241, 0.08) 0px, transparent 50%);
    }
    
    .block-container { 
        padding-top: 2rem; 
        padding-bottom: 5rem; 
        max-width: 1100px;
    }
    
    /* --- ANIMATIONS --- */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(5px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* --- METRICS DASHBOARD --- */
    div[data-testid="metric-container"] {
        background-color: #1e293b; 
        border: 1px solid #334155;
        padding: 12px 16px;
        border-radius: 10px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transition: transform 0.2s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        border-color: #475569;
    }
    div[data-testid="metric-container"] label {
        font-size: 0.8rem;
        color: #94a3b8; 
    }
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
        font-size: 1.5rem;
        color: #f8fafc;
        font-weight: 700;
    }

    /* --- INPUT WRAPPER --- */
    .input-wrapper {
        background-color: #1e293b;
        border: 1px solid #334155;
        padding: 16px;
        border-radius: 12px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        margin-bottom: 30px;
    }

    /* --- COMPACT TASK CARD --- */
    .task-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 10px 14px;
        margin-bottom: 8px;
        
        /* Smooth Animation */
        animation: fadeIn 0.3s ease-out forwards;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        
        display: flex;
        flex-direction: column;
    }
    .task-card:hover {
        background-color: #253045; 
        border-color: #475569;
        transform: translateX(4px);
    }
    
    /* Elegant Priority Stripes */
    .border-high { border-left: 3px solid #ef4444 !important; }   
    .border-medium { border-left: 3px solid #f59e0b !important; } 
    .border-low { border-left: 3px solid #10b981 !important; }    

    /* --- TYPOGRAPHY --- */
    .task-text {
        font-size: 0.95rem;
        font-weight: 500;
        color: #f1f5f9; 
        margin-bottom: 4px;
        font-family: 'Inter', sans-serif;
    }
    
    /* --- BADGES --- */
    .badge {
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.6rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        display: inline-block;
        margin-right: 6px;
    }
    .badge-high { color: #fecaca; background-color: rgba(239, 68, 68, 0.2); border: 1px solid rgba(239, 68, 68, 0.3); }
    .badge-medium { color: #fde68a; background-color: rgba(245, 158, 11, 0.2); border: 1px solid rgba(245, 158, 11, 0.3); }
    .badge-low { color: #a7f3d0; background-color: rgba(16, 185, 129, 0.2); border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-promo { color: #fdba74; background-color: rgba(249, 115, 22, 0.15); border: 1px dashed rgba(249, 115, 22, 0.4); }

    /* --- SIDEBAR --- */
    section[data-testid="stSidebar"] {
        background-color: #0f172a; 
        border-right: 1px solid #1e293b;
    }
    .history-card {
        padding: 8px 12px;
        border-radius: 6px;
        border: 1px solid #334155;
        background-color: #162032;
        margin-bottom: 6px;
    }
    .history-text {
        color: #64748b;
        text-decoration: line-through;
        font-size: 0.8rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    /* --- BUTTONS --- */
    .stButton button {
        border-radius: 6px;
        font-weight: 500;
        transition: all 0.2s;
    }
    
    /* Checkbox Alignment Fix */
    div[data-testid="stCheckbox"] {
        padding-top: 12px;
    }
    
    /* Hide Streamlit Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
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
        
        # Initialize sort index if missing
        if df['custom_sort_index'].isnull().all() and not df.empty:
            df['custom_sort_index'] = range(len(df), 0, -1) # Default reverse order
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
        
        # Bump promoted to top
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
        sync_to_cloud() 
        if mask_promote.sum() > 0: st.toast(f"🚀 Promoted {mask_promote.sum()} tasks!")
    
    st.session_state['auto_promote_ran'] = True

# --- Actions ---
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

def handle_sort_change(sorted_list):
    """Updates the custom_sort_index based on the new order from drag-and-drop."""
    df = st.session_state['tasks_df']
    
    total_items = len(sorted_list)
    for rank, item_text in enumerate(sorted_list):
        # We reconstruct the index based on the returned list order
        mask = (df['text'] == item_text) & (df['completed'] == False)
        if mask.any():
            # Highest rank = Top item
            df.loc[mask, 'custom_sort_index'] = total_items - rank

    st.session_state['tasks_df'] = df
    sync_to_cloud()
    st.rerun()

# --- Execution ---
load_data(force_refresh=False)
run_auto_promote()
all_tasks = st.session_state['tasks_df'].to_dict('records')

# --- Main Layout ---
with st.sidebar:
    c_title, c_ref = st.columns([3, 1])
    with c_title: st.title("History")
    with c_ref: 
        if st.button("🔄", help="Force Sync"):
            load_data(force_refresh=True)
            st.rerun()

    st.markdown("---")
    
    completed = [t for t in all_tasks if t['completed']]
    completed = sorted(completed, key=lambda x: x['completed_at'] if x['completed_at'] else '0', reverse=True)

    if not completed:
        st.markdown("<p style='color:#64748b; font-size:0.8rem; font-style:italic;'>No completed tasks.</p>", unsafe_allow_html=True)
        
    for task in completed:
        st.markdown(f"""
        <div class="history-card">
            <div class="history-text">{task['text']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        c_spacer, c_undo, c_del = st.columns([1.5, 1, 1])
        with c_undo:
            if st.button("↩️", key=f"u_{task['id']}", help="Restore"):
                toggle_complete(task['id'], True); st.rerun()
        with c_del:
            if st.button("✕", key=f"d_{task['id']}", help="Delete"):
                delete_task(task['id']); st.rerun()

col_main = st.container()

# --- Main Content ---
with col_main:
    st.title("Task Master Pro")
    st.caption(f"{get_current_time().strftime('%A, %B %d')}")
    st.markdown("<br>", unsafe_allow_html=True)

    # 1. Metrics
    active = [t for t in all_tasks if not t['completed']]
    m1, m2, m3 = st.columns(3)
    m1.metric("Pending", len(active))
    m2.metric("Done Today", len([t for t in completed if t['completed_at'] and t['completed_at'][:10] == get_today_str()]))
    m3.metric("Total", len(all_tasks))

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Add Task
    st.markdown('<div class="input-wrapper">', unsafe_allow_html=True)
    with st.form("add_form", clear_on_submit=True, border=False):
        c1, c2, c3 = st.columns([3, 1.2, 0.8])
        txt = c1.text_input("New Task", placeholder="Add a new task...", label_visibility="collapsed")
        prio = c2.selectbox("Priority", ["High", "Medium", "Low"], label_visibility="collapsed")
        if c3.form_submit_button("Add", type="primary", use_container_width=True):
            if txt: add_task(txt, prio); st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # 3. Task List - MODE SWITCHING
    sorted_active = sorted(active, key=lambda x: x.get('custom_sort_index', 0), reverse=True)

    if not sorted_active:
        st.markdown("""
        <div style='text-align: center; padding: 30px; background: rgba(255,255,255,0.05); border: 1px dashed #334155; border-radius: 12px; color: #94a3b8; margin-top:10px;'>
            <p>🎉 Zero pending tasks!</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # MODE TOGGLE
        col_lbl, col_tog = st.columns([0.8, 0.2])
        with col_lbl: st.caption("Active Tasks")
        with col_tog: reorder_mode = st.toggle("Reorder Mode", key="reorder_toggle")
        
        if reorder_mode:
            # --- DRAG & DROP VIEW ---
            st.info("💡 Drag items to reorder, then switch toggle OFF to edit.")
            sortable_list = [t['text'] for t in sorted_active]
            sorted_items = sort_items(sortable_list)
            
            if sorted_items != sortable_list:
                handle_sort_change(sorted_items)
        else:
            # --- DETAILED CARD VIEW ---
            for i, task in enumerate(sorted_active):
                p_class = f"border-{task['priority'].lower()}"
                b_class = f"badge-{task['priority'].lower()}"
                
                with st.container():
                    c_check, c_content, c_edit = st.columns([0.25, 4.5, 0.25])
                    
                    c_check.write("") 
                    c_check.checkbox("", key=f"c_{task['id']}", on_change=toggle_complete, args=(task['id'], False))
                    
                    badges = f'<span class="badge {b_class}">{task["priority"]}</span>'
                    if task['was_auto_promoted']: badges += '<span class="badge badge-promo">⚠️ Carried Over</span>'
                    
                    c_content.markdown(f"""
                    <div class="task-card {p_class}">
                        <span class="task-text">{task['text']}</span>
                        <div>{badges}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    with c_edit:
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
