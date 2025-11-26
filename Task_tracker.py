import streamlit as st
import pandas as pd
import datetime
from datetime import date
from streamlit_gsheets import GSheetsConnection

# --- Configuration ---
st.set_page_config(page_title="Task Master Pro", page_icon="✅", layout="wide")

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

# --- Google Sheets Connection ---
@st.cache_resource
def get_gsheets_conn():
    return st.connection("gsheets", type=GSheetsConnection)

def init_db():
    """Initialize the Google Sheets worksheet with proper columns if empty."""
    conn = get_gsheets_conn()
    try:
        df = conn.read(worksheet='Tasks', usecols=list(range(7)))
        # Ensure all required columns exist
        required_cols = ['id', 'text', 'priority', 'completed', 'created_at', 'completed_at', 'was_auto_promoted']
        if df.empty or not all(col in df.columns for col in required_cols):
            # Create empty dataframe with proper structure
            df = pd.DataFrame(columns=required_cols)
            conn.update(worksheet='Tasks', data=df)
    except Exception:
        # If worksheet doesn't exist or is empty, create it
        df = pd.DataFrame(columns=['id', 'text', 'priority', 'completed', 'created_at', 'completed_at', 'was_auto_promoted'])
        conn.update(worksheet='Tasks', data=df)

def run_auto_promote():
    """Auto-promote old tasks to High priority using pandas filtering."""
    conn = get_gsheets_conn()
    df = conn.read(worksheet='Tasks', usecols=list(range(7)))
    
    if df.empty:
        return
    
    # Ensure proper data types
    if 'completed' in df.columns:
        df['completed'] = df['completed'].apply(lambda x: bool(x) if isinstance(x, (bool, int)) else str(x).lower() in ['true', '1', 'yes'])
    else:
        df['completed'] = False
    if 'was_auto_promoted' in df.columns:
        df['was_auto_promoted'] = df['was_auto_promoted'].apply(lambda x: bool(x) if isinstance(x, (bool, int)) else str(x).lower() in ['true', '1', 'yes'])
    else:
        df['was_auto_promoted'] = False
    if 'id' in df.columns:
        df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
    else:
        df['id'] = range(len(df))
    
    # Ensure created_at is string and handle NaN
    if 'created_at' in df.columns:
        df['created_at'] = df['created_at'].astype(str).replace('nan', '')
    else:
        df['created_at'] = ''
    
    today_str = str(date.today())
    updates = 0
    
    # Filter incomplete tasks from previous days that aren't High yet
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
    
    # Mark existing High priority tasks from yesterday as carried over
    mask_carried = (
        (df['completed'] == False) & 
        (df['priority'] == 'High') & 
        (df['was_auto_promoted'] == False) & 
        (df['created_at'].str[:10] < today_str) &
        (df['created_at'].str[:10] != '')
    )
    
    if mask_carried.any():
        df.loc[mask_carried, 'was_auto_promoted'] = True
    
    # Save back to Google Sheets
    if updates > 0 or mask_carried.any():
        conn.update(worksheet='Tasks', data=df)
    
    if updates > 0:
        st.toast(f"🚀 Auto-promoted {updates} old tasks to High Priority!")

def add_task(text, priority):
    """Add a new task to Google Sheets."""
    conn = get_gsheets_conn()
    df = conn.read(worksheet='Tasks', usecols=list(range(7)))
    
    # Get next ID
    if df.empty or 'id' not in df.columns or df['id'].isna().all():
        next_id = 1
    else:
        df['id'] = pd.to_numeric(df['id'], errors='coerce')
        next_id = int(df['id'].max() + 1) if not df['id'].isna().all() else 1
    
    # Create new row
    new_row = pd.DataFrame([{
        'id': next_id,
        'text': text,
        'priority': priority,
        'completed': False,
        'created_at': str(datetime.datetime.now()),
        'completed_at': None,
        'was_auto_promoted': False
    }])
    
    # Append to dataframe
    df = pd.concat([df, new_row], ignore_index=True)
    
    # Save back to Google Sheets
    conn.update(worksheet='Tasks', data=df)

def get_tasks():
    """Get all tasks from Google Sheets as a list of dictionaries."""
    conn = get_gsheets_conn()
    df = conn.read(worksheet='Tasks', usecols=list(range(7)))
    
    if df.empty:
        return []
    
    # Ensure proper data types
    if 'id' in df.columns:
        df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
    if 'completed' in df.columns:
        # Handle various boolean formats from Google Sheets
        df['completed'] = df['completed'].apply(lambda x: bool(x) if isinstance(x, (bool, int)) else str(x).lower() in ['true', '1', 'yes'])
    if 'was_auto_promoted' in df.columns:
        df['was_auto_promoted'] = df['was_auto_promoted'].apply(lambda x: bool(x) if isinstance(x, (bool, int)) else str(x).lower() in ['true', '1', 'yes'])
    
    # Replace NaN with None for JSON compatibility
    df = df.where(pd.notna(df), None)
    
    return df.to_dict('records')

