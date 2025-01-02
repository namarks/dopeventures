import os
from IPython.core.display import display, HTML
import requests
from itertools import islice

    
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


def resolve_short_url(short_url):
        response = requests.head(short_url, allow_redirects=True)
        return response.url


def extract_values_from_pd_list_column(df, column_name):
    """
    Extract all items from a DataFarme column containing list vlaues

    Args:
        df (pd.DataFrame): DataFrame 
        column_name (str): Name of the column containing list of values

    Returns:
        pd.Series: Series containing unnested values
    """
    
    return df.explode(column_name)[column_name].dropna().unique()


def generate_distinct_values_from_list_column(df, column_name):
    unique_spotify_links = (
        df[column_name]
        .dropna()  # Remove NaN values
        .explode()  # Unnest lists into rows
        .unique()  # Get unique values
        .tolist()  # Convert to list
        )
    
    return unique_spotify_links


def batch(iterable, n=50):
    """Helper function to split an iterable into batches of size n."""
    it = iter(iterable)
    return iter(lambda: list(islice(it, n)), [])
