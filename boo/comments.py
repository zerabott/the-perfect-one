from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import COMMENTS_PER_PAGE, CHANNEL_ID, BOT_USERNAME
from utils import escape_markdown_text
from db import get_comment_count
from db_connection import get_db_connection, execute_query, adapt_query
from submission import is_media_post, get_media_info
import logging

logger = logging.getLogger(__name__)


def save_comment(post_id, content, user_id, parent_comment_id=None):
    """Save a comment to the database"""
    try:
        db_conn = get_db_connection()
        with db_conn.get_connection() as conn:
            cursor = conn.cursor()
            
            # First, validate that the post exists
            post_check_query = adapt_query("SELECT post_id FROM posts WHERE post_id = ? AND approved = 1")
            cursor.execute(post_check_query, (post_id,))
            post_exists = cursor.fetchone()
            
            if not post_exists:
                logger.error(f"Cannot save comment: Post {post_id} does not exist or is not approved")
                return None, f"Post {post_id} not found or not approved"
            
            # Validate parent comment if provided
            if parent_comment_id:
                parent_check_query = adapt_query("SELECT comment_id FROM comments WHERE comment_id = ?")
                cursor.execute(parent_check_query, (parent_comment_id,))
                parent_exists = cursor.fetchone()
                
                if not parent_exists:
                    logger.error(f"Cannot save comment: Parent comment {parent_comment_id} does not exist")
                    return None, f"Parent comment {parent_comment_id} not found"
            
            # Insert comment using proper database abstraction
            if db_conn.use_postgresql:
                # PostgreSQL: use RETURNING clause to get the ID
                insert_query = adapt_query("INSERT INTO comments (post_id, content, user_id, parent_comment_id) VALUES (?, ?, ?, ?) RETURNING comment_id")
                cursor.execute(insert_query, (post_id, content, user_id, parent_comment_id))
                comment_id = cursor.fetchone()[0]
            else:
                # SQLite: use lastrowid
                insert_query = adapt_query("INSERT INTO comments (post_id, content, user_id, parent_comment_id) VALUES (?, ?, ?, ?)")
                cursor.execute(insert_query, (post_id, content, user_id, parent_comment_id))
                comment_id = cursor.lastrowid

            # Update user stats
            update_query = adapt_query("UPDATE users SET comments_posted = comments_posted + 1 WHERE user_id = ?")
            cursor.execute(update_query, (user_id,))
            
            if db_conn.use_postgresql:
                conn.commit()
            
            return comment_id, None
    except Exception as e:
        logger.error(f"Error saving comment: {e}")
        return None, f"Database error: {str(e)}"


def get_post_with_channel_info(post_id):
    """Get post information including channel message ID"""
    try:
        query = adapt_query("SELECT post_id, content, category, channel_message_id, approved FROM posts WHERE post_id = ?")
        result = execute_query(query, (post_id,), fetch='one')
        return result
    except Exception as e:
        logger.error(f"Error getting post info: {e}")
        return None


def get_comments_paginated(post_id, page=1):
    """Get comments for a post in flat structure like Telegram native replies"""
    offset = (page - 1) * COMMENTS_PER_PAGE

    try:
        # Get total count using the existing function
        total_comments = get_comment_count(post_id)

        # Get paginated comments
        db_conn = get_db_connection()
        
        if db_conn.use_postgresql:
            # PostgreSQL version with ROW_NUMBER()
            query = """
                SELECT comment_id, content, timestamp, likes, dislikes, flagged, parent_comment_id,
                       ROW_NUMBER() OVER (ORDER BY timestamp ASC) as comment_number
                FROM comments 
                WHERE post_id = %s
                ORDER BY timestamp ASC
                LIMIT %s OFFSET %s
            """
        else:
            # SQLite version with ROW_NUMBER()
            query = """
                SELECT comment_id, content, timestamp, likes, dislikes, flagged, parent_comment_id,
                       ROW_NUMBER() OVER (ORDER BY timestamp ASC) as comment_number
                FROM comments 
                WHERE post_id = ?
                ORDER BY timestamp ASC
                LIMIT ? OFFSET ?
            """
        
        comments = execute_query(query, (post_id, COMMENTS_PER_PAGE, offset), fetch='all')

        # Transform into simplified flat structure
        comments_flat = []
        for comment in comments or []:
            comment_id = comment[0]
            content = comment[1]
            timestamp = comment[2]
            likes = comment[3]
            dislikes = comment[4]
            flagged = comment[5]
            parent_comment_id = comment[6]
            comment_number = comment[7]
            
            comment_data = {
                'comment_id': comment_id,
                'content': content,
                'timestamp': timestamp,
                'likes': likes,
                'dislikes': dislikes,
                'flagged': flagged,
                'parent_comment_id': parent_comment_id,
                'comment_number': comment_number,
                'is_reply': parent_comment_id is not None
            }
            
            # If this is a reply, get the original comment info
            if parent_comment_id:
                original_query = adapt_query("SELECT comment_id, content, timestamp FROM comments WHERE comment_id = ?")
                original = execute_query(original_query, (parent_comment_id,), fetch='one')
                if original:
                    comment_data['original_comment'] = {
                        'comment_id': original[0],
                        'content': original[1],
                        'timestamp': original[2]
                    }
            
            comments_flat.append(comment_data)

        total_pages = (total_comments + COMMENTS_PER_PAGE - 1) // COMMENTS_PER_PAGE

        return comments_flat, page, total_pages, total_comments
    except Exception as e:
        logger.error(f"Error getting paginated comments: {e}")
        return [], 1, 1, 0