def toggle_complete(task_id, current_val):
    """Toggle task completion status."""
    conn = get_gsheets_conn()
    df = conn.read(worksheet='Tasks', usecols=list(range(7)))
    
    if df.empty:
        return
    
    # Ensure proper data types
    df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)
    if 'completed' in df.columns:
        df['completed'] = df['completed'].apply(lambda x: bool(x) if isinstance(x, (bool, int)) else str(x).lower() in ['true', '1', 'yes'])
    else:
        df['completed'] = False
    
    # Find and update the task
    mask = df['id'] == task_id
    if mask.any():
        new_val = not current_val
        df.loc[mask, 'completed'] = new_val
        df.loc[mask, 'completed_at'] = str(datetime.datetime.now()) if new_val else None
        
        # Save back to Google Sheets
        conn.update(worksheet='Tasks', data=df)

def update_task_details(task_id, new_text, new_priority):
    """Update task text and priority."""
    conn = get_gsheets_conn()
    df = conn.read(worksheet='Tasks', usecols=list(range(7)))
    
    if df.empty:
        return
    
    # Ensure proper data types
    df['id'] = pd.to_numeric(df['id'], errors='coerce').astype(int)
    
    # Find and update the task
    mask = df['id'] == task_id
    if mask.any():
        df.loc[mask, 'text'] = new_text
        df.loc[mask, 'priority'] = new_priority
        
        # Save back to Google Sheets
        conn.update(worksheet='Tasks', data=df)

def delete_task(task_id):
    """Delete a task from Google Sheets."""
    conn = get_gsheets_conn()
    df = conn.read(worksheet='Tasks', usecols=list(range(7)))
    
    if df.empty:
        return
    
    # Ensure proper data types
    df['id'] = pd.to_numeric(df['id'], errors='coerce').astype(int)
    
    # Remove the task
    df = df[df['id'] != task_id]
    
    # Save back to Google Sheets
    conn.update(worksheet='Tasks', data=df)

# --- Main Logic ---
init_db()
run_auto_promote()

# Get all tasks once for use in both sidebar and main area
all_tasks = get_tasks()

# --- UI Layout ---
col_main, col_sidebar = st.columns([3, 1])

# --- Sidebar: History Panel ---
with st.sidebar:
    st.title("✅ History")
    st.markdown("---")
    
    completed_tasks = [t for t in all_tasks if t['completed']]
    completed_tasks = sorted(completed_tasks, key=lambda x: x['completed_at'] if x['completed_at'] else x['created_at'], reverse=True)

    if not completed_tasks:
        st.info("No completed tasks yet. Get to work! 💪")
    
    for task in completed_tasks:
        # Calculate nice time display
        if task['completed_at']:
            dt_obj = datetime.datetime.strptime(task['completed_at'], "%Y-%m-%d %H:%M:%S.%f")
            
            # Show "Today" or specific date
            if dt_obj.date() == date.today():
                time_str = f"Today, {dt_obj.strftime('%I:%M %p')}"
            else:
                time_str = dt_obj.strftime("%b %d, %I:%M %p")
        else:
            time_str = "Recently"

        # Container for History Item
        with st.container():
            st.markdown(f"""
            <div class="history-item">
                <div class="history-text">{task['text']}</div>
                <div class="history-time">Completed: {time_str}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Action buttons in columns
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("↺ Reopen", key=f"undo_{task['id']}", help="Mark as incomplete", use_container_width=True):
                    toggle_complete(task['id'], True)
                    st.rerun()
            with btn_col2:
                if st.button("🗑️ Delete", key=f"delete_{task['id']}", help="Permanently delete task", type="primary", use_container_width=True):
                    delete_task(task['id'])
                    st.rerun()
            st.markdown("---")


# --- Main Area ---
with col_main:
    st.title("Task Master Pro 🚀")
    st.caption("Focus on what matters. Your daily tasks are auto-prioritized.")
    
    # Input Section
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

    # Sorting Logic
    priority_map = {"High": 3, "Medium": 2, "Low": 1}
    active_tasks = [t for t in all_tasks if not t['completed']]
    
    # Sort: High Priority -> Newest
    active_tasks = sorted(active_tasks, key=lambda x: x['created_at'], reverse=True)
    active_tasks = sorted(active_tasks, key=lambda x: priority_map.get(x['priority'], 1), reverse=True)

    if not active_tasks:
        st.success("🎉 You're all caught up! No active tasks.")

    # Task List Display
    for task in active_tasks:
        # Determine classes
        p_class = f"priority-{task['priority'].lower()}"
        
        # We use a container with a custom class for the 'card' look
        with st.container():
            # Apply styling wrapper via Markdown
            # Note: Streamlit containers don't natively take classes easily, so we mimic structure
            # But the best way is to use columns inside a styled div if possible, 
            # or just style the elements and use st.container for grouping.
            
            c_check, c_content, c_actions = st.columns([0.5, 5, 0.5])
            
            with c_check:
                # Vertical align checkbox
                st.write("") 
                st.checkbox("", key=f"check_{task['id']}", on_change=toggle_complete, args=(task['id'], False))
            
            with c_content:
                # Custom HTML for title and badges
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
                    
                    if st.button("Save Changes", key=f"save_{task['id']}"):
                        update_task_details(task['id'], e_txt, e_prio)
                        st.rerun()
                    
                    st.divider()
                    
                    if st.button("Delete Task", key=f"del_{task['id']}", type="primary"):
                        delete_task(task['id'])
                        st.rerun()
            
            st.markdown("---") # Thin separator instead of full card border to keep it clean in Streamlit