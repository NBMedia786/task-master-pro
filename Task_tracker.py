import streamlit as st
import pandas as pd
import datetime
import uuid
import pytz
import time
import random
from streamlit_gsheets import GSheetsConnection

# --- Configuration ---
st.set_page_config(page_title="Task Master Pro", page_icon="✅", layout="wide")
TIMEZONE = 'Asia/Kolkata' 

# --- Professional UI & CSS Styling ---
st.markdown("""
    <style>
    /* Global Settings */
    .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
    
    /* --- Task Card Design --- */
    .task-card {
        background-color: #ffffff;
        border: 1px solid #f0f2f6;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.03);
        transition: all 0.2s ease;
        border-left-width: 5px; /* Stripe width */
    }
    .task-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0,0,0,0.08);
    }
    
    /* Priority Stripes (The colorful part) */
    .border-high { border-left-color: #ef4444 !important; }   /* Red */
    .border-medium { border-left-color: #f59e0b !important; } /* Amber */
    .border-low { border-left-color: #10b981 !important; }    /* Emerald */
    
    /* Dark Mode Adjustments */
    @media (prefers-color-scheme: dark) {
        .task-card { 
            background-color: #262730; 
            border-color: #3f3f46; 
        }
    }

    /* --- Badges --- */
    .badge {
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        display: inline-flex;
        align-items: center;
        margin-right: 8px;
    }
    .badge-high { color: #991b1b; background-color: #fee2e2; }
    .badge-medium { color: #92400e; background-color: #fef3c7; }
    .badge-low { color: #065f46; background-color: #d1fae5; }
    .badge-promo { color: #7c2d12; background-color: #ffedd5; border: 1px dashed #fdba74; }

    /* --- Typography --- */
    .task-text {
        font-size: 1.05rem;
        font-weight: 500;
        color: #1f2937;
        line-height: 1.4;
    }
    @media (prefers-color-scheme: dark) {
        .task-text { color: #e4e4e7; }
    }
    
    /* --- Input Form Container --- */
    .input-container {
        background-color: #f8fafc;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        margin-bottom: 25px;
    }
    @media (prefers-color-scheme: dark) {
        .input-container { background-color: #18181b; border-color: #27272a; }
    }

    /* --- Buttons --- */
    /* Make up/down buttons minimal */
    div[data-testid="column"] button {
        padding: 0px 8px;
        min-height: 32px;
        border: none;
        background: transparent;
    }
    div[data-testid="column"] button:hover {
        background-color: #f4f4f5;
        color: #2563eb;
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

def save_data(df):
    conn = get_gsheets_conn()
    def write_op(): conn.update(worksheet='Tasks', data=df)
    try:
        retry_operation(write_op)
        st.cache_data.clear()
    except Exception as e:
        st.toast(f"⚠️ Could not save: {e}")

def fetch_data(init_if_missing=True, error_handling='stop'):
    conn = get_gsheets_conn()
    cols = ['id', 'text', 'priority', 'completed', 'created_at', 'completed_at', 'was_auto_promoted', 'custom_sort_index']
    
    try:
        def read_op(): return conn.read(worksheet='Tasks', usecols=list(range(len(cols))), ttl=0)
        df = retry_operation(read_op)
        
        if df is None: df = pd.DataFrame(columns=cols)
        if df.empty: df = pd.DataFrame(columns=cols) if df.columns.empty else df

        for col in cols:
            if col not in df.columns: df[col] = None
        
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
        return df
        
    except Exception as e:
        if "WorksheetNotFound" in str(e) and init_if_missing:
            df_new = pd.DataFrame(columns=cols)
            save_data(df_new)
            return df_new
        msg = f"Unable to load data: {e}"
        if error_handling == 'stop': st.error(msg); st.stop()
        elif error_handling == 'toast': st.toast("⚠️ Server busy. Please wait 10s."); return None
        return None

def run_auto_promote(df):
    if 'auto_promote_ran' in st.session_state: return df
    if df.empty: st.session_state['auto_promote_ran'] = True; return df
    
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
        save_data(df)
        if mask_promote.sum() > 0: st.toast(f"🚀 Promoted {mask_promote.sum()} tasks!")
    
    st.session_state['auto_promote_ran'] = True
    return df

def add_task(text, priority):
    df = fetch_data(error_handling='toast')
    if df is None: return 
    max_idx = df['custom_sort_index'].max()
    if pd.isna(max_idx): max_idx = 0
    new_row = pd.DataFrame([{
        'id': str(uuid.uuid4()), 'text': text, 'priority': priority, 'completed': False,
        'created_at': str(get_current_time()), 'completed_at': None, 'was_auto_promoted': False,
        'custom_sort_index': max_idx + 1
    }])
    df = pd.concat([df, new_row], ignore_index=True)
    save_data(df)
    st.toast("Task Added!")

def move_task(task_id, direction):
    df = fetch_data(error_handling='toast')
    if df is None: return
    df = df.sort_values(by='custom_sort_index', ascending=False).reset_index(drop=True)
    try: current_idx = df[df['id'] == str(task_id)].index[0]
    except IndexError: st.toast("⚠️ Task not found."); return

    swap_idx = None
    if direction == 'up' and current_idx > 0: swap_idx = current_idx - 1
    elif direction == 'down' and current_idx < len(df) - 1: swap_idx = current_idx + 1
        
    if swap_idx is not None:
        val_curr = df.at[current_idx, 'custom_sort_index']
        val_swap = df.at[swap_idx, 'custom_sort_index']
        if val_curr == val_swap: val_swap += 1
        df.at[current_idx, 'custom_sort_index'] = val_swap
        df.at[swap_idx, 'custom_sort_index'] = val_curr
        save_data(df)

def toggle_complete(task_id, current_val):
    df = fetch_data(error_handling='toast')
    if df is None: return
    target_id = str(task_id)
    if target_id not in df['id'].values: st.toast("⚠️ Task not found."); return
    mask = df['id'] == target_id
    new_val = not current_val
    df.loc[mask, 'completed'] = new_val
    df.loc[mask, 'completed_at'] = str(get_current_time()) if new_val else None
    save_data(df)

def update_task_details(task_id, new_text, new_priority):
    df = fetch_data(error_handling='toast')
    if df is None: return
    target_id = str(task_id)
    if target_id not in df['id'].values: st.toast("⚠️ Task not found."); return
    mask = df['id'] == target_id
    df.loc[mask, 'text'] = new_text
    df.loc[mask, 'priority'] = new_priority
    df.loc[mask, 'was_auto_promoted'] = False
    save_data(df)
    st.toast("Task Updated!")

def delete_task(task_id):
    df = fetch_data(error_handling='toast')
    if df is None: return
    target_id = str(task_id)
    if target_id not in df['id'].values: st.toast("⚠️ Task not found."); return
    df = df[df['id'] != target_id]
    save_data(df)
    st.toast("Task Deleted!")

# --- Execution ---
data = fetch_data(init_if_missing=True, error_handling='stop')
data = run_auto_promote(data)
all_tasks = data.to_dict('records')

# --- Main Layout ---
col_main, col_sidebar = st.columns([2.5, 1])

# --- Sidebar: History ---
with col_sidebar:
    st.markdown("### 📜 History")
    completed = [t for t in all_tasks if t['completed']]
    completed = sorted(completed, key=lambda x: x['completed_at'] if x['completed_at'] else '0', reverse=True)

    if not completed:
        st.info("No completed tasks yet.")
        
    for task in completed:
        with st.container():
            st.markdown(f"""
            <div style="padding: 10px; background-color: #f9fafb; border-radius: 6px; margin-bottom: 8px; border-left: 3px solid #cbd5e1;">
                <div style="font-size: 0.9rem; font-weight: 500; text-decoration: line-through; color: #64748b;">{task['text']}</div>
            </div>
            """, unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            if c1.button("Undo", key=f"u_{task['id']}", use_container_width=True):
                toggle_complete(task['id'], True); st.rerun()
            if c2.button("Clear", key=f"d_{task['id']}", use_container_width=True):
                delete_task(task['id']); st.rerun()

# --- Main Content ---
with col_main:
    # 1. Header & Progress Dashboard
    st.title("Task Master Pro")
    
    active = [t for t in all_tasks if not t['completed']]
    total_today = len(active) + len([t for t in completed if t['completed_at'] and t['completed_at'][:10] == get_today_str()])
    done_today = len([t for t in completed if t['completed_at'] and t['completed_at'][:10] == get_today_str()])
    
    if total_today > 0:
        progress = done_today / total_today
        st.progress(progress, text=f"Daily Progress: {int(progress*100)}%")
    else:
        st.progress(0, text="Ready to start the day!")
    
    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Add Task Form (Styled Container)
    with st.container():
        st.markdown('<div class="input-container">', unsafe_allow_html=True)
        with st.form("add_form", clear_on_submit=True, border=False):
            c1, c2, c3 = st.columns([3, 1.5, 1])
            txt = c1.text_input("New Task", placeholder="What needs to be done?", label_visibility="collapsed")
            prio = c2.selectbox("Priority", ["High", "Medium", "Low"], label_visibility="collapsed")
            if c3.form_submit_button("➕ Add Task", type="primary", use_container_width=True):
                if txt: add_task(txt, prio); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # 3. Task List (Sorted by custom index)
    # Important: sort by custom_sort_index DESC so highest index is at TOP
    sorted_active = sorted(active, key=lambda x: x.get('custom_sort_index', 0), reverse=True)

    if not sorted_active:
        st.success("🎉 All caught up! Enjoy your day.")

    for i, task in enumerate(sorted_active):
        p_class = f"border-{task['priority'].lower()}"
        b_class = f"badge-{task['priority'].lower()}"
        
        # Render Card
        with st.container():
            c_check, c_content, c_move, c_edit = st.columns([0.4, 4, 0.8, 0.4])
            
            # Checkbox
            c_check.write("")
            c_check.checkbox("", key=f"c_{task['id']}", on_change=toggle_complete, args=(task['id'], False))
            
            # Content
            badges = f'<span class="badge {b_class}">{task["priority"]}</span>'
            if task['was_auto_promoted']: badges += '<span class="badge badge-promo">⚠️ Carried Over</span>'
            
            c_content.markdown(f"""
            <div class="task-card {p_class}">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span class="task-text">{task['text']}</span>
                </div>
                <div style="margin-top:6px;">{badges}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Move Buttons (Up/Down)
            with c_move:
                st.write("") # Spacer
                if i > 0: # Can move up
                    if st.button("⬆️", key=f"up_{task['id']}"):
                        move_task(task['id'], 'up'); st.rerun()
                if i < len(sorted_active) - 1: # Can move down
                    if st.button("⬇️", key=f"dn_{task['id']}"):
                        move_task(task['id'], 'down'); st.rerun()

            # Edit/Delete Popover
            with c_edit:
                st.write("")
                with st.popover("⋮"):
                    e_txt = st.text_input("Edit", task['text'], key=f"e_{task['id']}")
                    
                    opts = ["High", "Medium", "Low"]
                    curr = task['priority'] if task['priority'] in opts else "Medium"
                    e_prio = st.selectbox("Priority", opts, index=opts.index(curr), key=f"ep_{task['id']}")
                    
                    c_save, c_del = st.columns(2)
                    if c_save.button("Save", key=f"sv_{task['id']}", type="primary", use_container_width=True):
                        update_task_details(task['id'], e_txt, e_prio); st.rerun()
                    
                    if c_del.button("Delete", key=f"dl_{task['id']}", use_container_width=True):
                        delete_task(task['id']); st.rerun()
