import streamlit as st
import streamlit.components.v1 as components
import requests
from utils import format_date, DARK_THEME_CSS

# API endpoint constants
API_BASE_URL = "https://m6njm571hh.execute-api.us-east-2.amazonaws.com"

st.set_page_config(
    page_title="Post View",
    page_icon="👜",
    layout="wide"
)

st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)

def get_post(post_id: str):
    """Fetch post data from API"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/posts/{post_id}", timeout=10)
        if response.status_code == 404:
            st.error("Post not found")
            return None
        elif response.status_code != 200:
            st.error(f"Error fetching post (Status {response.status_code})")
            return None
            
        response.raise_for_status()
        return response.json()
    except requests.Timeout:
        st.error("Request timed out. Please try again.")
        return None
    except requests.RequestException as e:
        st.error(f"Error fetching post: {str(e)}")
        return None

def get_comments(post_id: str, sort: str = "most_upvotes"):
    """Fetch comments from API"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/posts/{post_id}/comments",
            params={"sort": sort, "include_removed": False},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching comments: {str(e)}")
        return None

def display_nested_comments(comments, highlight_comment_id=None):
    """Display comments in a nested tree structure"""
    
    # Create HTML for comments
    comments_html = ""
    comment_dict = {}
    top_level_comments = []
    
    # Build comment dictionary
    for comment in comments['results']:  # Note: comments are now in 'results' key
        comment_dict[comment['id']] = {
            'data': comment,
            'replies': [],
            'level': 0
        }
    
    # Build hierarchy
    for comment in comments['results']:
        parent_id = comment['parent_id']
        if parent_id == post_id:
            top_level_comments.append(comment['id'])
        else:
            if parent_id in comment_dict:
                comment_dict[parent_id]['replies'].append(comment['id'])
                comment_dict[comment['id']]['level'] = comment_dict[parent_id]['level'] + 1

    def build_comment_html(comment_id, level=0):
        if comment_id not in comment_dict:
            return ""
        
        comment = comment_dict[comment_id]['data']
        
        # Skip deleted comments
        if comment['body'] in ['[deleted]', '[removed]']:
            return ""
            
        replies = comment_dict[comment_id]['replies']
        # Filter out deleted replies
        valid_replies = [r for r in replies if comment_dict[r]['data']['body'] not in ['[deleted]', '[removed]']]
        
        # Updated level labels
        level_label = {
            0: "Reply to Original Post (Level 1)",
            1: "Reply to Original Comment (Level 2)",
        }.get(level, f"Level {level + 1} Reply")
        
        # Format links in comment body
        body = comment['body']
        # Convert markdown links to HTML
        import re
        body = re.sub(
            r'\[(.*?)\]\((.*?)\)',
            r'<a href="\2" target="_blank" class="comment-link">\1</a>',
            body
        )
        
        reply_count = len(valid_replies)
        reply_text = f"{reply_count} {'reply' if reply_count == 1 else 'replies'}" if reply_count > 0 else ""
        expand_button = f"""
            <button class="collapse-btn" onclick="toggleComment(this, '{comment['id']}')">
                [+] View {reply_text}
            </button>
        """ if reply_count > 0 else ""
        
        return f"""
            <div class="comment" data-level="{level}">
                <div class="comment-header">
                    <strong>u/{comment['author']}</strong> - 
                    <span class="level-label">{level_label}</span><br>
                    <span class="metadata">Score: {comment['score']} | Posted on: {format_date(comment['created_utc'])}</span>
                </div>
                <p class="comment-body">{body}</p>
                {expand_button}
                <div class="replies" id="replies-{comment['id']}" style="display: none;">
                    {''.join(build_comment_html(reply_id, level + 1) for reply_id in valid_replies)}
                </div>
            </div>
        """

    for comment_id in top_level_comments:
        comments_html += build_comment_html(comment_id)

    # Render using components.html
    components.html(
        f"""
        <style>
            .comment {{
                margin: 10px 0;
                border-left: 2px solid #666;
                padding-left: 8px;
            }}
            .comment[data-level="0"] {{ margin-left: 0; }}
            .comment[data-level="1"] {{ margin-left: 20px; }}
            .comment[data-level="2"] {{ margin-left: 40px; }}
            .comment[data-level="3"] {{ margin-left: 60px; }}
            .comment[data-level="4"] {{ margin-left: 80px; }}
            .comment-header {{
                margin: 8px 0;
                color: #FAFAFA;
            }}
            .collapse-btn {{
                background: transparent;
                border: 1px solid #666;
                color: #FAFAFA;
                padding: 2px 8px;
                margin: 8px 0;
                cursor: pointer;
                border-radius: 3px;
                display: block;
            }}
            .collapse-btn:hover {{
                background: #666;
            }}
            .level-label {{
                color: #888;
                font-size: 0.9em;
            }}
            .metadata {{
                color: #888;
                font-size: 0.9em;
            }}
            .comment-body {{
                color: #FAFAFA;
                margin: 8px 0;
                white-space: pre-wrap;
                text-indent: 0;
                padding: 0;
            }}
            .comment-link {{
                color: #58a6ff;
                text-decoration: none;
            }}
            
            .comment-link:hover {{
                text-decoration: underline;
            }}
        </style>
        <script>
            function toggleComment(btn, id) {{
                const replies = document.getElementById('replies-' + id);
                const isExpanded = replies.style.display === 'block';
                
                replies.style.display = isExpanded ? 'none' : 'block';
                
                // Extract the number of replies from the button text
                const match = btn.textContent.match(/\\d+/);
                if (match) {{
                    const count = match[0];
                    const replyWord = count === '1' ? 'reply' : 'replies';
                    if (isExpanded) {{
                        btn.textContent = '[+] View ' + count + ' ' + replyWord;
                    }} else {{
                        btn.textContent = '[-] Hide ' + count + ' ' + replyWord;
                    }}
                }}
            }}
        </script>
        <div class="comments-container">
            {comments_html}
        </div>
        """,
        height=800,
        scrolling=True
    )

