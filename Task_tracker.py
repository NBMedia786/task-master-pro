import streamlit as st
import pandas as pd
import datetime
from datetime import date
import uuid
import pytz
from streamlit_gsheets import GSheetsConnection

# --- Configuration ---
st.set_page_config(page_title="Task Master Pro", page_icon="✅", layout="wide")

# Set your timezone here (e.g., 'Asia/Kolkata', 'US/Pacific', 'UTC')
TIMEZONE = 'Asia/Kolkata' 

# --- Professional UI & CSS Styling ---
st.markdown("""
    <style>
    /* Main Font & Reset */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Task Card Styling */
    .task-card {
        background-color: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        transition: transform 0.1s ease-in-out;
    }
    .task-card:hover {
        border-color: #d1d5db;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    
    /* Dark Mode Support for Cards */
    @media (prefers-color-scheme: dark) {
        .task-card {
            background-color: #262730;
            border-color: #41424b;
        }
        .task-card:hover {
            border-color: #565863;
        }
    }

    /* Priority Badges */
    .badge {
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.5px;
        display: inline-flex;
        align-items: center;
        margin-right: 8px;
    }
    .priority-high { color: #991b1b; background-color: #fecaca; border: 1px solid #f87171; }
    .priority-medium { color: #92400e; background-color: #fde68a; border: 1px solid #fbbf24; }
    .priority-low { color: #065f46; background-color: #a7f3d0; border: 1px solid #34d399; }
    
    .carried-over { 
        color: #c2410c; 
        background-color: #ffedd5; 
        border: 1px dashed #fdba74;
        font-size: 0.7rem;
        padding: 2px 8px;
    }

    /* Text Styling */
    .task-text {
        font-size: 1.1rem;
        font-weight: 500;
        color: #1f2937;
    }
    .task-meta {
        font-size: 0.8rem;
        color: #6b7280;
        margin-top: 4px;
    }
    
    /* Sidebar History Styling */
    .history-item {
        border-left: 3px solid #4f46e5;
        padding-left: 12px;
        margin-bottom: 16px;
    }
    .history-text {
        font-size: 0.95rem;
        font-weight: 500;
        margin-bottom: 2px;
    }
    .history-time {
        font-size: 0.75rem;
        color: #9ca3af;
    }
    
    /* Custom Button override */
    .stButton button {
        border-radius: 6px;
        font-weight: 500;
    }
    </style>
""", unsafe_allow_html=True)

# --- Helpers ---
def get_current_time():
    """Get current time in the configured timezone."""
    tz = pytz.timezone(TIMEZONE)
    return datetime.datetime.now(tz)

def get_today_str():
    """Get today's date string in the configured timezone."""
    return get_current_time().strftime('%Y-%m-%d')

# --- Google Sheets Connection ---
@st.cache_resource
def get_gsheets_conn():
    return st.connection("gsheets", type=GSheetsConnection)

def fetch_data():
    """Robust data fetching with type safety."""
    conn = get_gsheets_conn()
    # Define columns explicitly
    cols = ['id', 'text', 'priority', 'completed', 'created_at', 'completed_at', 'was_auto_promoted']
    
    try:
        df = conn.read(worksheet='Tasks', usecols=list(range(len(cols))))
        
        # If the sheet is completely empty or missing headers
        if df.empty:
            return pd.DataFrame(columns=cols)
            
        # Ensure all columns exist, if not, add them
        for col in cols:
            if col not in df.columns:
                df[col] = None
                
        # --- TYPE SAFETY BLOCK ---
        # 1. ID: Ensure ID is string (UUID)
        df['id'] = df['id'].astype(str)
        
        # 2. Booleans: Handle Google Sheets varied boolean outputs (TRUE, 'TRUE', 1, '1')
        def clean_bool(x):
            if isinstance(x, bool): return x
            if isinstance(x, (int, float)): return bool(x)
            return str(x).lower() in ['true', '1', 'yes']

        if 'completed' in df.columns:
            df['completed'] = df['completed'].apply(clean_bool)
        if 'was_auto_promoted' in df.columns:
            df['was_auto_promoted'] = df['was_auto_promoted'].apply(clean_bool)
            
        # 3. Dates: Ensure strings
        df['created_at'] = df['created_at'].astype(str).replace('nan', '')
        df['completed_at'] = df['completed_at'].astype(str).replace('nan', None)
        
        return df
        
    except Exception:
        # Fallback if worksheet is missing or totally broken
        return pd.DataFrame(columns=cols)

