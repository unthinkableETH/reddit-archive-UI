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
    print(f"Total comments to process: {len(comments)}")
    
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
            print(f"Found top level comment: {comment['id']} with author: {comment['author']}")
        elif comment['parent_id'] in comment_dict:
            comment_dict[comment['parent_id']]['replies'].append(comment['id'])
            print(f"Found nested reply: {comment['id']} under parent: {comment['parent_id']}")
    
    print(f"Number of top-level comments: {len(top_level_comments)}")
    print(f"Total number of reply relationships: {sum(len(c['replies']) for c in comment_dict.values())}")
    
    # Build HTML for nested comments
    def build_comment_html(comment_id, level=0):
        if comment_id not in comment_dict:
            print(f"Warning: Comment {comment_id} not found in dictionary")
            return ""
        
        comment = comment_dict[comment_id]['data']
        replies = comment_dict[comment_id]['replies']
        
        if replies:
            print(f"Building HTML for comment {comment_id} with {len(replies)} replies at level {level}")
        
        is_highlighted = comment['id'] == highlight_comment_id
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
                <button onclick="toggleReplies('{comment['id']}')" class="expand-button" id="button-{comment['id']}">
                    [+] {len(replies)} {'reply' if len(replies) == 1 else 'replies'}
                </button>
            """
            replies_html = f"""
                <div class="replies" id="replies-{comment['id']}" style="display: none;">
                    {''.join(build_comment_html(reply_id, level + 1) for reply_id in replies)}
                </div>
            """
        
        return f"""
            <div class="comment {' nested-comment' if level > 0 else ''}" data-level="{level}">
                <div class="comment-header">
                    <div class="author-line">
                        <span class="author">u/{comment['author']}</span>
                        <span class="level-label">- {level_label}</span>
                    </div>
                    <div class="metadata">Score: {comment['score']} | Posted on: {comment['formatted_date']}</div>
                </div>
                <div class="comment-body">{comment['body'].strip()}</div>
                {expand_button if replies else ''}
                <div class="replies" id="replies-{comment['id']}" style="display: none;">
                    {''.join(build_comment_html(reply_id, level + 1) for reply_id in replies)}
                </div>
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
        .comments-container {
            color: white;
            max-width: 1200px;
            margin: 0 auto;
        }
        .comment {
            margin-left: calc(var(--level) * 55px);
            margin-bottom: 1.4em;
            padding: 18px 22px;
            border-left: 3px solid #555;
            position: relative;
            line-height: 1.6;
        }
        .comment[data-level="0"] { 
            margin-left: 0; 
            margin-bottom: 2em;
            border-left: 3px solid #666;
        }
        .nested-comment {
            background-color: rgba(255, 255, 255, 0.015);
            margin-left: 52px;
        }
        .comment[data-level="2"] {
            background-color: rgba(255, 255, 255, 0.022);
        }
        .comment[data-level="3"] {
            background-color: rgba(255, 255, 255, 0.029);
        }
        .comment-header {
            margin-bottom: 1em;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }
        .author-line {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 4px;
        }
        .author {
            color: #fff;
            font-weight: 500;
            font-size: 0.95em;
        }
        .level-label {
            color: #888;
            font-style: italic;
            font-size: 0.9em;
        }
        .metadata {
            color: #777;
            font-size: 0.85em;
        }
        .comment-body {
            margin: 0;
            padding: 5px 0 10px 0;
            white-space: pre-wrap;
            font-size: 0.95em;
            color: rgba(255, 255, 255, 0.9);
            letter-spacing: 0.2px;
            word-spacing: 0.5px;
        }
        button.expand-button {
            background: none;
            border: none;
            color: #888;
            cursor: pointer;
            font-size: 0.85em;
            padding: 6px 0;
            margin-top: 8px;
            font-family: monospace;
            letter-spacing: 0.5px;
            opacity: 0.9;
            margin-left: -3px;
        }
        .replies {
            margin-top: 14px;
            position: relative;
            border-left: 3px solid #555;
            margin-left: -3px;
            padding-left: 3px;
        }
        .replies::before {
            display: none;
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
            max-width: 1200px;
            margin: 0 auto;
        }
        .comment {
            margin-left: calc(var(--level) * 55px);
            margin-bottom: 1.4em;
            padding: 18px 22px;
            border-left: 3px solid #555;
            position: relative;
            line-height: 1.6;
        }
        .comment[data-level="0"] { 
            margin-left: 0; 
            margin-bottom: 2em;
            border-left: 3px solid #666;
        }
        .nested-comment {
            background-color: rgba(255, 255, 255, 0.015);
            margin-left: 52px;
        }
        .comment[data-level="2"] {
            background-color: rgba(255, 255, 255, 0.022);
        }
        .comment[data-level="3"] {
            background-color: rgba(255, 255, 255, 0.029);
        }
        .comment-header {
            margin-bottom: 1em;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }
        .author-line {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 4px;
        }
        .author {
            color: #fff;
            font-weight: 500;
            font-size: 0.95em;
        }
        .level-label {
            color: #888;
            font-style: italic;
            font-size: 0.9em;
        }
        .metadata {
            color: #777;
            font-size: 0.85em;
        }
        .comment-body {
            margin: 0;
            padding: 5px 0 10px 0;
            white-space: pre-wrap;
            font-size: 0.95em;
            color: rgba(255, 255, 255, 0.9);
            letter-spacing: 0.2px;
            word-spacing: 0.5px;
        }
        button.expand-button {
            background: none;
            border: none;
            color: #888;
            cursor: pointer;
            font-size: 0.85em;
            padding: 6px 0;
            margin-top: 8px;
            font-family: monospace;
            letter-spacing: 0.5px;
            opacity: 0.9;
            margin-left: -3px;
        }
        .replies {
            margin-top: 14px;
            position: relative;
            border-left: 3px solid #555;
            margin-left: -3px;
            padding-left: 3px;
        }
        .replies::before {
            display: none;
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
    
    # Sort dropdown
    comment_sort = st.selectbox(
        "Sort comments by",
        ["most_upvotes", "newest", "oldest"],
        format_func=lambda x: {
            "most_upvotes": "Most Upvotes",
            "newest": "Newest",
            "oldest": "Oldest"
        }[x]
    )
    
    # Add expand/collapse all buttons
    st.divider()
    st.subheader("Comment Display")
    col1, col2 = st.columns(2)
    
    # Add this JavaScript to the page once
    st.components.v1.html(
        """
        <script>
        function expandAll() {
            console.log('Starting expandAll function');
            var container = document.querySelector('.comments-container');
            console.log('Container found:', container !== null);
            
            if (container) {
                var allReplies = container.getElementsByClassName('replies');
                console.log('Number of replies found:', allReplies.length);
                
                var allButtons = container.getElementsByClassName('expand-button');
                console.log('Number of buttons found:', allButtons.length);
                
                for (var i = 0; i < allReplies.length; i++) {
                    var reply = allReplies[i];
                    var commentId = reply.id.replace('replies-', '');
                    console.log('Processing reply:', commentId);
                    
                    reply.style.display = 'block';
                    
                    var button = document.getElementById('button-' + commentId);
                    if (button) {
                        var numReplies = button.textContent.match(/\d+/)[0];
                        button.textContent = `[-] Hide ${numReplies} ${numReplies === '1' ? 'reply' : 'replies'}`;
                        console.log('Updated button:', commentId);
                    }
                }
            }
        }

        function collapseAll() {
            var container = document.querySelector('.comments-container');
            if (container) {
                var allReplies = container.getElementsByClassName('replies');
                for (var i = 0; i < allReplies.length; i++) {
                    allReplies[i].style.display = 'none';
                }
                
                var allButtons = container.getElementsByClassName('expand-button');
                for (var i = 0; i < allButtons.length; i++) {
                    var button = allButtons[i];
                    var numReplies = button.textContent.match(/\d+/)[0];
                    button.textContent = `[+] Show ${numReplies} ${numReplies === '1' ? 'reply' : 'replies'}`;
                }
            }
        }
        </script>
        """,
        height=0
    )
    
    with col1:
        if st.button("Expand All"):
            st.components.v1.html(
                """
                <script>
                    expandAll();
                </script>
                """,
                height=0
            )
    
    with col2:
        if st.button("Collapse All"):
            st.components.v1.html(
                """
                <script>
                    collapseAll();
                </script>
                """,
                height=0
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
                        
                    container = st.container()
                    container.markdown(
                        f"""
                        <div style="margin-left: {i * 40}px; padding: 10px; border-left: 2px solid #666;">
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
    
    
