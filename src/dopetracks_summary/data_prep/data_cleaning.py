"""
data_cleaning.py

This module performs data cleaning and preprocessing for iMessage data.

Key Functions:
- rename_columns: Standardizes column names for easier readability.
- convert_timestamps: Converts raw timestamps to datetime format.
- fill_null_values: Replaces null values in DataFrames with default values.

Usage:
This module is called by pull_data.py to clean extracted data. Functions can also be used
independently for cleaning specific datasets.
"""


import pandas as pd


def rename_columns(messages, handles):
    """
    Renames columns for better readability.

    Args:
        messages_raw (DataFrame): Raw messages DataFrame.
        handles (DataFrame): Handles DataFrame.

    Returns:
        Tuple[DataFrame, DataFrame]: Updated messages and handles DataFrames.
    """
    messages.rename(columns={'ROWID': 'message_id'}, inplace=True)
    handles.rename(columns={'ROWID': 'handle_id', 'id': 'contact_info'}, inplace=True)
    return messages, handles


def convert_timestamps(messages):
    """
    Converts date and timestamp strings to datetime objects for better handling.

    Args:
        messages (DataFrame): Messages DataFrame.

    Returns:
        DataFrame: Updated messages DataFrame with converted timestamps.
    """
    messages['timestamp'] = messages['date_utc'].apply(lambda x: pd.Timestamp(x))
    messages['date'] = messages['timestamp'].apply(lambda x: x.date())
    messages['date'] = pd.to_datetime(messages['date'], errors='coerce')
    
    return messages

def fill_null_values(df, fill_value=""):
    """
    Fill null values in a DataFrame.
    """
    return df.fillna(fill_value)