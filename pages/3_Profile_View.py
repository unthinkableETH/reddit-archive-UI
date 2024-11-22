import streamlit as st
from database import execute_query
from queries import GET_USER_POSTS, GET_USER_COMMENTS, SEARCH_USERS, SORT_ORDERS
from utils import format_date, DARK_THEME_CSS

st.set_page_config(
    page_title="Profile View",
    page_icon="👜",
    layout="wide"
)

st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)

st.title("Profile View")

# Get username from URL parameters or search
params = st.query_params
username = params.get("username", "")

# Search interface
search_query = st.text_input("Search for a user:", value=username)

if search_query:
    try:
        matching_users = execute_query(
            SEARCH_USERS, 
            (f"%{search_query}%", f"%{search_query}%")
        )
        
        if matching_users:
            if len(matching_users) == 1:
                username = matching_users[0]['author']
            else:
                username = st.selectbox(
                    "Select a user:", 
                    [user['author'] for user in matching_users]
                )
    except Exception as e:
        st.error(f"Error searching users: {str(e)}")

if username:
    st.write(f"## u/{username}'s Profile")
    
    # Sorting controls
    col1, col2 = st.columns(2)
    with col1:
        post_sort = st.selectbox(
            "Sort posts by",
            ["newest", "oldest", "most_upvotes", "most_comments"],
            format_func=lambda x: {
                "newest": "Newest",
                "oldest": "Oldest",
                "most_upvotes": "Most Upvotes",
                "most_comments": "Most Comments"
            }[x]
        )
    with col2:
        comment_sort = st.selectbox(
            "Sort comments by",
            ["newest", "oldest", "most_upvotes"],
            format_func=lambda x: {
                "newest": "Newest",
                "oldest": "Oldest",
                "most_upvotes": "Most Upvotes"
            }[x]
        )

    try:
        # Create tabs for posts and comments
        posts_tab, comments_tab = st.tabs(["Posts", "Comments"])
        
        with posts_tab:
            posts = execute_query(
                GET_USER_POSTS.format(sort_order=SORT_ORDERS[post_sort]), 
                (username,)
            )
            
            if posts:
                st.write(f"### Posts ({len(posts)})")
                for post in posts:
                    with st.container():
                        st.markdown(f"### {post['title']}")
                        st.markdown(
                            f"Score: {post['score']} | "
                            f"Comments: {post['num_comments']} | "
                            f"Posted on: {format_date(post['created_utc'])} in r/{post['subreddit']}"
                        )
                        
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            with st.expander("Show Content"):
                                st.write(post['selftext'])
                        with col2:
                            st.link_button(
                                "View Discussion", 
                                f"/Post_View?post_id={post['id']}"
                            )
                        st.divider()
            else:
                st.info("No posts found")
        
        with comments_tab:
            comments = execute_query(
                GET_USER_COMMENTS.format(sort_order=SORT_ORDERS[comment_sort]), 
                (username,)
            )
            
            if comments:
                st.write(f"### Comments ({len(comments)})")
                for comment in comments:
                    st.markdown(
                        f"""<div style='padding: 8px; border-left: 2px solid #ccc;'>
                            <i>Score: {comment['score']} | "
                            Posted on: {format_date(comment['created_utc'])} in r/{comment['subreddit']}</i>
                            <p>{comment['body']}</p>
                            <a href="/Post_View?post_id={comment['submission_id']}&comment_id={comment['id']}">
                                View Full Discussion
                            </a>
                        </div>""",
                        unsafe_allow_html=True
                    )
                    st.divider()
            else:
                st.info("No comments found")
                
    except Exception as e:
        st.error(f"Error loading profile data: {str(e)}")
else:
    st.info("Enter a username to view their profile")
