import streamlit as st
import requests
from utils import format_date, DARK_THEME_CSS
from datetime import datetime, date
from streamlit.runtime.scriptrunner import get_script_run_ctx
import time

st.set_page_config(
    page_title="Search RepLadies Archive",
    page_icon="👜",
    layout="wide"
)

st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)

st.title("Search RepLadies Archive")

# At the top of your file
st.markdown("""
    <style>
    .streamlit-expanderHeader {
        font-size: 24px !important;
        font-weight: bold !important;
    }
    </style>
""", unsafe_allow_html=True)

# At the top of your file, add this CSS
st.markdown("""
    <style>
        .streamlit-expanderHeader {
            font-size: 1.25rem !important;
            font-weight: 600 !important;
        }
    </style>
""", unsafe_allow_html=True)

# API endpoint constants
API_BASE_URL = "https://m6njm571hh.execute-api.us-east-2.amazonaws.com"

# Add these near the top with other session state initializations
if 'previous_search_type' not in st.session_state:
    st.session_state.previous_search_type = None
if 'previous_start_date' not in st.session_state:
    st.session_state.previous_start_date = None
if 'previous_end_date' not in st.session_state:
    st.session_state.previous_end_date = None

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_valid_date_range():
    try:
        response = requests.get(f"{API_BASE_URL}/api/metadata/date_range", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                'min_date': datetime.strptime(data['earliest_date'], '%Y-%m-%d').date(),
                'max_date': datetime.strptime(data['latest_date'], '%Y-%m-%d').date()
            }
    except Exception as e:
        st.error(f"Error fetching date range: {str(e)}")
    
    # Fallback dates
    return {
        'min_date': datetime(2020, 1, 1).date(),
        'max_date': datetime.now().date()
    }

def scroll_to_top():
    js = '''
    <script>
        // Attempt to scroll the main content area
        var main = window.parent.document.querySelector('section[data-testid="stSidebar"] + section');
        if (main) {
            main.scrollTo({top: 0, behavior: 'smooth'});
        }

        // Attempt to scroll the iframe content
        window.scrollTo({top: 0, behavior: 'smooth'});

        // Attempt to scroll the app container
        var appView = window.parent.document.querySelector('.main');
        if (appView) {
            appView.scrollTo({top: 0, behavior: 'smooth'});
        }

        // Force scroll after a small delay to ensure it works
        setTimeout(function() {
            window.scrollTo(0, 0);
            if (main) main.scrollTo(0, 0);
            if (appView) appView.scrollTo(0, 0);
        }, 100);
    </script>
    '''
    st.components.v1.html(js, height=0)

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

# Add this helper function at the top with your other imports and helper functions
def should_show_next_button(results):
    """
    Determines if we should show the next button based on results
    """
    if not results or not isinstance(results, dict):
        return False
    
    # Check if we have results and they match the limit
    results_list = results.get('results', [])
    limit = results.get('limit', 20)
    
    # Show next if we have a full page of results and haven't reached total pages
    current_page = results.get('page', 1)
    total_pages = results.get('total_pages', 0)
    
    return len(results_list) == limit and current_page < total_pages

def format_author_link(author):
    """Format author name as link unless deleted"""
    if author in ['[deleted]', 'deleted', None]:
        return '[deleted]'
    return f"[u/{author}](/Profile_View?author={author})"

def get_preview(text, max_length=200):
    """Get a preview of text, cutting at the nearest sentence or word boundary"""
    if len(text) <= max_length:
        return text, False
    
    # Try to find the end of a sentence within the preview length
    preview = text[:max_length]
    sentence_end = max([preview.rfind('. '), preview.rfind('! '), preview.rfind('? ')])
    
    if sentence_end > max_length // 2:  # If we found a sentence end in a reasonable spot
        preview = text[:sentence_end + 1]
    else:  # Fall back to word boundary
        preview = text[:max_length].rsplit(' ', 1)[0]
    
    return f"{preview}...", True

