import os
from IPython.core.display import display, HTML

    
def display_scrollable(df, height=300):
    display(HTML(f"""
    <div style="height:{height}px; overflow:auto; border:1px solid lightgray;">
        {df.to_html(escape=False, index=False)}
    </div>
    """))

def get_messages_db_path():
    """
    Get the path to the Messages database dynamically based on the user's home directory.

    Returns:
        str: Full path to the Messages database.
    """
    return os.path.expanduser("~/Library/Messages/chat.db")



def get_project_root():
    """Returns the absolute path of the project root directory."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

