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
        if parent_id == post_id:  # Top-level comment (direct reply to post)
            top_level_comments.append(comment['id'])
        else:  # Reply to another comment
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
        
        # Add level label with numbers for all levels
        level_label = {
            0: "Reply to Original Post (Level 1)",
            1: "Reply (Level 2)",
            2: "Reply to Reply (Level 3)",
        }.get(level, f"Level {level + 1} Reply")
        
        st.markdown(
            f"""
            <div style='margin-left: {left_margin}px; padding: 8px; border-left: 2px solid #ccc;'>
                <strong>u/{comment['author']}</strong> - <span style='color: #666;'>{level_label}</span><br>
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
        # Create a lookup dictionary for quick access
        comment_dict = {comment['id']: comment for comment in comments}
        
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
                for comment in highlighted_chain:
                    is_highlighted = comment['id'] == highlight_comment_id
                    style = "color: red;" if is_highlighted else ""
                    
                    st.markdown(
                        f"""<div style='padding: 8px; border-left: 2px solid #ccc;'>
                            <strong>u/{comment['author']}</strong> - 
                            <i>Score: {comment['score']} | Posted on: {format_date(comment['created_utc'])}</i>
                            <p style="{style}">{comment['body']}</p>
                        </div>""",
                        unsafe_allow_html=True
                    )
                    st.divider()
        
        # Display all comments in nested structure
        st.header("All Comments")
        display_nested_comments(comments, highlight_comment_id if highlight_comment else None)
    else:
        st.info("No comments found for this post")

except Exception as e:
    st.error(f"Error loading post: {str(e)}")