def save_data(df):
    """Save dataframe to Google Sheets."""
    conn = get_gsheets_conn()
    conn.update(worksheet='Tasks', data=df)

def init_db():
    """Initialize the Google Sheets worksheet if needed."""
    conn = get_gsheets_conn()
    required_cols = ['id', 'text', 'priority', 'completed', 'created_at', 'completed_at', 'was_auto_promoted']
    
    try:
        # Try to read to see if it exists
        df = conn.read(worksheet='Tasks', usecols=list(range(len(required_cols))))
        if df.empty or not all(col in df.columns for col in required_cols):
             # Re-initialize headers if missing
             df = pd.DataFrame(columns=required_cols)
             save_data(df)
    except Exception:
        # If 'Tasks' worksheet doesn't exist, create an empty DF and write it.
        # Note: User must still ensure the 'Tasks' tab exists in the Sheet to avoid 
        # API errors, but this handles the data structure.
        df = pd.DataFrame(columns=required_cols)
        try:
            save_data(df)
        except Exception as e:
            st.error(f"Could not initialize 'Tasks' worksheet. Please ensure a tab named 'Tasks' exists in your Google Sheet. Error: {e}")
            st.stop()

def run_auto_promote():
    """Auto-promote old tasks to High priority."""
    df = fetch_data()
    
    if df.empty:
        return
    
    today_str = get_today_str()
    updates = 0
    
    # Logic: If created date < today AND not completed AND not High -> Promote
    # Using simple string comparison for dates works well for ISO format YYYY-MM-DD
    
    # 1. Identify tasks to promote
    mask_promote = (
        (df['completed'] == False) & 
        (df['priority'] != 'High') & 
        (df['created_at'].str[:10] < today_str) &
        (df['created_at'].str[:10] != '')
    )
    
    if mask_promote.any():
        df.loc[mask_promote, 'priority'] = 'High'
        df.loc[mask_promote, 'was_auto_promoted'] = True
        updates = mask_promote.sum()
    
    # 2. Identify tasks that are already High and carried over (for the UI badge)
    mask_carried = (
        (df['completed'] == False) & 
        (df['priority'] == 'High') & 
        (df['was_auto_promoted'] == False) & 
        (df['created_at'].str[:10] < today_str) &
        (df['created_at'].str[:10] != '')
    )
    
    if mask_carried.any():
        df.loc[mask_carried, 'was_auto_promoted'] = True
        updates += mask_carried.sum() # Count this as an update to trigger save
    
    if updates > 0:
        save_data(df)
        if mask_promote.sum() > 0:
            st.toast(f"🚀 Auto-promoted {mask_promote.sum()} old tasks to High Priority!")

def add_task(text, priority):
    """Add a new task."""
    df = fetch_data()
    
    new_row = pd.DataFrame([{
        'id': str(uuid.uuid4()), # Use UUID for robust unique IDs
        'text': text,
        'priority': priority,
        'completed': False,
        'created_at': str(get_current_time()),
        'completed_at': None,
        'was_auto_promoted': False
    }])
    
    df = pd.concat([df, new_row], ignore_index=True)
    save_data(df)

def toggle_complete(task_id, current_val):
    """Toggle task completion."""
    df = fetch_data()
    
    # Use string comparison for UUIDs
    mask = df['id'] == str(task_id)
    if mask.any():
        new_val = not current_val
        df.loc[mask, 'completed'] = new_val
        df.loc[mask, 'completed_at'] = str(get_current_time()) if new_val else None
        save_data(df)

def update_task_details(task_id, new_text, new_priority):
    """Update task details."""
    df = fetch_data()
    mask = df['id'] == str(task_id)
    if mask.any():
        df.loc[mask, 'text'] = new_text
        df.loc[mask, 'priority'] = new_priority
        save_data(df)

def delete_task(task_id):
    """Delete a task."""
    df = fetch_data()
    df = df[df['id'] != str(task_id)]
    save_data(df)

# --- Main Application Execution ---

# 1. Initialize logic
init_db()
run_auto_promote()

# 2. Get Data
all_tasks = fetch_data().to_dict('records')

# --- UI Layout ---
col_main, col_sidebar = st.columns([3, 1])

