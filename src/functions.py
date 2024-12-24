import re
from IPython.core.display import display, HTML
import typedstream

def get_chat_size(handles_list):
    '''
    Given the list of handles in a chat thread, returns the size of the list, i.e., the number of unique handles in the chat. 
    '''
    if handles_list is None:
        return 0
    else:
        return len(handles_list)
    
def extract_text_from_typedstream(data):
    """
    Extract readable text from binary attributedBody data using typedstream.

    Parameters:
        data (bytes): Binary attributedBody field data.

    Returns:
        str: Extracted readable text, or an empty string if parsing fails.
    """
    try:
        # Deserialize the binary data
        deserialized_object = typedstream.unarchive_from_data(data)

        # Extract the text content
        if hasattr(deserialized_object, 'contents') and deserialized_object.contents:
            return deserialized_object.contents[0].value.value
        else:
            return ''
    except Exception as e:
        print(f"Error extracting text: {e}")
        return ''



def parse_binary_message(data):
    """
    Parse a binary attributedBody message and extract text and metadata.

    Parameters:
        data (bytes): Serialized binary data.

    Returns:
        dict: Extracted text and metadata.
    """
    try:
        parsed = typedstream.unarchive_from_data(data)
        result = {"text": None, "metadata": {}}

        # Extract text
        if hasattr(parsed, 'contents') and len(parsed.contents) > 0:
            result["text"] = parsed.contents[0].value.value if hasattr(parsed.contents[0].value, 'value') else str(parsed.contents[0])

        # Extract metadata
        for content in parsed.contents:
            if isinstance(content.value, dict):  # Check for NSDictionary
                result["metadata"] = {key: value for key, value in content.value.items()}

        return result
    except Exception as e:
        print(f"Error parsing binary message: {e}")
        return {"text": None, "metadata": {}}



def display_scrollable(df, height=300):
    display(HTML(f"""
    <div style="height:{height}px; overflow:auto; border:1px solid lightgray;">
        {df.to_html(escape=False, index=False)}
    </div>
    """))


def extract_urls(text):
    """
    Extracts all URLs from a given text string.
    
    Parameters:
        text (str): The input text containing URLs.

    Returns:
        list: A list of extracted URLs.
    """
    if not isinstance(text, str):  # Ensure input is a string
        return []
    
    # Regular expression to match URLs
    url_pattern = r'https?://[^\s,<>"]+|www\.[^\s,<>"]+'
    
    # Find all matching URLs
    urls = re.findall(url_pattern, text)
    return urls