# Sidebar controls
with st.sidebar:
    st.subheader("Search Options")
    search_type = st.radio(
        "Search in:", 
        ["post_title", "post_body", "comments", "everything"],
        format_func=lambda x: {
            "post_title": "Post Titles Only",
            "post_body": "Post Content Only",
            "comments": "Comments Only",
            "everything": "Everything (Posts + Comments)"
        }[x],
        key='search_type'
    )
    
    # Sort options here...
    
    # Date range picker
    st.subheader("Date Range")
    date_range = get_valid_date_range()
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "From",
            value=None,
            min_value=date_range['min_date'],
            max_value=date_range['max_date'],
            key='start_date'
        )
    with col2:
        end_date = st.date_input(
            "To",
            value=None,
            min_value=date_range['min_date'],
            max_value=date_range['max_date'],
            key='end_date'
        )

    # Now check for changes AFTER we have the values
    if (st.session_state.previous_search_type != search_type or 
        st.session_state.previous_start_date != st.session_state.get('start_date') or 
        st.session_state.previous_end_date != st.session_state.get('end_date')):
        st.session_state.page = 1
        st.session_state.previous_search_type = search_type
        st.session_state.previous_start_date = st.session_state.get('start_date')
        st.session_state.previous_end_date = st.session_state.get('end_date')

    # Debug info
    st.caption(f"Available date range: {date_range['min_date']} to {date_range['max_date']}")

# Main search interface
search_query = st.text_input("Enter your search terms", key="search_box")

# Add this near your search input, before the search box
with st.expander("💡 Search Tips - Boolean Operators (AND, OR, NOT)"):
    st.markdown("""
        Use Boolean Operators to refine your search:
        - `Chanel AND quality` (finds posts with both words)
        - `Chanel NOT caviar` (excludes posts with 'caviar')
        - `Chanel OR Hermes` (finds posts with either word)
        
        [Learn more about Boolean search tips here](https://www.reddit.com/r/WagoonLadies/comments/13w4wbc/tips_and_tricks_time_to_learn_something_new/)
    """)

# You could also add a small hint below the search box
if not search_query:
    st.caption("Pro tip: Try using AND, OR, NOT to refine your search")

if search_query:
    # Check if this is a new search by comparing with previous search
    if 'previous_search' not in st.session_state or st.session_state.previous_search != search_query:
        st.session_state.page = 1  # Reset to page 1
        st.session_state.previous_search = search_query  # Store current search
    
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

        # Display results with proper messaging
        no_results = True
        
        if search_type in ["post_title", "post_body", "everything"]:
            if post_results and post_results.get('results'):
                no_results = False
                st.header(f"Posts ({post_results['total_results']} total)")
                if search_type == "everything":
                    st.caption(f"Sorted by: {post_sort}")
                else:
                    st.caption(f"Sorted by: {sort_by}")
                
                current_start = ((post_results['page'] - 1) * post_results['limit']) + 1
                current_end = min(current_start + len(post_results['results']) - 1, post_results['total_results'])
                st.caption(f"Showing results {current_start} - {current_end} of {post_results['total_results']}")
                
                for post in post_results['results']:
                    st.subheader(post['title'])
                    
                    # Post metadata directly under subheader
                    author_link = format_author_link(post['author'])
                    st.caption(
                        f"Posted by {author_link} | "
                        f"Score: {post.get('score', 0)} | "
                        f"Comments: {post.get('num_comments', 0)} | "
                        f"Posted on: {post['formatted_date']}"
                    )
                    
                    with st.expander("Show Post"):
                        st.markdown(post['selftext'])
                        st.markdown("---")
                        col1, col2 = st.columns([5,1])
                        with col2:
                            st.markdown(f"[💬 View Discussion](/Post_View?post_id={post['id']})")
        
        if search_type in ["comments", "everything"]:
            if comment_results and comment_results.get('results'):
                no_results = False
                st.header(f"Comments ({comment_results['total_results']} total)")
                if search_type == "everything":
                    st.caption(f"Sorted by: {comment_sort}")
                else:
                    st.caption(f"Sorted by: {sort_by}")
                
                current_start = ((comment_results['page'] - 1) * comment_results['limit']) + 1
                current_end = min(current_start + len(comment_results['results']) - 1, comment_results['total_results'])
                st.caption(f"Showing results {current_start} - {current_end} of {comment_results['total_results']}")
                
                for comment in comment_results['results']:
                    st.markdown("---")  # Separator between comments
                    
                    # Comment metadata
                    author_link = format_author_link(comment['author'])
                    st.markdown(
                        f"**Comment by {author_link}** | "
                        f"Score: {comment.get('score', 0)} | "
                        f"Posted on: {comment['formatted_date']}"
                    )
                    
                    # Get preview and determine if we need an expander
                    preview, needs_expander = get_preview(comment['body'])
                    
                    if needs_expander:
                        st.markdown(preview)
                        with st.expander("Show full comment"):
                            st.markdown(comment['body'])
                    else:
                        st.markdown(comment['body'])
                        
                    st.markdown(f"[View full discussion →](/Post_View?post_id={comment['submission_id']})")
        
        if no_results:
            if search_type == "comments":
                st.info("No comments found matching your search.")
            elif search_type in ["post_title", "post_body"]:
                st.info("No posts found matching your search.")
            else:  # everything
                st.info("No posts or comments found matching your search.")

        # Pagination controls
        if search_query and (post_results or comment_results):
            col1, col2, col3 = st.columns([1, 2, 1])
            current_page = st.session_state.get('page', 1)
            
            # Get total pages for both result types
            post_total_pages = post_results.get('total_pages', 0) if post_results else 0
            comment_total_pages = comment_results.get('total_pages', 0) if comment_results else 0
            max_total_pages = max(post_total_pages, comment_total_pages)
            
            with col1:
                if current_page > 1:
                    if st.button("← Previous"):
                        scroll_to_top()
                        st.session_state.page = current_page - 1
                        time.sleep(0.2)
                        st.rerun()
            
            with col2:
                if max_total_pages > 0:
                    st.write(f"Page {current_page} of {max_total_pages}")
                else:
                    st.write(f"Page {current_page}")
            
            with col3:
                show_next = False
                
                if search_type in ["post_title", "post_body"]:
                    show_next = should_show_next_button(post_results)
                elif search_type == "comments":
                    show_next = should_show_next_button(comment_results)
                else:  # everything
                    # Show next if either posts or comments have more pages
                    show_next = (should_show_next_button(post_results) or 
                                should_show_next_button(comment_results))
                
                if show_next:
                    if st.button("Next →"):
                     import streamlit as st
