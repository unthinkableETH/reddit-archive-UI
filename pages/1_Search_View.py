import streamlit as st
import requests
from utils import format_date, DARK_THEME_CSS
from datetime import datetime, date

st.set_page_config(
    page_title="Search RepLadies Archive",
    page_icon="👜",
    layout="wide"
)

st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)

st.title("Search RepLadies Archive")

# API endpoint constants
API_BASE_URL = "https://m6njm571hh.execute-api.us-east-2.amazonaws.com"

def search_api_posts(query: str, sort: str, search_type: str = "title_body", page: int = 1, limit: int = 20, start_date=None, end_date=None):
    """Search posts using the API"""
    try:
        params = {
            "query": query,
            "sort": sort,
            "search_type": search_type,
            "page": page,
            "limit": limit
        }
        
        # Add dates independently if they exist
        if isinstance(start_date, (datetime, date)):
            params["start_date"] = start_date.strftime("%Y-%m-%d")
        if isinstance(end_date, (datetime, date)):
            params["end_date"] = end_date.strftime("%Y-%m-%d")
            
        # Debug info
        if params.get("start_date") or params.get("end_date"):
            st.caption(f"Date filter: {params.get('start_date', 'any')} to {params.get('end_date', 'any')}")
            
        response = requests.get(
            f"{API_BASE_URL}/api/search/posts",
            params=params,
            timeout=30
        )
        
        if response.status_code != 200:
            error_msg = response.text
            try:
                error_data = response.json()
                if 'detail' in error_data:
                    error_msg = error_data['detail']
            except:
                pass
            st.error(f"API Error ({response.status_code}): {error_msg}")
            return None
            
        return response.json()
        
    except requests.Timeout:
        st.error("Search took too long. Please try adding a date range or using more specific search terms.")
        return None
    except requests.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return None

def search_api_comments(query: str, sort: str, page: int = 1, limit: int = 20, start_date=None, end_date=None):
    """Search comments using the API"""
    try:
        params = {
            "query": query,
            "sort": sort,
            "page": page,
            "limit": limit
        }
        
        # Add dates independently if they exist
        if isinstance(start_date, (datetime, date)):
            params["start_date"] = start_date.strftime("%Y-%m-%d")
        if isinstance(end_date, (datetime, date)):
            params["end_date"] = end_date.strftime("%Y-%m-%d")
            
        response = requests.get(
            f"{API_BASE_URL}/api/search/comments",
            params=params,
            timeout=30
        )
        
        if response.status_code != 200:
            error_msg = response.text
            try:
                error_data = response.json()
                if 'detail' in error_data:
                    error_msg = error_data['detail']
            except:
                pass
            st.error(f"API Error ({response.status_code}): {error_msg}")
            return None
            
        return response.json()
        
    except requests.Timeout:
        st.error("Search took too long. Please try adding a date range or using more specific search terms.")
        return None
    except requests.RequestException as e:
        st.error(f"API Error: {str(e)}")
        return None

# Sidebar controls
with st.sidebar:
    st.header("Search Options")
    
    search_method = st.radio(
        "Search Method",
        ["Fast Search (Beta)"],
        help="Optimized search using our API"
    )
    
    search_type = st.radio(
        "Search in:", 
        ["post_title", "post_body", "comments", "everything"],
        format_func=lambda x: {
            "post_title": "Post Titles Only",
            "post_body": "Post Content Only",
            "comments": "Comments Only",
            "everything": "Everything (Posts + Comments)"
        }[x]
    )
    
    # Show different sort options based on search type
    if search_type == "everything":
        st.subheader("Sort Options")
        col1, col2 = st.columns(2)
        with col1:
            post_sort = st.selectbox(
                "Sort Posts by:",
                ["most_upvotes", "newest", "oldest", "most_comments"],
                format_func=lambda x: {
                    "most_upvotes": "Most Upvotes",
                    "newest": "Newest First",
                    "oldest": "Oldest First",
                    "most_comments": "Most Comments"
                }[x]
            )
        with col2:
            comment_sort = st.selectbox(
                "Sort Comments by:",
                ["most_upvotes", "newest", "oldest"],
                format_func=lambda x: {
                    "most_upvotes": "Most Upvotes",
                    "newest": "Newest First",
                    "oldest": "Oldest First"
                }[x]
            )
    else:
        # Single sort option for other search types
        sort_options = (
            ["most_upvotes", "newest", "oldest", "most_comments"]
            if search_type in ["post_title", "post_body"]
            else ["most_upvotes", "newest", "oldest"]
        )
        
        sort_by = st.selectbox(
            "Sort by:",
            sort_options,
            format_func=lambda x: {
                "most_upvotes": "Most Upvotes",
                "newest": "Newest First",
                "oldest": "Oldest First",
                "most_comments": "Most Comments"
            }[x]
        )
    
    # Date range picker
    st.subheader("Date Range")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "From",
            value=None,
            min_value=datetime(2015, 1, 1).date(),
            max_value=datetime.now().date(),
            help="Optional: Filter posts from this date"
        )
    with col2:
        end_date = st.date_input(
            "To",
            value=None,
            min_value=datetime(2015, 1, 1).date(),
            max_value=datetime.now().date(),
            help="Optional: Filter posts up to this date"
        )