def get_comment_by_id(comment_id):
    """Get a specific comment by ID"""
    try:
        query = adapt_query("SELECT * FROM comments WHERE comment_id = ?")
        return execute_query(query, (comment_id,), fetch='one')
    except Exception as e:
        logger.error(f"Error getting comment by ID: {e}")
        return None


def react_to_comment(user_id, comment_id, reaction_type):
    """Add or update reaction to a comment"""
    try:
        db_conn = get_db_connection()
        with db_conn.get_connection() as conn:
            cursor = conn.cursor()

            # Check existing reaction
            check_query = adapt_query("SELECT reaction_type FROM reactions WHERE user_id = ? AND target_type = 'comment' AND target_id = ?")
            cursor.execute(check_query, (user_id, comment_id))
            existing = cursor.fetchone()

            if existing:
                if existing[0] == reaction_type:
                    # Remove reaction if same type
                    delete_query = adapt_query("DELETE FROM reactions WHERE user_id = ? AND target_type = 'comment' AND target_id = ?")
                    cursor.execute(delete_query, (user_id, comment_id))
                    
                    # Update comment counts
                    if reaction_type == 'like':
                        update_query = adapt_query("UPDATE comments SET likes = likes - 1 WHERE comment_id = ?")
                    else:
                        update_query = adapt_query("UPDATE comments SET dislikes = dislikes - 1 WHERE comment_id = ?")
                    cursor.execute(update_query, (comment_id,))
                    action = "removed"
                else:
                    # Update reaction type
                    update_reaction_query = adapt_query("UPDATE reactions SET reaction_type = ? WHERE user_id = ? AND target_type = 'comment' AND target_id = ?")
                    cursor.execute(update_reaction_query, (reaction_type, user_id, comment_id))
                    
                    # Update comment counts
                    if existing[0] == 'like':
                        update_query = adapt_query("UPDATE comments SET likes = likes - 1, dislikes = dislikes + 1 WHERE comment_id = ?")
                    else:
                        update_query = adapt_query("UPDATE comments SET likes = likes + 1, dislikes = dislikes - 1 WHERE comment_id = ?")
                    cursor.execute(update_query, (comment_id,))
                    action = "changed"
            else:
                # Add new reaction
                insert_query = adapt_query("INSERT INTO reactions (user_id, target_type, target_id, reaction_type) VALUES (?, 'comment', ?, ?)")
                cursor.execute(insert_query, (user_id, comment_id, reaction_type))
                
                # Update comment counts
                if reaction_type == 'like':
                    update_query = adapt_query("UPDATE comments SET likes = likes + 1 WHERE comment_id = ?")
                else:
                    update_query = adapt_query("UPDATE comments SET dislikes = dislikes + 1 WHERE comment_id = ?")
                cursor.execute(update_query, (comment_id,))
                action = "added"

            if db_conn.use_postgresql:
                conn.commit()

            # Return current counts
            count_query = adapt_query("SELECT likes, dislikes FROM comments WHERE comment_id = ?")
            cursor.execute(count_query, (comment_id,))
            counts = cursor.fetchone()
            current_likes = counts[0] if counts else 0
            current_dislikes = counts[1] if counts else 0

            return True, action, current_likes, current_dislikes
    except Exception as e:
        logger.error(f"Error reacting to comment: {e}")
        return False, str(e), 0, 0


def flag_comment(comment_id):
    """Flag a comment for review"""
    try:
        query = adapt_query("UPDATE comments SET flagged = 1 WHERE comment_id = ?")
        execute_query(query, (comment_id,))
        return True
    except Exception as e:
        logger.error(f"Error flagging comment: {e}")
        return False


def get_user_reaction(user_id, comment_id):
    """Get user's reaction to a specific comment"""
    try:
        query = adapt_query("SELECT reaction_type FROM reactions WHERE user_id = ? AND target_type = 'comment' AND target_id = ?")
        result = execute_query(query, (user_id, comment_id), fetch='one')
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Error getting user reaction: {e}")
        return None


def get_comment_sequential_number(comment_id):
    """Get the sequential number of a comment within its post (flat structure)"""
    try:
        # Get the comment's post_id and timestamp
        info_query = adapt_query("SELECT post_id, timestamp FROM comments WHERE comment_id = ?")
        comment_info = execute_query(info_query, (comment_id,), fetch='one')

        if not comment_info:
            return None

        post_id, timestamp = comment_info

        # Count all comments in this post that were posted before or at the same time
        count_query = adapt_query("""
            SELECT COUNT(*) FROM comments 
            WHERE post_id = ? AND timestamp <= ?
            ORDER BY timestamp ASC
        """)
        result = execute_query(count_query, (post_id, timestamp), fetch='one')
        return result[0] if result else 1
    except Exception as e:
        logger.error(f"Error getting comment sequential number: {e}")
        return 1


