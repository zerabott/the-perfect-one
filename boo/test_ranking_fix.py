#!/usr/bin/env python3
"""
Test script to verify the ranking system fixes
"""

import sys
import os
sys.path.append('.')

def test_imports():
    """Test if all required modules can be imported"""
    try:
        from enhanced_ranking_ui import show_enhanced_ranking_menu, enhanced_ranking_callback_handler, show_point_guide
        print("✅ Enhanced ranking UI imports - OK")
        
        from rank_ladder import show_rank_ladder, RankLadderDisplay
        print("✅ Rank ladder imports - OK")
        
        from enhanced_ranking_system import EnhancedPointSystem
        print("✅ Enhanced ranking system imports - OK")
        
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_menu_structure():
    """Test if the menu buttons are correctly configured"""
    try:
        from enhanced_ranking_ui import show_enhanced_ranking_menu
        import inspect
        
        # Get the source code to check button configuration
        source = inspect.getsource(show_enhanced_ranking_menu)
        
        expected_buttons = [
            "🪜 Rank Ladder",
            "📖 Point Guide", 
            "🎖️ My Achievement",
            "📊 Detail Stats",
            "🏠 Main Menu"
        ]
        
        for button in expected_buttons:
            if button in source:
                print(f"✅ Found button: {button}")
            else:
                print(f"❌ Missing button: {button}")
                return False
        
        # Check callback data
        expected_callbacks = [
            "rank_ladder",
            "rank_point_guide",
            "achievement_view_my",
            "ranking_detailed_stats",
            "menu"
        ]
        
        for callback in expected_callbacks:
            if callback in source:
                print(f"✅ Found callback: {callback}")
            else:
                print(f"❌ Missing callback: {callback}")
                return False
        
        return True
    except Exception as e:
        print(f"❌ Menu structure test error: {e}")
        return False

def test_callback_handlers():
    """Test if callback handlers are properly configured"""
    try:
        from enhanced_ranking_ui import enhanced_ranking_callback_handler
        import inspect
        
        source = inspect.getsource(enhanced_ranking_callback_handler)
        
        expected_handlers = [
            "rank_ladder",
            "rank_point_guide",
            "achievement_view_my",
            "ranking_detailed_stats"
        ]
        
        for handler in expected_handlers:
            if f'data == "{handler}"' in source or f'data.startswith("{handler}")' in source:
                print(f"✅ Found handler for: {handler}")
            else:
                print(f"❌ Missing handler for: {handler}")
                return False
        
        return True
    except Exception as e:
        print(f"❌ Callback handler test error: {e}")
        return False

def test_point_guide():
    """Test if the point guide function is properly implemented"""
    try:
        from enhanced_ranking_ui import show_point_guide
        import inspect
        
        source = inspect.getsource(show_point_guide)
        
        # Check for essential content
        essential_content = [
            "Confession Activities",
            "Comment Activities", 
            "Daily Activities",
            "Special Bonuses",
            "Penalties",
            "Tips"
        ]
        
        for content in essential_content:
            if content in source:
                print(f"✅ Point guide contains: {content}")
            else:
                print(f"❌ Point guide missing: {content}")
                return False
        
        return True
    except Exception as e:
        print(f"❌ Point guide test error: {e}")
        return False

def test_rank_ladder():
    """Test if the rank ladder function is properly implemented"""
    try:
        from rank_ladder import show_rank_ladder
        import inspect
        
        source = inspect.getsource(show_rank_ladder)
        
        # Check for correct callback
        if 'enhanced_ranking' in source:
            print("✅ Rank ladder has correct back button callback")
        else:
            print("❌ Rank ladder has incorrect back button callback")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Rank ladder test error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing Ranking System Fixes")
    print("=" * 40)
    
    tests = [
        ("Import Test", test_imports),
        ("Menu Structure Test", test_menu_structure),
        ("Callback Handler Test", test_callback_handlers),
        ("Point Guide Test", test_point_guide),
        ("Rank Ladder Test", test_rank_ladder)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name}...")
        if test_func():
            print(f"✅ {test_name} - PASSED")
            passed += 1
        else:
            print(f"❌ {test_name} - FAILED")
    
    print(f"\n" + "=" * 40)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The ranking system should be working correctly.")
        return True
    else:
        print("⚠️ Some tests failed. Please check the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