import requests
from utils import format_date, DARK_THEME_CSS
from datetime import datetime, date
from streamlit.runtime.scriptrunner import get_script_run_ctx
import time

st.set_page_config(
    page_title="Search RepLadies Archive",
    page_icon="👜",
    layout="wide"
)

st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)

st.title("Search RepLadies Archive")

# At the top of your file
st.markdown("""
    <style>
    .streamlit-expanderHeader {
        font-size: 24px !important;
        font-weight: bold !important;
    }
    </style>
""", unsafe_allow_html=True)

# At the top of your file, add this CSS
st.markdown("""
    <style>
        .streamlit-expanderHeader {
            font-size: 1.25rem !important;
            font-weight: 600 !important;
        }
    </style>
""", unsafe_allow_html=True)

# API endpoint constants
API_BASE_URL = "https://m6njm571hh.execute-api.us-east-2.amazonaws.com"

# Add these near the top with other session state initializations
if 'previous_search_type' not in st.session_state:
    st.session_state.previous_search_type = None
if 'previous_start_date' not in st.session_state:
    st.session_state.previous_start_date = None
if 'previous_end_date' not in st.session_state:
    st.session_state.previous_end_date = None

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_valid_date_range():
    try:
        response = requests.get(f"{API_BASE_URL}/api/metadata/date_range", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return {
                'min_date': datetime.strptime(data['earliest_date'], '%Y-%m-%d').date(),
                'max_date': datetime.strptime(data['latest_date'], '%Y-%m-%d').date()
            }
    except Exception as e:
        st.error(f"Error fetching date range: {str(e)}")
    
    # Fallback dates
    return {
        'min_date': datetime(2020, 1, 1).date(),
        'max_date': datetime.now().date()
    }

def scroll_to_top():
    js = '''
    <script>
        // Attempt to scroll the main content area
        var main = window.parent.document.querySelector('section[data-testid="stSidebar"] + section');
        if (main) {
            main.scrollTo({top: 0, behavior: 'smooth'});
        }

        // Attempt to scroll the iframe content
        window.scrollTo({top: 0, behavior: 'smooth'});

        // Attempt to scroll the app container
        var appView = window.parent.document.querySelector('.main');
        if (appView) {
            appView.scrollTo({top: 0, behavior: 'smooth'});
        }

        // Force scroll after a small delay to ensure it works
        setTimeout(function() {
            window.scrollTo(0, 0);
            if (main) main.scrollTo(0, 0);
            if (appView) appView.scrollTo(0, 0);
        }, 100);
    </script>
    '''
    st.components.v1.html(js, height=0)

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

# Add this helper function at the top with your other imports and helper functions
def should_show_next_button(results):
    """
    Determines if we should show the next button based on results
    """
    if not results or not isinstance(results, dict):
        return False
    
    # Check if we have results and they match the limit
    results_list = results.get('results', [])
    limit = results.get('limit', 20)
    
    # Show next if we have a full page of results and haven't reached total pages
    current_page = results.get('page', 1)
    total_pages = results.get('total_pages', 0)
    
    return len(results_list) == limit and current_page < total_pages

def format_author_link(author):
    """Format author name as link unless deleted"""
    if author in ['[deleted]', 'deleted', None]:
        return '[deleted]'
    return f"[u/{author}](/Profile_View?author={author})"

def get_preview(text, max_length=200):
    """Get a preview of text, cutting at the nearest sentence or word boundary"""
    if len(text) <= max_length:
        return text, False
    
    # Try to find the end of a sentence within the preview length
    preview = text[:max_length]
    sentence_end = max([preview.rfind('. '), preview.rfind('! '), preview.rfind('? ')])
    
    if sentence_end > max_length // 2:  # If we found a sentence end in a reasonable spot
        preview = text[:sentence_end + 1]
    else:  # Fall back to word boundary
        preview = text[:max_length].rsplit(' ', 1)[0]
    
    return f"{preview}...", True

# Sidebar controls
with st.sidebar:
    st.subheader("Search Options")
    search_type = st.radio(
        "Search in:", 
        ["post_title", "post_body", "comments", "everything"],
        format_func=lambda x: {
            "post_title": "Post Titles Only",
            "post_body": "Post Content Only",
            "comments": "Comments Only",
            "everything": "Everything (Posts + Comments)"
        }[x],
        key='search_type'
    )
    
    # Sort options here...
    
    # Date range picker
    st.subheader("Date Range")
    date_range = get_valid_date_range()
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "From",
            value=None,
            min_value=date_range['min_date'],
            max_value=date_range['max_date'],
            key='start_date'
        )
    with col2:
        end_date = st.date_input(
            "To",
            value=None,
            min_value=date_range['min_date'],
            max_value=date_range['max_date'],
            key='end_date'
        )

    # Now check for changes AFTER we have the values
    if (st.session_state.previous_search_type != search_type or 
        st.session_state.previous_start_date != st.session_state.get('start_date') or 
        st.session_state.previous_end_date != st.session_state.get('end_date')):
        st.session_state.page = 1
        st.session_state.previous_search_type = search_type
        st.session_state.previous_start_date = st.session_state.get('start_date')
        st.session_state.previous_end_date = st.session_state.get('end_date')

    # Add debug info to see what's happening
    st.caption(f"Available date range: {date_range['min_date']} to {date_range['max_date']}")

