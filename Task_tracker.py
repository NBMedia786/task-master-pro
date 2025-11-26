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

# --- CSS Styling ---
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    .task-card {
        background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 10px;
        padding: 15px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    @media (prefers-color-scheme: dark) {
        .task-card { background-color: #262730; border-color: #41424b; }
    }
    .badge {
        padding: 4px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 600;
        display: inline-flex; align-items: center; margin-right: 8px;
    }
    .priority-high { color: #991b1b; background-color: #fecaca; border: 1px solid #f87171; }
    .priority-medium { color: #92400e; background-color: #fde68a; border: 1px solid #fbbf24; }
    .priority-low { color: #065f46; background-color: #a7f3d0; border: 1px solid #34d399; }
    .carried-over { color: #c2410c; background-color: #ffedd5; border: 1px dashed #fdba74; font-size: 0.7rem; padding: 2px 8px; }
    .task-text { font-size: 1.1rem; font-weight: 500; }
    .history-item { border-left: 3px solid #4f46e5; padding-left: 12px; margin-bottom: 16px; }
    .history-text { font-size: 0.95rem; font-weight: 500; margin-bottom: 2px; }
    .history-time { font-size: 0.75rem; color: #9ca3af; }
    .stButton button { border-radius: 6px; font-weight: 500; }
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

def retry_operation(func, retries=3):
    """Retries a function if it hits a rate limit error. Reduced retries to prevent long waits."""
    for i in range(retries):
        try:
            return func()
        except Exception as e:
            error_str = str(e)
            # Check for rate limit (429) or resource exhausted errors
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "Quota exceeded" in error_str:
                wait_time = (2 ** i) + random.random() # Exponential backoff
                time.sleep(wait_time)
                continue
            else:
                raise e # Re-raise if it's a different error
    raise Exception("Max retries exceeded for API operation")

def fetch_data():
    """Fetches data safely with retries. Returns df. If error, stops app execution."""
    conn = get_gsheets_conn()
    cols = ['id', 'text', 'priority', 'completed', 'created_at', 'completed_at', 'was_auto_promoted']
    
    try:
        # Define the read operation
        def read_op():
            return conn.read(worksheet='Tasks', usecols=list(range(len(cols))), ttl=0)
            
        # Execute with retry logic
        df = retry_operation(read_op)
        
        # Handle empty/None returns safely
        if df is None:
             return pd.DataFrame(columns=cols)
        if df.empty:
             return pd.DataFrame(columns=cols) if df.columns.empty else df

        # Ensure schema matches
        for col in cols:
            if col not in df.columns:
                df[col] = None
                
        # Type cleanup
        df['id'] = df['id'].astype(str)
        def clean_bool(x):
            if isinstance(x, bool): return x
            if isinstance(x, (int, float)): return bool(x)
            return str(x).lower() in ['true', '1', 'yes']

        if 'completed' in df.columns:
            df['completed'] = df['completed'].apply(clean_bool)
        if 'was_auto_promoted' in df.columns:
            df['was_auto_promoted'] = df['was_auto_promoted'].apply(clean_bool)
            
        df['created_at'] = df['created_at'].astype(str).replace('nan', '')
        df['completed_at'] = df['completed_at'].astype(str).replace('nan', None)
        
        return df
        
    except Exception as e:
        st.error(f"Unable to load data (Retrying might help): {e}")
        st.stop()

def save_data(df):
    """Saves data to Google Sheets with retries."""
    conn = get_gsheets_conn()
    
    def write_op():
        conn.update(worksheet='Tasks', data=df)
        
    try:
        retry_operation(write_op)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Failed to save data: {e}")

def init_db():
    """Initializes the DB only if it is missing."""
    conn = get_gsheets_conn()
    required_cols = ['id', 'text', 'priority', 'completed', 'created_at', 'completed_at', 'was_auto_promoted']
    
    try:
        def check_op():
            conn.read(worksheet='Tasks', ttl=0)
        retry_operation(check_op)
    except Exception as e:
        if "WorksheetNotFound" in str(e):
             df = pd.DataFrame(columns=required_cols)
             save_data(df)
        # Else: ignore. Let fetch_data catch it.

def run_auto_promote():
    # --- FIX: Only run this logic ONCE per session to allow manual overrides ---
    if 'auto_promote_ran' in st.session_state:
        return
        
    df = fetch_data()
    if df.empty: return
    
    today_str = get_today_str()
    updates = 0
    
    mask_promote = (
        (df['completed'] == False) & 
        (df['priority'] != 'High') & 
        (df['created_at'].str[:10] < today_str) &
        (df['created_at'].str[:10] != '')
    )
    if mask_promote.any():
        df.loc[mask_promote, 'priority'] = 'High'
        df.loc[mask_promote, 'was_auto_promoted'] = True
        updates += 1
    
    mask_carried = (
        (df['completed'] == False) & 
        (df['priority'] == 'High') & 
        (df['was_auto_promoted'] == False) & 
        (df['created_at'].str[:10] < today_str) &
        (df['created_at'].str[:10] != '')
    )
    if mask_carried.any():
        df.loc[mask_carried, 'was_auto_promoted'] = True
        updates += 1
    
    if updates > 0:
        save_data(df)
        if mask_promote.sum() > 0:
            st.toast(f"🚀 Promoted {mask_promote.sum()} tasks!")
    
    # Mark as ran so it doesn't fight the user on next reload
    st.session_state['auto_promote_ran'] = True

def add_task(text, priority):
    df = fetch_data()
    
    new_row = pd.DataFrame([{
        'id': str(uuid.uuid4()),
        'text': text,
        'priority': priority,
        'completed': False,
        'created_at': str(get_current_time()),
        'completed_at': None,
        'was_auto_promoted': False
    }])
    df = pd.concat([df, new_row], ignore_index=True)
    save_data(df)
    st.toast("Task Added!")

def toggle_complete(task_id, current_val):
    df = fetch_data()
    target_id = str(task_id)
    
    # SAFETY CHECK: Only proceed if ID exists
    if target_id not in df['id'].values:
        st.toast("⚠️ Task not found (sync error). Refreshing...")
        return

    mask = df['id'] == target_id
    new_val = not current_val
    df.loc[mask, 'completed'] = new_val
    df.loc[mask, 'completed_at'] = str(get_current_time()) if new_val else None
    
    save_data(df)

def update_task_details(task_id, new_text, new_priority):
    df = fetch_data()
    target_id = str(task_id)
    
    # SAFETY CHECK
    if target_id not in df['id'].values:
        st.toast("⚠️ Task not found. Cannot update.")
        return

    mask = df['id'] == target_id
    df.loc[mask, 'text'] = new_text
    df.loc[mask, 'priority'] = new_priority
    # FIX: If user manually updates, remove the 'auto promoted' flag so badge disappears
    df.loc[mask, 'was_auto_promoted'] = False
    
    save_data(df)
    st.toast("Task Updated!")

def delete_task(task_id):
    df = fetch_data()
    target_id = str(task_id)
    
    # CRITICAL SAFETY CHECK
    if target_id not in df['id'].values:
        st.toast("⚠️ Task not found (already deleted?). Data preserved.")
        return

    # Filter out the task
    df = df[df['id'] != target_id]
    
    # Save only after verification
    save_data(df)
    st.toast("Task Deleted!")

# --- Execution ---
init_db()
run_auto_promote()

# Safe Fetch
data = fetch_data()
all_tasks = data.to_dict('records')

# --- Layout ---
col_main, col_sidebar = st.columns([3, 1])

with st.sidebar:
    st.title("✅ History")
    st.markdown("---")
    completed_tasks = [t for t in all_tasks if t['completed']]
    completed_tasks = sorted(completed_tasks, key=lambda x: x['completed_at'] if x['completed_at'] else '0', reverse=True)

    if not completed_tasks:
        st.info("No completed tasks.")
    
    for task in completed_tasks:
        time_str = "Recently"
        if task['completed_at'] and task['completed_at'] != 'None':
            try:
                dt_obj = datetime.datetime.fromisoformat(task['completed_at'])
                if dt_obj.date() == get_current_time().date():
                    time_str = f"Today, {dt_obj.strftime('%I:%M %p')}"
                else:
                    time_str = dt_obj.strftime("%b %d")
            except: pass

        with st.container():
            st.markdown(f"""<div class="history-item"><div class="history-text">{task['text']}</div><div class="history-time">{time_str}</div></div>""", unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            if b1.button("↺", key=f"undo_{task['id']}"):
                toggle_complete(task['id'], True)
                st.rerun()
            if b2.button("🗑️", key=f"del_h_{task['id']}"):
                delete_task(task['id'])
                st.rerun()
            st.markdown("---")

with col_main:
    st.title("Task Master Pro 🚀")
    
    with st.container():
        with st.form("add_form", clear_on_submit=True):
            c1, c2, c3 = st.columns([4, 2, 1])
            txt = c1.text_input("New Task", placeholder="Task name...", label_visibility="collapsed")
            prio = c2.selectbox("Priority", ["High", "Medium", "Low"], label_visibility="collapsed")
            if c3.form_submit_button("Add Task", type="primary"):
                if txt:
                    add_task(txt, prio)
                    st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    
    active_tasks = [t for t in all_tasks if not t['completed']]
    priority_map = {"High": 3, "Medium": 2, "Low": 1}
    active_tasks = sorted(active_tasks, key=lambda x: x['created_at'], reverse=True)
    active_tasks = sorted(active_tasks, key=lambda x: priority_map.get(x['priority'], 1), reverse=True)

    if not active_tasks:
        st.success("🎉 All caught up!")

    for task in active_tasks:
        p_class = f"priority-{task['priority'].lower()}"
        with st.container():
            c_check, c_content, c_actions = st.columns([0.5, 5, 0.5])
            c_check.write("")
            c_check.checkbox("", key=f"check_{task['id']}", on_change=toggle_complete, args=(task['id'], False))
            
            badges = f'<span class="badge {p_class}">{task["priority"]}</span>'
            if task['was_auto_promoted']: badges += '<span class="badge carried-over">⚠️ Carried Over</span>'
            
            c_content.markdown(f"""<div style="margin-bottom: 4px;"><span class="task-text">{task['text']}</span></div><div>{badges}</div>""", unsafe_allow_html=True)
            
            with c_actions.popover("⋮"):
                e_txt = st.text_input("Text", task['text'], key=f"e_{task['id']}")
                
                # --- FIX: SAFE PRIORITY SELECTION ---
                prio_options = ["High", "Medium", "Low"]
                curr_prio = task['priority']
                if curr_prio not in prio_options:
                    curr_prio = "Medium" # Fallback to prevent crash
                
                e_prio = st.selectbox("Level", prio_options, index=prio_options.index(curr_prio), key=f"ep_{task['id']}")
                
                if st.button("Save", key=f"sv_{task['id']}"):
                    update_task_details(task['id'], e_txt, e_prio)
                    st.rerun()
                st.divider()
                if st.button("Delete", key=f"dl_{task['id']}", type="primary"):
                    delete_task(task['id'])
                    st.rerun()
            st.markdown("---")
