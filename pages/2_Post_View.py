import streamlit as st
import streamlit.components.v1 as components
import requests
from utils import format_date, DARK_THEME_CSS

# API endpoint constants
API_BASE_URL = "https://m6njm571hh.execute-api.us-east-2.amazonaws.com"

st.set_page_config(page_title="Post View", page_icon="👜", layout="wide")
st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)

def format_comment_html(comment, level, is_highlighted=False):
    """Helper function to format comment HTML consistently"""
    level_label = {
        0: "Reply to Original Post (Level 1)",
        1: "Reply to Original Comment (Level 2)",
    }.get(level, f"Level {level + 1} Reply")
    
    if is_highlighted:
        level_label += " 🔍 (Comment From Search)"
    
    return f"""
    <div class="comment" data-level="{level}">
        <div class="comment-header">
            <strong>u/{comment['author']}</strong> - 
            <span class="level-label">{level_label}</span><br>
            <span class="metadata">Score: {comment['score']} | Posted on: {comment['formatted_date']}</span>
        </div>
        <div class="comment-body">{comment['body'].strip()}</div>
    </div>
    """

COMMENTS_CSS = """
    <style>
        .comments-container {
            color: white;
        }
        .comment {
            margin-left: calc(var(--level) * 20px);
            margin-bottom: 1em;
            padding: 10px;
            border-left: 2px solid #ccc;
        }
        .comment[data-level="0"] { 
            margin-left: 0; 
        }
        .comment-header {
            margin-bottom: 0.5em;
            font-size: 0.9em;
        }
        .level-label {
            color: #999;
            font-style: italic;
        }
        .metadata {
            color: #999;
            font-size: 0.9em;
        }
        .comment-body {
            margin: 0;
            padding: 10px;
            white-space: pre-wrap;
        }
    </style>
"""

# Get post and comment IDs from URL parameters
params = st.query_params
post_id = params.get("post_id")
highlight_comment_id = params.get("comment_id")

if not post_id:
    st.error("No post ID provided in the URL.")
    st.stop()

try:
    # Fetch post
    response = requests.get(f"{API_BASE_URL}/api/posts/{post_id}", timeout=10)
    post = response.json()
    
    # Display post
    st.title(post['title'])
    st.write(post['selftext'])
    st.markdown(
        f"Posted by u/{post['author']} | "
        f"Score: {post['score']} | "
        f"Comments: {post['num_comments']} | "
        f"Posted on: {post['formatted_date']}"
    )
    st.divider()
    
    # Fetch comments
    response = requests.get(
        f"{API_BASE_URL}/api/posts/{post_id}/comments",
        params={"sort": "most_upvotes"},
        timeout=10
    )
    comments_data = response.json()
    
    if comments_data and comments_data['results']:
        # If there's a highlighted comment, show its thread first
        if highlight_comment_id:
            comment_dict = {comment['id']: comment for comment in comments_data['results']}
            highlighted_chain = []
            current_comment = comment_dict.get(highlight_comment_id)
            
            while current_comment:
                highlighted_chain.insert(0, current_comment)
                if current_comment['parent_id'] == post_id:
                    break
                current_comment = comment_dict.get(current_comment['parent_id'])
            
            if highlighted_chain:
                st.header("Comment Thread Context")  # New header text
                comments_html = "".join(
                    format_comment_html(comment, i, comment['id'] == highlight_comment_id)
                    for i, comment in enumerate(highlighted_chain)
                )
                
                components.html(
                    COMMENTS_CSS + f'<div class="comments-container">{comments_html}</div>',
                    height=400,
                    scrolling=True
                )
                st.divider()
        
        # Display all comments
        st.header(f"All Comments ({comments_data['total_comments']})")
        display_nested_comments(comments_data['results'], highlight_comment_id)

except Exception as e:
    st.error(f"Error loading post: {str(e)}")