# Get post and comment IDs from URL parameters
params = st.query_params
post_id = params.get("post_id")
highlight_comment_id = params.get("comment_id")

if not post_id:
    st.title("Post View")
    st.error("No post ID provided in the URL.")
    st.markdown("""
    ### How to Access Post View
    This page shows detailed views of posts and their comments. To view a post:

    1. Use the [Search page](/Search_View) to find posts
    2. Click on any post title or "View Discussion" button
    """)
    st.stop()

# Sidebar controls
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
    
    bring_to_top = st.toggle("Bring highlighted comment to top", value=True)
    highlight_comment = st.toggle("Highlight search result comment", value=True)

try:
    # Fetch post
    post = get_post(post_id)
    
    if not post:
        st.error("Post not found")
        st.stop()
    
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
    comments_data = get_comments(post_id, comment_sort)
    
    if comments_data and comments_data['results']:
        # Create a lookup dictionary for quick access
        comment_dict = {comment['id']: comment for comment in comments_data['results']}
        
        # If there's a highlighted comment and bring_to_top is enabled
        if highlight_comment_id and highlight_comment and bring_to_top:
            highlighted_chain = []
            seen_comments = set()
            
            # Get the comment chain
            current_comment = comment_dict.get(highlight_comment_id)
            while current_comment:
                if current_comment['id'] not in seen_comments:
                    highlighted_chain.insert(0, current_comment)
                    seen_comments.add(current_comment['id'])
                
                parent_id = current_comment['parent_id']
                if parent_id == post_id:  # Parent is the post
                    break
                    
                current_comment = comment_dict.get(parent_id)
            
            # Display highlighted chain
            if highlighted_chain:
                st.header("Highlighted Comment Thread")
                for i, comment in enumerate(highlighted_chain):
                    is_highlighted = comment['id'] == highlight_comment_id
                    style = "background-color: rgba(255, 0, 0, 0.1);" if is_highlighted else ""
                    
                    # Display comment with metadata
                    st.markdown(
                        f"""<div style='padding: 8px; border-left: 2px solid #ccc;'>
                            <strong>u/{comment['author']}</strong> | 
                            Score: {comment['score']} | 
                            Posted on: {comment['formatted_date']}
                            <div style="{style}">{comment['body']}</div>
                        </div>""",
                        unsafe_allow_html=True
                    )
                    st.divider()
        
        # Display all comments in nested structure
        st.header(f"All Comments ({comments_data['total_comments']})")
        display_nested_comments(comments_data, highlight_comment_id if highlight_comment else None)
    else:
        st.info("No comments found for this post")

except Exception as e:
    st.error(f"Error loading post: {str(e)}")
