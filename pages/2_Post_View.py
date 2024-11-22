import streamlit as st
import streamlit.components.v1 as components
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
    
    # Create HTML for comments
    comments_html = ""
    comment_dict = {}
    top_level_comments = []
    
    # Build comment dictionary
    for comment in comments:
        comment_dict[comment['id']] = {
            'data': comment,
            'replies': [],
            'level': 0
        }
    
    # Build hierarchy
    for comment in comments:
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
        replies = comment_dict[comment_id]['replies']
        
        level_label = {
            0: "Reply to Original Post (Level 1)",
            1: "Reply (Level 2)",
            2: "Reply to Reply (Level 3)",
        }.get(level, f"Level {level + 1} Reply")
        
        reply_count = len(replies)
        reply_text = f"({reply_count} {'reply' if reply_count == 1 else 'replies'})" if reply_count > 0 else "(no replies)"
        
        return f"""
            <div class="comment" data-level="{level}">
                <div class="comment-header">
                    <button class="collapse-btn" onclick="toggleComment('{comment['id']}')">
                        [+] Click to expand/collapse {reply_text}
                    </button>
                    <strong>u/{comment['author']}</strong> - 
                    <span class="level-label">{level_label}</span><br>
                    <span class="metadata">Score: {comment['score']} | Posted on: {format_date(comment['created_utc'])}</span>
                </div>
                <div id="content-{comment['id']}" class="comment-content">
                    <div class="comment-body" id="body-{comment['id']}" style="display: none;">
                        {comment['body']}
                    </div>
                    <div class="replies" id="replies-{comment['id']}" style="display: none;">
                        {''.join(build_comment_html(reply_id, level + 1) for reply_id in replies)}
                    </div>
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
                padding: 8px;
                border-left: 2px solid #666;
            }}
            .comment[data-level="0"] {{ margin-left: 0px; }}
            .comment[data-level="1"] {{ margin-left: 20px; }}
            .comment[data-level="2"] {{ margin-left: 40px; }}
            .comment[data-level="3"] {{ margin-left: 60px; }}
            .comment[data-level="4"] {{ margin-left: 80px; }}
            .comment-header {{
                margin-bottom: 8px;
                color: #FAFAFA;
            }}
            .collapse-btn {{
                background: transparent;
                border: 1px solid #666;
                color: #FAFAFA;
                padding: 2px 8px;
                margin-right: 8px;
                cursor: pointer;
                border-radius: 3px;
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
            }}
        </style>
        <script>
            function toggleComment(id) {{
                const body = document.getElementById('body-' + id);
                const replies = document.getElementById('replies-' + id);
                const btn = event.target;
                const isExpanded = body.style.display === 'block';
                
                body.style.display = isExpanded ? 'none' : 'block';
                if (replies) replies.style.display = isExpanded ? 'none' : 'block';
                
                btn.textContent = btn.textContent.replace(
                    isExpanded ? '[-]' : '[+]',
                    isExpanded ? '[+]' : '[-]'
                );
                
                // Update the text
                const replyText = btn.textContent.match(/\(.*\)/)[0];
                btn.textContent = `${isExpanded ? '[+]' : '[-]'} Click to ${isExpanded ? 'expand' : 'collapse'} ${replyText}`;
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
