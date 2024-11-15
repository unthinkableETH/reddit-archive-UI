import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st
from datetime import datetime
import re
import os
import time

# Must be the first Streamlit command
st.set_page_config(
    page_title="Post View",
    page_icon="👜",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "RepLadies Reddit Archive"
    }
)

# Dark theme styling
st.markdown("""
    <style>
        /* Main background */
        .stApp {
            background-color: #0E1117;
        }
        
        /* Sidebar */
        [data-testid="stSidebar"] {
            background-color: #262730;
        }
        
        /* Card backgrounds */
        [data-testid="stExpander"] {
            background-color: #262730;
        }
        
        /* Text colors */
        .stMarkdown {
            color: #FAFAFA;
        }
        
        /* All links */
        a {
            color: #4A9EFF !important;
        }
        a:hover {
            color: #7CB9FF !important;
            text-decoration: none;
        }
        
        /* Dividers */
        hr {
            border-color: #333333;
        }
    </style>
""", unsafe_allow_html=True)

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

    1. Go to the [main page](/)
    2. Search for comments using the search box
    3. Click "View Full Post and Comments" on any comment in the search results
    """)
    st.stop()

# Sidebar controls
st.sidebar.header("Post View")
st.sidebar.subheader("Comment Controls")

comment_sort = st.sidebar.selectbox(
    "Sort comments by",
    ["most_upvotes", "newest", "oldest"],
    format_func=lambda x: {
        "most_upvotes": "Most Upvotes",
        "newest": "Newest",
        "oldest": "Oldest"
    }[x],
    index=0
)

bring_to_top = st.sidebar.toggle("Bring highlighted comment to top", value=True)
highlight_comment = st.sidebar.toggle("Highlight search result comment", value=True)

@st.cache_resource(show_spinner=False, ttl=3600)  # Cache for 1 hour
def get_database_connection():
    conn = psycopg2.connect(
        dbname=st.secrets["postgres"]["dbname"],
        user=st.secrets["postgres"]["user"],
        password=st.secrets["postgres"]["password"],
        host=st.secrets["postgres"]["host"],
        port=st.secrets["postgres"]["port"],
        connect_timeout=30,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
        application_name='repladies_streamlit_post'
    )
    return conn

def clean_reddit_id(reddit_id, keep_prefix=False):
    """Standardize Reddit ID format"""
    if not reddit_id:
        return None
    if reddit_id.startswith(('t1_', 't3_')):
        return reddit_id if keep_prefix else reddit_id.split('_')[1]
    return reddit_id

def add_prefix(id_str, type_prefix):
    """Add Reddit type prefix if missing"""
    if not id_str:
        return None
    if id_str.startswith(('t1_', 't3_')):
        return id_str
    return f"{type_prefix}_{id_str}"

def format_date(utc_timestamp):
    """Convert UTC timestamp to readable date"""
    try:
        utc_timestamp = int(utc_timestamp)
        return datetime.utcfromtimestamp(utc_timestamp).strftime('%B %d, %Y %I:%M %p')
    except ValueError:
        return "Invalid Date"

def fetch_post(cursor, post_id):
    """Fetch post details from database"""
    cursor.execute("""
        SELECT title, selftext, author, created_utc, id, score, num_comments, subreddit
        FROM submissions 
        WHERE id = %s
    """, (post_id,))
    return cursor.fetchone()

def fetch_comments_with_hierarchy(cursor, post_id, sort_order="most_upvotes"):
    """Fetch and organize comments in hierarchy"""
    order_clause = {
        "most_upvotes": "score DESC",
        "newest": "created_utc DESC",
        "oldest": "created_utc ASC"
    }.get(sort_order, "score DESC")

    try:
        cursor.execute(f"""
            SELECT id, submission_id as link_id, parent_id, author, body, created_utc, score, subreddit 
            FROM comments 
            WHERE submission_id = %s 
            ORDER BY {order_clause}
        """, (add_prefix(post_id, 't3'),))
        comments = cursor.fetchall()

        nested_comments = []
        comment_dict = {comment['id']: comment for comment in comments}

        def add_nested_comments(comment, level=0):
            nested_comments.append((comment, level))
            for reply in comments:
                if reply['parent_id'] == f't1_{clean_reddit_id(comment["id"])}':
                    add_nested_comments(reply, level + 1)

        for comment in comments:
            if comment['parent_id'] == f't3_{post_id}':
                add_nested_comments(comment)

        return nested_comments
    except Exception as e:
        st.error(f"Error fetching comments: {e}")
        return []

try:
    # Fetch post and comments
    conn = get_database_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        post = fetch_post(cursor, post_id)
        
        if post:
            # Display post details
            st.title(post['title'])
            st.write(post['selftext'])
            formatted_date = format_date(post['created_utc'])
            st.write(f"Score: {post['score']} | Comments: {post['num_comments']} | Posted on: {formatted_date}")
            st.markdown(f'Posted by <a href="/Profile_View?username={post["author"]}">u/{post["author"]}</a> in r/{post["subreddit"]}', unsafe_allow_html=True)
            st.markdown("---")

            # Fetch and display comments
            nested_comments = fetch_comments_with_hierarchy(cursor, post_id, sort_order=comment_sort)
            
            # Create a lookup dictionary for quick access
            comment_lookup = {clean_reddit_id(comment['id']): (comment, level) for comment, level in nested_comments}
            
            # Handle highlighted comment if it exists
            if highlight_comment_id and highlight_comment and bring_to_top:
                highlighted_comment = comment_lookup.get(clean_reddit_id(highlight_comment_id))
                if highlighted_comment:
                    highlighted_chain = []
                    seen_comments = set()
                    
                    # Get the direct parent chain
                    current_comment = highlighted_comment
                    while current_comment:
                        comment, level = current_comment
                        
                        if clean_reddit_id(comment['id']) not in seen_comments:
                            highlighted_chain.insert(0, (comment, level))
                            seen_comments.add(clean_reddit_id(comment['id']))
                        
                        parent_id = clean_reddit_id(comment['parent_id'])
                        
                        if comment['parent_id'].startswith('t3_'):
                            break
                            
                        current_comment = comment_lookup.get(parent_id)
                        if not current_comment:
                            break

                    # Get all children recursively
                    def get_all_children(comment_id, base_level):
                        children = []
                        for comment, level in nested_comments:
                            if comment['parent_id'] == f't1_{clean_reddit_id(comment_id)}' and clean_reddit_id(comment['id']) not in seen_comments:
                                children.append((comment, level))
                                seen_comments.add(clean_reddit_id(comment['id']))
                                children.extend(get_all_children(comment['id'], level + 1))
                        return children

                    children = get_all_children(highlight_comment_id, highlighted_comment[1] + 1)
                    highlighted_chain.extend(children)

                    if highlighted_chain:
                        st.markdown("### Highlighted Comment Thread:")
                        for comment, level in highlighted_chain:
                            left_margin = min(level * 20, 200)
                            style = f"margin-left: {left_margin}px; padding: 8px; border-left: 2px solid #ccc;"
                            
                            is_highlighted = clean_reddit_id(comment['id']) == clean_reddit_id(highlight_comment_id)
                            formatted_body = comment['body'].replace('\n', '<br>')
                            
                            if is_highlighted:
                                st.markdown(
                                    f"""<div style='{style}'>
                                        <strong>Level {level} - <a href="/Profile_View?username={comment['author']}">u/{comment['author']}</a></strong> - 
                                        <i>Score: {comment['score']} | Posted on: {format_date(comment['created_utc'])}</i><br>
                                        <p style="color: red; text-decoration: underline;">{formatted_body}</p>
                                    </div>""", 
                                    unsafe_allow_html=True
                                )
                            else:
                                st.markdown(
                                    f"""<div style='{style}'>
                                        <strong>Level {level} - <a href="/Profile_View?username={comment['author']}">u/{comment['author']}</a></strong> - 
                                        <i>Score: {comment['score']} | Posted on: {format_date(comment['created_utc'])}</i><br>
                                        <p>{formatted_body}</p>
                                    </div>""", 
                                    unsafe_allow_html=True
                                )
                            st.markdown("---")

                    displayed_comment_ids = seen_comments
                else:
                    displayed_comment_ids = set()
            else:
                displayed_comment_ids = set()

            # Display remaining comments
            st.markdown("### All Comments:")
            for comment, level in nested_comments:
                if clean_reddit_id(comment['id']) not in displayed_comment_ids:
                    left_margin = min(level * 20, 200)
                    style = f"margin-left: {left_margin}px; padding: 8px; border-left: 2px solid #ccc;"
                    
                    is_highlighted = clean_reddit_id(comment['id']) == clean_reddit_id(highlight_comment_id) and highlight_comment
                    formatted_body = comment['body'].replace('\n', '<br>')
                    
                    if is_highlighted:
                        st.markdown(
                            f"""<div style='{style}'>
                                <strong>Level {level} - <a href="/Profile_View?username={comment['author']}">u/{comment['author']}</a></strong> - 
                                <i>Score: {comment['score']} | Posted on: {format_date(comment['created_utc'])}</i><br>
                                <p style="color: red; text-decoration: underline;">{formatted_body}</p>
                            </div>""", 
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            f"""<div style='{style}'>
                                <strong>Level {level} - <a href="/Profile_View?username={comment['author']}">u/{comment['author']}</a></strong> - 
                                <i>Score: {comment['score']} | Posted on: {format_date(comment['created_utc'])}</i><br>
                                <p>{formatted_body}</p>
                            </div>""", 
                            unsafe_allow_html=True
                        )
                    st.markdown("---")
        else:
            st.error("Post not found")

except psycopg2.Error as e:
    st.error(f"Database error: {e}")
except Exception as e:
    st.error(f"An unexpected error occurred: {e}")
