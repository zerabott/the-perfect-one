#!/usr/bin/env python3
"""
Enhanced Ranking UI with Better Progress Visualization and User Experience
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from typing import List, Dict, Optional
import math
from datetime import datetime, timedelta

from enhanced_ranking_system import EnhancedPointSystem, EnhancedAchievementSystem
from enhanced_leaderboard import EnhancedLeaderboardManager, LeaderboardType
from enhanced_ranking_system import UserRank
from ranking_integration import ranking_manager
from utils import escape_markdown_text
from logger import get_logger

logger = get_logger('enhanced_ranking_ui')

def format_number_for_markdown(value: float, decimal_places: int = 1) -> str:
    """Format a number for MarkdownV2 display, escaping decimal points"""
    if decimal_places == 0:
        formatted = f"{value:.0f}"
    else:
        formatted = f"{value:.{decimal_places}f}"
    
    # Escape decimal points for MarkdownV2
    return formatted.replace('.', '\.')  

class EnhancedRankingUI:
    """Enhanced UI components with better visualizations"""
    
    @staticmethod
    def create_advanced_progress_bar(current: int, maximum: int, length: int = 15) -> str:
        """Create an advanced progress bar with realistic loading appearance"""
        if maximum == 0:
            return "█" * length + " 100% MAXED!"
        
        # Ensure we don't have negative values
        current = max(0, current)
        progress = min(current / maximum, 1.0) if maximum > 0 else 0
        filled = int(progress * length)
        empty = length - filled
        
        # Use realistic loading bar characters
        fill_char = "█"  # Solid block
        empty_char = "░"  # Light shade
        
        bar = fill_char * filled + empty_char * empty
        percentage = f"{int(progress * 100)}%"
        
        return f"{bar} {percentage}"
    
    @staticmethod
    def create_streak_visualization(streak_days: int) -> str:
        """Create visual representation of streak"""
        if streak_days == 0:
            return "📅 No streak yet - start your journey!"
        elif streak_days < 7:
            return f"🔥 {streak_days} day streak - keep it up!"
        elif streak_days < 30:
            return f"⚡ {streak_days} day streak - you're on fire!"
        elif streak_days < 90:
            return f"🚀 {streak_days} day streak - amazing dedication!"
        elif streak_days < 365:
            return f"👑 {streak_days} day streak - you're a legend!"
        else:
            return f"🌟 {streak_days} day streak - ULTIMATE DEVOTEE!"
    
    @staticmethod
    def format_enhanced_rank_display(user_rank: UserRank, user_id: int) -> str:
        """Enhanced rank display with more visual elements"""
        # Calculate progress to next rank with debugging info
        if user_rank.points_to_next > 0:
            # Direct approach: calculate what percentage of the way we are to next rank
            # If next_rank_points = 1000 and points_to_next = 200, then we're at 800/1000 = 80%
            current_points_in_rank = user_rank.next_rank_points - user_rank.points_to_next
            progress_percentage = int((current_points_in_rank / user_rank.next_rank_points) * 100)
            
            # Ensure percentage is within valid range
            progress_percentage = max(0, min(100, progress_percentage))
            
            # Create the visual progress bar
            filled_blocks = int((progress_percentage / 100) * 12)
            empty_blocks = 12 - filled_blocks
            progress_bar = f"{'█' * filled_blocks}{'░' * empty_blocks} {progress_percentage}%"
            
            next_rank_text = f"Next: {user_rank.points_to_next:,} points to go"
            
        else:
            progress_bar = "████████████ 100% MAXED!"
            next_rank_text = "🎉 Maximum rank achieved!"
        
        # Get streak visualization
        from db_connection import get_db_connection
        db_conn = get_db_connection()
        with db_conn.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT consecutive_days FROM user_rankings WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            streak_days = result[0] if result else 0
        
        streak_viz = EnhancedRankingUI.create_streak_visualization(streak_days)
        
        # Special rank indicator
        rank_indicator = "⭐ SPECIAL RANK" if user_rank.is_special_rank else "📊 Standard Rank"
        
        rank_text = f"""
 🏆 *YOUR RANKING STATUS*

 {escape_markdown_text(user_rank.rank_emoji)} **{escape_markdown_text(user_rank.rank_name)}** {escape_markdown_text('(' + rank_indicator + ')')}
 💎 **{user_rank.total_points:,} Total Points**

 📈 *Progress to Next Rank*
 {progress_bar}
 {escape_markdown_text(next_rank_text)}

 {escape_markdown_text(streak_viz)}

 🎯 **{user_rank.total_points:,}** total points earned
 🏅 **{ranking_manager.get_user_achievements(user_id).__len__()}** achievements unlocked
 """
        
        return rank_text


async def show_enhanced_ranking_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the enhanced ranking menu"""
    try:
        user_id = update.effective_user.id
        user_rank = ranking_manager.get_user_rank(user_id)
        
        if not user_rank:
            # Initialize user ranking if it doesn't exist
            ranking_manager.initialize_user_ranking(user_id)
            user_rank = ranking_manager.get_user_rank(user_id)
        
        if not user_rank:
            await update.callback_query.answer("❌ Unable to load your ranking data. Please try again later.")
            return
        
        # Create ranking display
        rank_display = EnhancedRankingUI.format_enhanced_rank_display(user_rank, user_id)
        
        # Create keyboard with options
        keyboard = [
            [InlineKeyboardButton("🪜 Rank Ladder", callback_data="rank_ladder")],
            [InlineKeyboardButton("📖 Point Guide", callback_data="rank_point_guide")],
            [InlineKeyboardButton("🎖️ My Achievement", callback_data="achievement_view_my")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=rank_display,
                reply_markup=reply_markup,
                parse_mode='MarkdownV2'
            )
        else:
            await update.message.reply_text(
                text=rank_display,
                reply_markup=reply_markup,
                parse_mode='MarkdownV2'
            )
            
    except Exception as e:
        logger.error(f"Error showing enhanced ranking menu: {e}")
        error_message = "❌ Sorry, there was an error displaying your ranking information."
        if update.callback_query:
            await update.callback_query.answer(error_message)
        else:
            await update.message.reply_text(error_message)


async def enhanced_ranking_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle enhanced ranking callback queries"""
    query = update.callback_query
    await query.answer()
    
    try:
        data = query.data
        user_id = update.effective_user.id
        
        if data == "enhanced_ranking":
            await show_enhanced_ranking_menu(update, context)
            
            
        elif data == "achievement_view_my":
            achievements = ranking_manager.get_user_achievements(user_id)
            
            if not achievements:
                achievement_text = "🎖️ *YOUR ACHIEVEMENTS*\n\n❌ No achievements unlocked yet\!"
            else:
                achievement_text = "🎖️ *YOUR ACHIEVEMENTS*\n\n"
                for achievement in achievements[:10]:  # Show first 10
                    special_indicator = "⭐" if achievement.get('is_special') else "🏅"
                    achievement_text += f"{special_indicator} *{escape_markdown_text(achievement.get('name', 'Unknown'))}*\n"
                    achievement_text += f"   {escape_markdown_text(achievement.get('description', 'No description'))}\n"
                    achievement_text += f"   \+{achievement.get('points', 0)} points\n\n"
            
            keyboard = [
                [InlineKeyboardButton("🔙 Back", callback_data="enhanced_ranking")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=achievement_text,
                reply_markup=reply_markup,
                parse_mode='MarkdownV2'
            )
            
        elif data == "rank_ladder":
            # Show the rank ladder
            from rank_ladder import show_rank_ladder
            await show_rank_ladder(update, context)
            
        elif data == "rank_point_guide":
            # Show point system guide
            await show_point_guide(update, context)
            
        
        else:
            # Handle other ranking-related callbacks
            await query.answer("Feature coming soon!")
            
    except Exception as e:
        logger.error(f"Error in enhanced_ranking_callback_handler: {e}")
        await query.answer("❌ An error occurred. Please try again.")


async def show_point_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the point system guide explaining how points are earned"""
    try:
        from enhanced_ranking_system import EnhancedPointSystem
        
        guide_text = "📖 *POINT SYSTEM GUIDE*\n\n"
        guide_text += escape_markdown_text("Learn how to earn points and climb the ranking system!") + "\n\n"
        
        # Confession activities
        guide_text += "🙊 *Confession Activities:*\n"
        guide_text += escape_markdown_text("• Approved Confession: +50 points") + "\n"
        guide_text += escape_markdown_text("• Featured Confession: +75 points") + "\n"
        guide_text += escape_markdown_text("• Viral Confession (200+ likes): +200 points") + "\n"
        guide_text += escape_markdown_text("• Popular Post (trending): +125 points") + "\n\n"
        
        # Comment activities
        guide_text += "💬 *Comment Activities:*\n"
        guide_text += escape_markdown_text("• Post Comment: +8 points") + "\n"
        guide_text += escape_markdown_text("• Comment Gets Liked: +2 points per like") + "\n"
        guide_text += escape_markdown_text("• Viral Comment (50+ likes): +50 points") + "\n"
        guide_text += escape_markdown_text("• Quality Comment (admin marked): +30 points") + "\n\n"
        
        # Daily activities
        guide_text += "📅 *Daily Activities:*\n"
        guide_text += escape_markdown_text("• Daily Login: +5 points") + "\n"
        guide_text += escape_markdown_text("• Week Streak: +50 points") + "\n"
        guide_text += escape_markdown_text("• Month Streak: +200 points") + "\n"
        guide_text += escape_markdown_text("• Year Streak: +1000 points") + "\n\n"
        
        # Special bonuses
        guide_text += "⭐ *Special Bonuses:*\n"
        guide_text += escape_markdown_text("• First Confession: +75 points") + "\n"
        guide_text += escape_markdown_text("• High Quality Content: +40 points") + "\n"
        guide_text += escape_markdown_text("• Community Help: +25 points") + "\n"
        guide_text += escape_markdown_text("• Weekend Activity: +10% bonus") + "\n\n"
        
        # Penalties
        guide_text += "⚠️ *Penalties:*\n"
        guide_text += escape_markdown_text("• Content Rejected: -3 points") + "\n"
        guide_text += escape_markdown_text("• Spam Detected: -10 points") + "\n"
        guide_text += escape_markdown_text("• Inappropriate Content: -20 points") + "\n\n"
        
        guide_text += "💡 *Tips:*\n"
        guide_text += escape_markdown_text("• Longer posts (500+ chars) get bonus points") + "\n"
        guide_text += escape_markdown_text("• Consistency pays off with streak multipliers") + "\n"
        guide_text += escape_markdown_text("• Quality content gets admin bonuses") + "\n"
        guide_text += escape_markdown_text("• Engaging with others earns reaction points") + "\n\n"
        
        guide_text += "🚀 *" + escape_markdown_text("Stay active and create quality content to maximize your points!") + "*"
        
        # Create keyboard with back button
        keyboard = [
            [
                InlineKeyboardButton("🔙 Back to Rank Menu", callback_data="enhanced_ranking")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                guide_text,
                parse_mode="MarkdownV2",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                guide_text,
                parse_mode="MarkdownV2",
                reply_markup=reply_markup
            )
                
    except Exception as e:
        logger.error(f"Error in show_point_guide: {e}")
        error_message = "❌ Sorry, there was an error displaying the point guide."
        if update.callback_query:
            await update.callback_query.answer(error_message)
        else:
            await update.message.reply_text(error_message)
