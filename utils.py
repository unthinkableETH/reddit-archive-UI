from datetime import datetime

def format_date(utc_timestamp):
    """Convert UTC timestamp to readable date"""
    try:
        utc_timestamp = int(utc_timestamp)
        return datetime.utcfromtimestamp(utc_timestamp).strftime('%B %d, %Y %I:%M %p')
    except ValueError:
        return "Invalid Date"

# Dark theme styling
DARK_THEME_CSS = """
    <style>
        .stApp {
            background-color: #0E1117;
        }
        [data-testid="stSidebar"] {
            background-color: #262730;
        }
        [data-testid="stExpander"] {
            background-color: #262730;
        }
        .stMarkdown {
            color: #FAFAFA;
        }
        a {
            color: #4A9EFF !important;
        }
        a:hover {
            color: #7CB9FF !important;
            text-decoration: none;
        }
        hr {
            border-color: #333333;
        }
    </style>
""" 