# Main search interface
search_query = st.text_input("Enter your search terms", key="search_box")

if search_query:
    try:
        post_results = None
        comment_results = None
        
        # Handle post searches
        if search_type in ["post_title", "post_body", "everything"]:
            with st.spinner("Searching posts..."):
                api_search_type = {
                    "post_title": "title",
                    "post_body": "body",
                    "everything": "title_body"
                }[search_type]
                
                post_results = search_api_posts(
                    query=search_query,
                    sort=post_sort if search_type == "everything" else sort_by,
                    search_type=api_search_type,
                    page=st.session_state.get('page', 1),
                    start_date=start_date,
                    end_date=end_date
                )

        # Handle comment searches
        if search_type in ["comments", "everything"]:
            with st.spinner("Searching comments..."):
                comment_results = search_api_comments(
                    query=search_query,
                    sort=comment_sort if search_type == "everything" else sort_by,
                    page=st.session_state.get('page', 1),
                    start_date=start_date,
                    end_date=end_date
                )

        # Display results
        if post_results and post_results.get('results'):
            st.header(f"Posts ({post_results['total_results']} total)")
            if search_type == "everything":
                st.caption(f"Sorted by: {post_sort}")
            else:
                st.caption(f"Sorted by: {sort_by}")
            
            current_start = ((post_results['page'] - 1) * post_results['limit']) + 1
            current_end = min(current_start + len(post_results['results']) - 1, post_results['total_results'])
            st.caption(f"Showing results {current_start} - {current_end} of {post_results['total_results']}")
            
            for post in post_results['results']:
                with st.container():
                    st.markdown(f"### {post['title']}")
                    st.markdown(
                        f"Posted by u/{post['author']} | "
                        f"Score: {post.get('score', 'N/A')} | "  # Handle possible NULL values
                        f"Comments: {post.get('num_comments', 'N/A')} | "  # Handle possible NULL values
                        f"Posted on: {post['formatted_date']}"
                    )
                    with st.expander("Show Content"):
                        st.write(post['selftext'])
                    st.divider()
        else:
            st.info("No posts found matching your search.")

        if comment_results and comment_results.get('results'):
            st.header(f"Comments ({comment_results['total_results']} total)")
            if search_type == "everything":
                st.caption(f"Sorted by: {comment_sort}")
            else:
                st.caption(f"Sorted by: {sort_by}")
            
            current_start = ((comment_results['page'] - 1) * comment_results['limit']) + 1
            current_end = min(current_start + len(comment_results['results']) - 1, comment_results['total_results'])
            st.caption(f"Showing results {current_start} - {current_end} of {comment_results['total_results']}")
            
            for comment in comment_results['results']:
                with st.container():
                    st.markdown(
                        f"""
                        <div style='padding: 8px; border-left: 2px solid #ccc;'>
                            <strong>u/{comment['author']}</strong><br>
                            <i>Score: {comment['score']} | Posted on: {comment['formatted_date']}</i>
                            <p>{comment['body']}</p>
                            <a href="/Post_View?post_id={comment['submission_id']}&comment_id={comment['id']}">
                                View Full Discussion
                            </a>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    st.divider()
        else:
            st.info("No comments found matching your search.")

        # Pagination controls
        if (post_results and post_results.get('results')) or (comment_results and comment_results.get('results')):
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if st.session_state.get('page', 1) > 1:
                    if st.button("← Previous"):
                        st.session_state.page = st.session_state.get('page', 1) - 1
                        st.rerun()
            with col2:
                st.write(f"Page {st.session_state.get('page', 1)}")
            with col3:
                if ((post_results and len(post_results['results']) == post_results['limit']) or 
                    (comment_results and len(comment_results['results']) == comment_results['limit'])):
                    if st.button("Next →"):
                        st.session_state.page = st.session_state.get('page', 1) + 1
                        st.rerun()

    except Exception as e:
        st.error(f"Search error: {str(e)}")
else:
    st.info("Enter search terms above to begin") 
