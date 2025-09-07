#!/usr/bin/env python3
"""
Cache Management Utility for Iota Bot
"""

import argparse
import json
from datetime import datetime
from cache import response_cache
from logging_config import logger

def show_cache_stats():
    """Display current cache statistics"""
    stats = response_cache.get_stats()
    
    print("📊 Cache Statistics")
    print("=" * 40)
    print(f"Total Entries: {stats['total_entries']}")
    print(f"Cache Hits: {stats['cache_hits']}")
    print(f"Cache Misses: {stats['cache_misses']}")
    print(f"Hit Rate: {stats['hit_rate']:.1%}")
    
    # Calculate efficiency
    if stats['hit_rate'] > 0.7:
        efficiency = "🟢 Excellent"
    elif stats['hit_rate'] > 0.4:
        efficiency = "🟡 Good"
    else:
        efficiency = "🔴 Poor"
    
    print(f"Efficiency: {efficiency}")

def clear_cache():
    """Clear all cached responses"""
    print("🗑️ Clearing cache...")
    response_cache.clear_cache()
    print("✅ Cache cleared successfully!")

def export_stats(filename=None):
    """Export cache statistics to JSON file"""
    if not filename:
        filename = f"cache_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    print(f"📊 Exporting cache statistics to {filename}...")
    response_cache.export_cache_stats(filename)
    print(f"✅ Statistics exported to {filename}")

def show_cache_info():
    """Show detailed cache information"""
    stats = response_cache.get_stats()
    
    print("🔍 Detailed Cache Information")
    print("=" * 40)
    
    # Basic stats
    show_cache_stats()
    
    print("\n📈 Performance Analysis")
    print("-" * 30)
    
    total_requests = stats['cache_hits'] + stats['cache_misses']
    if total_requests > 0:
        api_calls_saved = stats['cache_hits']
        efficiency_percent = (api_calls_saved / total_requests) * 100
        print(f"API Calls Saved: {api_calls_saved}")
        print(f"Efficiency: {efficiency_percent:.1f}%")
        
        if efficiency_percent > 70:
            print("🎯 Cache is performing excellently!")
        elif efficiency_percent > 40:
            print("👍 Cache is performing well")
        else:
            print("⚠️  Cache performance could be improved")
    else:
        print("No requests yet - start using the bot to see statistics!")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Iota Bot Cache Manager")
    parser.add_argument("--stats", action="store_true", help="Show cache statistics")
    parser.add_argument("--clear", action="store_true", help="Clear all cached responses")
    parser.add_argument("--export", metavar="FILENAME", help="Export cache statistics to file")
    parser.add_argument("--info", action="store_true", help="Show detailed cache information")
    
    args = parser.parse_args()
    
    if not any([args.stats, args.clear, args.export, args.info]):
        # Default: show stats
        show_cache_stats()
        return
    
    if args.stats:
        show_cache_stats()
    
    if args.clear:
        clear_cache()
    
    if args.export:
        export_stats(args.export)
    
    if args.info:
        show_cache_info()

if __name__ == "__main__":
    main()
