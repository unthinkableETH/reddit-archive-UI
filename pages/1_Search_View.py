import streamlit as st
from database import execute_query
from queries import SEARCH_POSTS, SEARCH_COMMENTS, SORT_ORDERS
from utils import format_date, DARK_THEME_CSS

st.set_page_config(
    page_title="Search RepLadies Archive",
    page_icon="👜",
    layout="wide"
)

st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)

st.title("Search RepLadies Archive")

# Sidebar controls
with st.sidebar:
    st.header("Search Options")
    
    search_type = st.radio(
        "Search in:", 
        ["post_title", "post_body", "comments", "everything"],
        format_func=lambda x: {
            "post_title": "Post Titles",
            "post_body": "Post Body Text",
            "comments": "Comments Only",
            "everything": "Everything ℹ️"
        }[x],
        help="When searching 'Everything', posts will be displayed first, followed by comments"
    )
    
    exact_match = st.toggle("Exact match", value=False)
    highlight_enabled = st.toggle("Highlight search terms", value=True)
    
    sort_by = st.selectbox(
        "Sort results by", 
        ["most_upvotes", "newest", "oldest", "most_comments"],
        format_func=lambda x: {
            "most_upvotes": "Most Upvotes",
            "newest": "Newest",
            "oldest": "Oldest",
            "most_comments": "Most Comments"
        }[x]
    )
    
    # Date range picker
    st.subheader("Date Range")
    start_date = st.date_input("Start Date")
    end_date = st.date_input("End Date")

# Main search interface
search_query = st.text_input("Enter your search terms", key="search_box")

if search_query:
    try:
        # Build date filter if dates are selected
        date_filter = ""
        params = [search_query]  # First param is always the search query
        
        if start_date:
            date_filter += " AND created_utc >= %s"
            params.append(int(start_date.timestamp()))
        if end_date:
            date_filter += " AND created_utc <= %s"
            params.append(int(end_date.timestamp()))
            
        # Add pagination parameters
        posts_per_page = 20
        page = st.session_state.get('page', 1)
        params.extend([posts_per_page, (page - 1) * posts_per_page])
        
        # Execute search based on type
        if search_type in ["post_title", "post_body", "everything"]:
            posts = execute_query(
                SEARCH_POSTS.format(
                    sort_order=SORT_ORDERS[sort_by],
                    date_filter=date_filter
                ),
                tuple(params)
            )
            
            if posts:
                st.header("Posts")
                for post in posts:
                    with st.container():
                        st.markdown(f"### {post['title']}")
                        st.markdown(
                            f"Posted by u/{post['author']} | "
                            f"Score: {post['score']} | "
                            f"Comments: {post['num_comments']} | "
                            f"Posted on: {format_date(post['created_utc'])}"
                        )
                        with st.expander("Show Content"):
                            st.write(post['selftext'])
                        st.divider()
        
        if search_type in ["comments", "everything"]:
            comments = execute_query(
                SEARCH_COMMENTS.format(
                    sort_order=SORT_ORDERS[sort_by],
                    date_filter=date_filter
                ),
                tuple(params)
            )
            
            if comments:
                st.header("Comments")
                for comment in comments:
                    with st.container():
                        st.markdown(
                            f"""
                            <div style='padding: 8px; border-left: 2px solid #ccc;'>
                                <strong>u/{comment['author']}</strong><br>
                                <i>Score: {comment['score']} | Posted on: {format_date(comment['created_utc'])}</i>
                                <p>{comment['body']}</p>
                                <a href="/Post_View?post_id={comment['submission_id']}&comment_id={comment['id']}">
                                    View Full Discussion
                                </a>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        st.divider()
        
        # Pagination controls
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if page > 1:
                if st.button("← Previous"):
                    st.session_state.page = page - 1
                    st.rerun()
        with col2:
            st.write(f"Page {page}")
        with col3:
            if len(posts) == posts_per_page or len(comments) == posts_per_page:
                if st.button("Next →"):
                    st.session_state.page = page + 1
                    st.rerun()
                    
    except Exception as e:
        st.error(f"Search error: {str(e)}")
else:
    st.info("Enter search terms above to begin") 