def get_parent_comment_for_reply(comment_id):
    """Get the original comment details for a reply (flat structure)"""
    try:
        # Get parent comment ID
        parent_query = adapt_query("SELECT parent_comment_id FROM comments WHERE comment_id = ?")
        result = execute_query(parent_query, (comment_id,), fetch='one')

        if not result or not result[0]:
            return None

        parent_comment_id = result[0]

        # Get parent comment details
        details_query = adapt_query("SELECT comment_id, post_id, content, timestamp FROM comments WHERE comment_id = ?")
        parent_comment = execute_query(details_query, (parent_comment_id,), fetch='one')

        if parent_comment:
            parent_sequential_number = get_comment_sequential_number(parent_comment_id)
            return {
                'comment_id': parent_comment[0],
                'post_id': parent_comment[1],
                'content': parent_comment[2],
                'timestamp': parent_comment[3],
                'sequential_number': parent_sequential_number
            }

        return None
    except Exception as e:
        logger.error(f"Error getting parent comment: {e}")
        return None


def find_comment_page(comment_id):
    """Find which page a comment is on for navigation"""
    try:
        # Get comment info
        info_query = adapt_query("SELECT post_id, parent_comment_id FROM comments WHERE comment_id = ?")
        comment_info = execute_query(info_query, (comment_id,), fetch='one')
        
        if not comment_info:
            return None
            
        post_id, parent_comment_id = comment_info
        
        # If it's a reply, find the parent comment's page
        target_comment_id = parent_comment_id if parent_comment_id else comment_id
        
        # Count parent comments before this one
        count_query = adapt_query("""
            SELECT COUNT(*) FROM comments 
            WHERE post_id = ? AND parent_comment_id IS NULL AND comment_id < ?
            ORDER BY timestamp ASC
        """)
        comments_before = execute_query(count_query, (post_id, target_comment_id), fetch='one')[0]
        page = (comments_before // COMMENTS_PER_PAGE) + 1
        
        return {
            'page': page,
            'post_id': post_id,
            'comment_id': target_comment_id
        }
    except Exception as e:
        logger.error(f"Error finding comment page: {e}")
        return None


# Format replies to look like Telegram's native reply feature
def format_reply(parent_text, child_text, parent_author="Anonymous"):
    """Format reply messages to look like Telegram's native reply feature with blockquote"""
    # Truncate parent text if too long for better display
    if len(parent_text) > 150:
        parent_text = parent_text[:150] + "..."
    
    # Use Telegram's native blockquote styling
    return f"<blockquote expandable>{parent_text}</blockquote>\n\n{child_text}"


async def update_channel_message_comment_count(context, post_id):
    """Update the comment count on the channel message"""
    try:
        # Get post info using database abstraction
        post_query = adapt_query("SELECT post_id, content, category, channel_message_id, approved, post_number FROM posts WHERE post_id = ?")
        post_info = execute_query(post_query, (post_id,), fetch='one')

        if not post_info or not post_info[3]:
            return False, "No channel message found"

        post_id, content, category, channel_message_id, approved, post_number = post_info

        if approved != 1:
            return False, "Post not approved"

        # Use the properly working get_comment_count function
        comment_count = get_comment_count(post_id)

        bot_username_clean = BOT_USERNAME.lstrip('@')
        keyboard = [
            [
                InlineKeyboardButton(
                    "💬 Add Comment",
                    url=f"https://t.me/{bot_username_clean}?start=comment_{post_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    f"👀 See Comments ({comment_count})",
                    url=f"https://t.me/{bot_username_clean}?start=view_{post_id}"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        categories_text = " ".join(
            [f"#{cat.strip().replace(' ', '')}" for cat in category.split(",")]
        )

        if is_media_post(post_id):
            media_info = get_media_info(post_id)
            if media_info:
                caption_text = f"<b>Confess # {post_number}</b>"

                if content and content.strip():
                    caption_text += f"\n\n{content}"

                if media_info.get('caption') and media_info['caption'] != content:
                    caption_text += f"\n\n{media_info['caption']}"

                caption_text += f"\n\n{categories_text}"

                await context.bot.edit_message_caption(
                    chat_id=CHANNEL_ID,
                    message_id=channel_message_id,
                    caption=caption_text,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=CHANNEL_ID,
                    message_id=channel_message_id,
                    text=f"<b>Confess # {post_number}</b>\n\n{content}\n\n{categories_text}",
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
        else:
            await context.bot.edit_message_text(
                chat_id=CHANNEL_ID,
                message_id=channel_message_id,
                text=f"<b>Confess # {post_number}</b>\n\n{content}\n\n{categories_text}",
                parse_mode="HTML",
                reply_markup=reply_markup
            )

        return True, f"Updated comment count to {comment_count}"

    except Exception as e:
        logger.error(f"Error updating channel message: {e}")
        return False, f"Failed to update channel message: {str(e)}"