# Main search interface
search_query = st.text_input("Enter your search terms", key="search_box")

# Add this near your search input, before the search box
with st.expander("💡 Search Tips - Boolean Operators (AND, OR, NOT)"):
    st.markdown("""
        Use Boolean Operators to refine your search:
        - `Chanel AND quality` (finds posts with both words)
        - `Chanel NOT caviar` (excludes posts with 'caviar')
        - `Chanel OR Hermes` (finds posts with either word)
        
        [Learn more about Boolean search tips here](https://www.reddit.com/r/WagoonLadies/comments/13w4wbc/tips_and_tricks_time_to_learn_something_new/)
    """)

# You could also add a small hint below the search box
if not search_query:
    st.caption("Pro tip: Try using AND, OR, NOT to refine your search")

if search_query:
    # Check if this is a new search by comparing with previous search
    if 'previous_search' not in st.session_state or st.session_state.previous_search != search_query:
        st.session_state.page = 1  # Reset to page 1
        st.session_state.previous_search = search_query  # Store current search
    
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

        # Display results with proper messaging
        no_results = True
        
        if search_type in ["post_title", "post_body", "everything"]:
            if post_results and post_results.get('results'):
                no_results = False
                st.header(f"Posts ({post_results['total_results']} total)")
                if search_type == "everything":
                    st.caption(f"Sorted by: {post_sort}")
                else:
                    st.caption(f"Sorted by: {sort_by}")
                
                current_start = ((post_results['page'] - 1) * post_results['limit']) + 1
                current_end = min(current_start + len(post_results['results']) - 1, post_results['total_results'])
                st.caption(f"Showing results {current_start} - {current_end} of {post_results['total_results']}")
                
                for post in post_results['results']:
                    st.subheader(post['title'])
                    
                    # Post metadata directly under subheader
                    author_link = format_author_link(post['author'])
                    st.caption(
                        f"Posted by {author_link} | "
                        f"Score: {post.get('score', 0)} | "
                        f"Comments: {post.get('num_comments', 0)} | "
                        f"Posted on: {post['formatted_date']}"
                    )
                    
                    with st.expander("Show Post"):
                        st.markdown(post['selftext'])
                        st.markdown("---")
                        col1, col2 = st.columns([5,1])
                        with col2:
                            st.markdown(f"[💬 View Discussion](/Post_View?post_id={post['id']})")
        
        if search_type in ["comments", "everything"]:
            if comment_results and comment_results.get('results'):
                no_results = False
                st.header(f"Comments ({comment_results['total_results']} total)")
                if search_type == "everything":
                    st.caption(f"Sorted by: {comment_sort}")
                else:
                    st.caption(f"Sorted by: {sort_by}")
                
                current_start = ((comment_results['page'] - 1) * comment_results['limit']) + 1
                current_end = min(current_start + len(comment_results['results']) - 1, comment_results['total_results'])
                st.caption(f"Showing results {current_start} - {current_end} of {comment_results['total_results']}")
                
                for comment in comment_results['results']:
                    st.markdown("---")  # Separator between comments
                    
                    # Comment metadata
                    author_link = format_author_link(comment['author'])
                    st.markdown(
                        f"**Comment by {author_link}** | "
                        f"Score: {comment.get('score', 0)} | "
                        f"Posted on: {comment['formatted_date']}"
                    )
                    
                    # Get preview and determine if we need an expander
                    preview, needs_expander = get_preview(comment['body'])
                    
                    if needs_expander:
                        st.markdown(preview)
                        with st.expander("Show full comment"):
                            st.markdown(comment['body'])
                    else:
                        st.markdown(comment['body'])
                        
                    st.markdown(f"[View full discussion →](/Post_View?post_id={comment['submission_id']})")
        
        if no_results:
            if search_type == "comments":
                st.info("No comments found matching your search.")
            elif search_type in ["post_title", "post_body"]:
                st.info("No posts found matching your search.")
            else:  # everything
                st.info("No posts or comments found matching your search.")

        # Pagination controls
        if search_query and (post_results or comment_results):
            col1, col2, col3 = st.columns([1, 2, 1])
            current_page = st.session_state.get('page', 1)
            
            # Get total pages for both result types
            post_total_pages = post_results.get('total_pages', 0) if post_results else 0
            comment_total_pages = comment_results.get('total_pages', 0) if comment_results else 0
            max_total_pages = max(post_total_pages, comment_total_pages)
            
            with col1:
                if current_page > 1:
                    if st.button("← Previous"):
                        scroll_to_top()
                        st.session_state.page = current_page - 1
                        time.sleep(0.2)
                        st.rerun()
            
            with col2:
                if max_total_pages > 0:
                    st.write(f"Page {current_page} of {max_total_pages}")
                else:
                    st.write(f"Page {current_page}")
            
            with col3:
                show_next = False
                
                if search_type in ["post_title", "post_body"]:
                    show_next = should_show_next_button(post_results)
                elif search_type == "comments":
                    show_next = should_show_next_button(comment_results)
                else:  # everything
                    # Show next if either posts or comments have more pages
                    show_next = (should_show_next_button(post_results) or 
                                should_show_next_button(comment_results))
                
                if show_next:
                    if st.button("Next →"):
                        scroll_to_top()
                        st.session_state.page = current_page + 1
                        time.sleep(0.2)
                        st.rerun()

    except Exception as e:
        st.error(f"Search error: {str(e)}")
else:
    st.info("Enter search terms above to begin")    scroll_to_top()
                        st.session_state.page = current_page + 1
                        time.sleep(0.2)
                        st.rerun()

    except Exception as e:
        st.error(f"Search error: {str(e)}")
else:
    st.info("Enter search terms above to begin") 
