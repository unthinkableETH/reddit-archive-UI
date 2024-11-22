import streamlit as st
from database import execute_query
from queries import GET_POST_BY_ID, GET_COMMENTS_FOR_POST, SORT_ORDERS
from utils import format_date, DARK_THEME_CSS

st.set_page_config(
    page_title="Post View",
    page_icon="👜",
    layout="wide"
)

st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)

# Get post and comment IDs from URL parameters
params = st.query_params
post_id = params.get("post_id")
highlight_comment_id = params.get("comment_id")

if not post_id:
    st.error("No post ID provided in the URL.")
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

def display_nested_comments(comments, highlight_comment_id=None):
    """Display comments in a nested tree structure"""
    comment_dict = {}
    top_level_comments = []
    
    # First pass: create dictionary of all comments
    for comment in comments:
        comment_dict[comment['id']] = {
            'data': comment,
            'replies': [],
            'level': 0
        }
    
    # Second pass: build the hierarchy
    for comment in comments:
        parent_id = comment['parent_id']
        if parent_id.startswith('t3_'):  # Top-level comment
            top_level_comments.append(comment['id'])
        elif parent_id.startswith('t1_'):  # Reply to another comment
            parent_id = parent_id[3:]  # Remove 't1_' prefix
            if parent_id in comment_dict:
                comment_dict[parent_id]['replies'].append(comment['id'])
                comment_dict[comment['id']]['level'] = comment_dict[parent_id]['level'] + 1
    
    # Function to recursively display comments
    def display_comment_tree(comment_id, level=0):
        if comment_id not in comment_dict:
            return
            
        comment = comment_dict[comment_id]['data']
        replies = comment_dict[comment_id]['replies']
        
        # Calculate indentation
        left_margin = min(level * 20, 200)  # Max indent of 200px
        
        # Check if this is the highlighted comment
        is_highlighted = comment['id'] == highlight_comment_id
        highlight_style = "color: red;" if is_highlighted else ""
        
        st.markdown(
            f"""
            <div style='margin-left: {left_margin}px; padding: 8px; border-left: 2px solid #ccc;'>
                <strong>u/{comment['author']}</strong> - 
                <i>Score: {comment['score']} | Posted on: {format_date(comment['created_utc'])}</i>
                <p style="{highlight_style}">{comment['body']}</p>
            </div>
            """, 
            unsafe_allow_html=True
        )
        
        # Display replies
        for reply_id in replies:
            display_comment_tree(reply_id, level + 1)
    
    # Display all top-level comments and their replies
    for comment_id in top_level_comments:
        display_comment_tree(comment_id)

try:
    # Fetch post
    post = execute_query(GET_POST_BY_ID, (post_id,))
    
    if not post:
        st.error("Post not found")
        st.stop()
        
    post = post[0]  # Get first result
    
    # Display post
    st.title(post['title'])
    st.write(post['selftext'])
    st.markdown(
        f"Posted by u/{post['author']} in r/{post['subreddit']} | "
        f"Score: {post['score']} | "
        f"Comments: {post['num_comments']} | "
        f"Posted on: {format_date(post['created_utc'])}"
    )
    st.divider()
    
    # Fetch comments
    comments = execute_query(
        GET_COMMENTS_FOR_POST.format(sort_order=SORT_ORDERS[comment_sort]), 
        (post_id,)
    )
    
    if comments:
        st.header("Comments")
        display_nested_comments(comments, highlight_comment_id)
    else:
        st.info("No comments found for this post")

except Exception as e:
    st.error(f"Error loading post: {str(e)}")
