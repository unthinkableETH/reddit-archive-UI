"""
SQL Queries for RepLadies Archive

This module contains all PostgreSQL queries used across the application.
Queries are organized by function (posts, comments, search) and use 
PostgreSQL-specific full-text search syntax.

Usage:
    from queries import GET_POSTS, SORT_ORDERS
    query = GET_POSTS.format(sort_order=SORT_ORDERS['newest'])
"""

from typing import Dict, TypedDict

class SortOrders(TypedDict):
    most_upvotes: str
    newest: str
    oldest: str
    most_comments: str

# Sort order configurations
SORT_ORDERS: SortOrders = {
    "most_upvotes": "score DESC",
    "newest": "created_utc DESC",
    "oldest": "created_utc ASC",
    "most_comments": "num_comments DESC"
}

# Main post queries
GET_POSTS = """
    SELECT id, author, title, selftext, created_utc, num_comments, score, subreddit
    FROM submissions
    ORDER BY {sort_order}
    LIMIT %s OFFSET %s
"""

GET_POST_BY_ID = """
    SELECT title, selftext, author, created_utc, id, score, num_comments, subreddit
    FROM submissions 
    WHERE id = %s
"""

# Comment queries
GET_COMMENTS_FOR_POST = """
    SELECT id, parent_id, body, author, created_utc, score
    FROM comments 
    WHERE submission_id = %s 
    ORDER BY {sort_order}
"""

# Search queries
SEARCH_POSTS = """
    SELECT id, author, title, selftext, created_utc, num_comments, score, subreddit
    FROM submissions 
    WHERE to_tsvector('english', title || ' ' || COALESCE(selftext, '')) @@ plainto_tsquery('english', %s)
    {date_filter}
    ORDER BY {sort_order}
    LIMIT %s OFFSET %s
"""

SEARCH_POSTS_EXACT = """
    SELECT title, selftext, author, created_utc, id, score, num_comments, subreddit
    FROM submissions 
    WHERE LOWER(title || ' ' || selftext) LIKE '%%' || LOWER(%s) || '%%'
    {date_filter}
    ORDER BY {sort_order}
    LIMIT %s OFFSET %s
"""

SEARCH_COMMENTS = """
    SELECT id, link_id, author, body, created_utc, score, subreddit
    FROM comments 
    WHERE to_tsvector('english', body) @@ plainto_tsquery('english', %s)
    {date_filter}
    ORDER BY {sort_order}
    LIMIT %s OFFSET %s
"""

# Count queries for pagination
COUNT_POSTS = "SELECT COUNT(*) FROM submissions"

COUNT_SEARCH_RESULTS = """
    SELECT 
        (SELECT COUNT(*) 
         FROM submissions 
         WHERE to_tsvector('english', title || ' ' || COALESCE(selftext, '')) @@ plainto_tsquery('english', %s)
         {date_filter}) as post_count,
        (SELECT COUNT(*) 
         FROM comments 
         WHERE to_tsvector('english', body) @@ plainto_tsquery('english', %s)
         {date_filter}) as comment_count
"""

# Date range queries
GET_DATE_BOUNDS = """
    SELECT 
        MIN(created_utc) as min_date,
        MAX(created_utc) as max_date
    FROM (
        SELECT created_utc FROM submissions
        UNION ALL
        SELECT created_utc FROM comments
    ) dates
"""

# Add these missing queries for profile view
GET_USER_POSTS = """
    SELECT title, selftext, created_utc, id, score, num_comments, subreddit
    FROM submissions 
    WHERE author = %s
    ORDER BY {sort_order}
"""

GET_USER_COMMENTS = """
    SELECT id, link_id, parent_id, body, created_utc, score, subreddit
    FROM comments 
    WHERE author = %s
    ORDER BY {sort_order}
"""

SEARCH_USERS = """
    SELECT DISTINCT author 
    FROM (
        SELECT author FROM submissions WHERE author LIKE %s
        UNION
        SELECT author FROM comments WHERE author LIKE %s
    ) authors
    ORDER BY author
    LIMIT 10
"""

# Add exact match count query
COUNT_SEARCH_RESULTS_EXACT = """
    SELECT 
        (SELECT COUNT(*) 
         FROM submissions 
         WHERE LOWER(title || ' ' || COALESCE(selftext, '')) LIKE '%%' || LOWER(%s) || '%%'
         {date_filter}) as post_count,
        (SELECT COUNT(*) 
         FROM comments 
         WHERE LOWER(body) LIKE '%%' || LOWER(%s) || '%%'
         {date_filter}) as comment_count
""" 