# --- Sidebar: History Panel ---
with st.sidebar:
    st.title("✅ History")
    st.markdown("---")
    
    completed_tasks = [t for t in all_tasks if t['completed']]
    # Sort by completed_at desc
    completed_tasks = sorted(completed_tasks, key=lambda x: x['completed_at'] if x['completed_at'] else '0', reverse=True)

    if not completed_tasks:
        st.info("No completed tasks yet.")
    
    for task in completed_tasks:
        time_str = "Recently"
        if task['completed_at'] and task['completed_at'] != 'None':
            try:
                # Parse the time string
                dt_obj = datetime.datetime.fromisoformat(task['completed_at'])
                # Adjust formatting
                if dt_obj.date() == get_current_time().date():
                    time_str = f"Today, {dt_obj.strftime('%I:%M %p')}"
                else:
                    time_str = dt_obj.strftime("%b %d, %I:%M %p")
            except ValueError:
                pass # Keep "Recently" if parsing fails

        # Container for History Item
        with st.container():
            st.markdown(f"""
            <div class="history-item">
                <div class="history-text">{task['text']}</div>
                <div class="history-time">Completed: {time_str}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Action buttons
            b1, b2 = st.columns(2)
            with b1:
                if st.button("↺", key=f"undo_{task['id']}", help="Reopen Task"):
                    toggle_complete(task['id'], True)
                    st.rerun()
            with b2:
                if st.button("🗑️", key=f"del_h_{task['id']}", help="Delete Forever"):
                    delete_task(task['id'])
                    st.rerun()
            st.markdown("---")

# --- Main Area ---
with col_main:
    st.title("Task Master Pro 🚀")
    st.caption(f"Timezone: {TIMEZONE} | Auto-priority active")
    
    # Input Form
    with st.container():
        with st.form("add_form", clear_on_submit=True):
            c1, c2, c3 = st.columns([4, 2, 1])
            with c1:
                txt = st.text_input("New Task", placeholder="What needs to be done?", label_visibility="collapsed")
            with c2:
                prio = st.selectbox("Priority", ["High", "Medium", "Low"], label_visibility="collapsed")
            with c3:
                submitted = st.form_submit_button("Add Task", type="primary")
            
            if submitted and txt:
                add_task(txt, prio)
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Filtering & Sorting
    priority_map = {"High": 3, "Medium": 2, "Low": 1}
    active_tasks = [t for t in all_tasks if not t['completed']]
    
    # Sort: 1. Priority (High to Low), 2. Created Date (Newest first)
    active_tasks = sorted(active_tasks, key=lambda x: x['created_at'], reverse=True)
    active_tasks = sorted(active_tasks, key=lambda x: priority_map.get(x['priority'], 1), reverse=True)

    if not active_tasks:
        st.success("🎉 All caught up!")

    # Task List
    for task in active_tasks:
        p_class = f"priority-{task['priority'].lower()}"
        
        with st.container():
            c_check, c_content, c_actions = st.columns([0.5, 5, 0.5])
            
            with c_check:
                st.write("") 
                # Note: We pass the ID as args
                st.checkbox("", key=f"check_{task['id']}", on_change=toggle_complete, args=(task['id'], False))
            
            with c_content:
                badges_html = f'<span class="badge {p_class}">{task["priority"]}</span>'
                if task['was_auto_promoted']:
                    badges_html += '<span class="badge carried-over">⚠️ Carried Over</span>'
                
                st.markdown(f"""
                <div style="margin-bottom: 4px;">
                    <span class="task-text">{task['text']}</span>
                </div>
                <div>{badges_html}</div>
                """, unsafe_allow_html=True)
            
            with c_actions:
                with st.popover("⋮"):
                    st.markdown("**Edit Task**")
                    e_txt = st.text_input("Text", task['text'], key=f"e_txt_{task['id']}")
                    e_prio = st.selectbox("Level", ["High", "Medium", "Low"], index=["High", "Medium", "Low"].index(task['priority']), key=f"e_prio_{task['id']}")
                    
                    if st.button("Save", key=f"save_{task['id']}"):
                        update_task_details(task['id'], e_txt, e_prio)
                        st.rerun()
                    
                    st.divider()
                    
                    if st.button("Delete", key=f"del_{task['id']}", type="primary"):
                        delete_task(task['id'])
                        st.rerun()
            
            st.markdown("---")
