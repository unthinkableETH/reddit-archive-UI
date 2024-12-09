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

def display_nested_comments(comments, highlight_comment_id=None):
    """Display comments in a nested structure with expanders"""
    comment_dict = {}
    top_level_comments = []
    
    # Build comment dictionary and identify top-level comments
    for comment in comments:
        comment_dict[comment['id']] = {
            'data': comment,
            'replies': []
        }
        if comment['parent_id'] == post_id:
            top_level_comments.append(comment['id'])
        elif comment['parent_id'] in comment_dict:
            comment_dict[comment['parent_id']]['replies'].append(comment['id'])
    
    # Build HTML for nested comments
    def build_comment_html(comment_id, level=0):
        if comment_id not in comment_dict:
            return ""
        
        comment = comment_dict[comment_id]['data']
        is_highlighted = comment['id'] == highlight_comment_id
        replies = comment_dict[comment_id]['replies']
        
        # Generate level label
        level_label = {
            0: "Reply to Original Post (Level 1)",
            1: "Reply to Original Comment (Level 2)",
        }.get(level, f"Level {level + 1} Reply")
        
        if is_highlighted:
            level_label += " 🔍 (Comment From Search)"
        
        # Add expand/collapse button if there are replies
        expand_button = ""
        replies_html = ""
        if replies:
            expand_button = f"""
                <div class="expand-wrapper">
                    <button onclick="toggleReplies('{comment['id']}')" class="expand-button" id="button-{comment['id']}">
                        [+] Show {len(replies)} repl{'y' if len(replies) == 1 else 'ies'}
                    </button>
                </div>
            """
            replies_html = f"""
                <div class="replies" id="replies-{comment['id']}" style="display: none;">
                    {''.join(build_comment_html(reply_id, level + 1) for reply_id in replies)}
                </div>
            """
        
        return f"""
            <div class="comment" data-level="{level}">
                <div class="comment-header">
                    <strong>u/{comment['author']}</strong> - 
                    <span class="level-label">{level_label}</span><br>
                    <span class="metadata">Score: {comment['score']} | Posted on: {comment['formatted_date']}</span>
                </div>
                <div class="comment-body">{comment['body'].strip()}</div>
                {expand_button}
                {replies_html}
            </div>
        """
    
    # Add JavaScript for expand/collapse functionality
    js_code = """
        <script>
        function toggleReplies(commentId) {
            const replies = document.getElementById('replies-' + commentId);
            const button = document.getElementById('button-' + commentId);
            if (replies.style.display === 'none') {
                replies.style.display = 'block';
                button.textContent = button.textContent.replace('[+]', '[-]').replace('Show', 'Hide');
            } else {
                replies.style.display = 'none';
                button.textContent = button.textContent.replace('[-]', '[+]').replace('Hide', 'Show');
            }
        }
        </script>
    """
    
    # Update CSS to be included in COMMENTS_CSS
    updated_css = COMMENTS_CSS.replace(
        "</style>",
        """
        .comment {
            margin-left: calc(var(--level) * 50px);
            margin-bottom: 1em;
            padding: 12px;
            border-left: 2px solid #666;
            transition: background-color 0.2s ease;
        }
        .comment:hover {
            background-color: rgba(255, 255, 255, 0.03);
        }
        .nested-comment {
            background-color: rgba(255, 255, 255, 0.02);
        }
        .comment-header {
            margin-bottom: 0.8em;
            font-size: 0.9em;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            padding-bottom: 5px;
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
            padding: 10px 5px;
            white-space: pre-wrap;
            line-height: 1.4;
        }
        button.expand-button {
            background: none;
            border: none;
            color: #666;
            cursor: pointer;
            font-size: 0.85em;
            padding: 2px 0;
            opacity: 0.8;
            margin-top: 5px;
        }
        button.expand-button:hover {
            opacity: 1;
            color: #999;
        }
        .replies {
            margin-top: 12px;
            padding-top: 5px;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
        }
        </style>
    """
    )
    
    comments_html = "".join(build_comment_html(comment_id) for comment_id in top_level_comments)
    
    components.html(
        updated_css + js_code + 
        f'<div class="comments-container">{comments_html}</div>',
        height=800,
        scrolling=True
    )

COMMENTS_CSS = """
    <style>
        .comments-container {
            color: white;
        }
        .comment {
            margin-left: calc(var(--level) * 50px);
            margin-bottom: 1em;
            padding: 12px;
            border-left: 2px solid #666;
            transition: background-color 0.2s ease;
        }
        .comment:hover {
            background-color: rgba(255, 255, 255, 0.03);
        }
        .nested-comment {
            background-color: rgba(255, 255, 255, 0.02);
        }
        .comment-header {
            margin-bottom: 0.8em;
            font-size: 0.9em;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            padding-bottom: 5px;
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
            padding: 10px 5px;
            white-space: pre-wrap;
            line-height: 1.4;
        }
        button.expand-button {
            background: none;
            border: none;
            color: #666;
            cursor: pointer;
            font-size: 0.85em;
            padding: 2px 0;
            opacity: 0.8;
            margin-top: 5px;
        }
        button.expand-button:hover {
            opacity: 1;
            color: #999;
        }
        .replies {
            margin-top: 12px;
            padding-top: 5px;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
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

# Add sort dropdown in sidebar
with st.sidebar:
    st.header("Comment Controls")
    comment_sort = st.selectbox(
        "Sort comments by",
        ["most_upvotes", "newest", "oldest"],
        format_func=lambda x: {
            "most_upvotes": "Most Upvotes",
            "newest": "Newest",
            "oldest": "Oldest"
        }[x]
    )

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
    
    # Fetch comments with sort
    response = requests.get(
        f"{API_BASE_URL}/api/posts/{post_id}/comments",
        params={
            "sort": comment_sort,
            "limit": 10000  # High limit to ensure we get all comments
        },
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
                st.header("Comment Thread Context")
                
                for i, comment in enumerate(highlighted_chain):
                    is_highlighted = comment['id'] == highlight_comment_id
                    level_label = {
                        0: "Reply to Original Post (Level 1)",
                        1: "Reply to Original Comment (Level 2)",
                    }.get(i, f"Level {i + 1} Reply")
                    
                    if is_highlighted:
                        level_label += " 🔍 (Comment From Search)"
                        
                    # Create a container with custom padding
                    container = st.container()
                    container.markdown(
                        f"""
                        <div style="margin-left: {i * 40}px; padding: 10px; border-left: 2px solid #666; background-color: {'rgba(255,255,255,0.02)' if i > 0 else 'transparent'}">
                            <p><strong>u/{comment['author']}</strong> - <em>{level_label}</em><br>
                            Score: {comment['score']} | Posted on: {comment['formatted_date']}</p>
                            <p>{comment['body']}</p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                
                st.divider()
        
        # Display all comments
        st.header(f"All Comments ({comments_data['total_comments']})")
        display_nested_comments(comments_data['results'], highlight_comment_id)

except Exception as e:
    st.error(f"Error loading post: {str(e)}")
