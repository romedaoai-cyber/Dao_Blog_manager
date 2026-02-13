#!/usr/bin/env python3
"""
Blog Analytics
Fetches blog performance data from HubSpot Analytics API.
Tracks views, bounce rates, engagement over time.
"""

import os
import sys
import json
import logging
import requests
from pathlib import Path
from datetime import datetime, timedelta

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

MODULE_DIR = Path(__file__).parent
CONFIG_FILE = MODULE_DIR / "blog_config.json"
ANALYTICS_DIR = MODULE_DIR / "analytics_data"
ANALYTICS_DIR.mkdir(exist_ok=True)
LATEST_ANALYTICS = ANALYTICS_DIR / "latest_analytics.json"
ANALYTICS_HISTORY = ANALYTICS_DIR / "analytics_history.json"

HUBSPOT_API_BASE = "https://api.hubapi.com"

logger = logging.getLogger("blog_analytics")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def load_access_key():
    """Load HubSpot access key."""
    from hubspot_blog_client import load_access_key as _load
    return _load()


def get_headers(access_key=None):
    if not access_key:
        access_key = load_access_key()
    return {
        "Authorization": f"Bearer {access_key}",
        "Content-Type": "application/json",
    }


# ──────────────────────────────────────────────
# Blog Post Performance
# ──────────────────────────────────────────────

def fetch_blog_performance(days=30):
    """
    Fetch performance data for all blog posts.

    Uses HubSpot CMS Performance API and Analytics API.
    Returns list of posts with their metrics.
    """
    access_key = load_access_key()
    if not access_key:
        return []

    headers = get_headers(access_key)

    # Step 1: Get all published posts
    posts = _get_published_posts(headers)
    if not posts:
        logger.warning("No published posts found")
        return []

    # Step 2: Get analytics for each post
    analytics_data = []
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    for post in posts:
        post_id = post.get("id")
        title = post.get("name", "Untitled")
        slug = post.get("slug", "")
        url = post.get("url", "")
        published_date = post.get("publishDate", "")

        # Fetch page-level analytics
        metrics = _fetch_page_analytics(post_id, slug, url, headers, start_date, end_date)

        post_data = {
            "id": post_id,
            "title": title,
            "slug": slug,
            "url": url,
            "published_date": published_date,
            "views": metrics.get("views", 0),
            "unique_views": metrics.get("unique_views", 0),
            "bounce_rate": metrics.get("bounce_rate", 0),
            "avg_time_on_page": metrics.get("avg_time_on_page", 0),
            "exits": metrics.get("exits", 0),
            "entrances": metrics.get("entrances", 0),
            "cta_clicks": metrics.get("cta_clicks", 0),
            "fetched_at": datetime.now().isoformat(),
            "period_days": days,
        }
        analytics_data.append(post_data)

    # Sort by views descending
    analytics_data.sort(key=lambda x: x.get("views", 0), reverse=True)

    # Save snapshot
    _save_snapshot(analytics_data)

    return analytics_data


def _get_published_posts(headers, limit=100):
    """Get all published blog posts."""
    url = f"{HUBSPOT_API_BASE}/cms/v3/blogs/posts"
    params = {"limit": limit, "state": "PUBLISHED", "sort": "-publishDate"}

    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code == 200:
        posts = resp.json().get("results", [])
        logger.info(f"📝 Found {len(posts)} published posts")
        return posts
    else:
        logger.error(f"❌ Failed to list posts: {resp.status_code}")
        return []


def _fetch_page_analytics(post_id, slug, url, headers, start_date, end_date):
    """Fetch analytics for a single page using HubSpot web analytics."""
    # Try the content performance endpoint
    analytics_url = f"{HUBSPOT_API_BASE}/analytics/v2/reports/content/totals"
    params = {
        "start": start_date.strftime("%Y%m%d"),
        "end": end_date.strftime("%Y%m%d"),
        "d1": "blog-posts",
        "f": post_id,
    }

    try:
        resp = requests.get(analytics_url, headers=headers, params=params)
        if resp.status_code == 200:
            data = resp.json()
            # Parse HubSpot analytics response
            totals = data.get("totals", {})
            return {
                "views": totals.get("rawViews", 0),
                "unique_views": totals.get("visits", 0),
                "bounce_rate": totals.get("bounceRate", 0),
                "avg_time_on_page": totals.get("avgPageViewsPerSession", 0),
                "exits": totals.get("exits", 0),
                "entrances": totals.get("entrances", 0),
                "cta_clicks": totals.get("ctaClicks", 0),
            }
    except Exception as e:
        logger.debug(f"Analytics fetch failed for {post_id}: {e}")

    # Fallback: try blog-specific endpoint
    try:
        blog_analytics_url = f"{HUBSPOT_API_BASE}/analytics/v2/reports/blog-posts/total"
        params2 = {
            "start": start_date.strftime("%Y%m%d"),
            "end": end_date.strftime("%Y%m%d"),
            "f": post_id,
        }
        resp2 = requests.get(blog_analytics_url, headers=headers, params=params2)
        if resp2.status_code == 200:
            data2 = resp2.json()
            totals2 = data2.get("totals", {})
            return {
                "views": totals2.get("rawViews", 0),
                "unique_views": totals2.get("visits", 0),
                "bounce_rate": totals2.get("bounceRate", 0),
                "avg_time_on_page": totals2.get("avgPageViewsPerSession", 0),
                "exits": 0,
                "entrances": 0,
                "cta_clicks": 0,
            }
    except Exception as e:
        logger.debug(f"Blog analytics fallback also failed: {e}")

    return {
        "views": 0, "unique_views": 0, "bounce_rate": 0,
        "avg_time_on_page": 0, "exits": 0, "entrances": 0, "cta_clicks": 0
    }


# ──────────────────────────────────────────────
# Top / Underperforming Analysis
# ──────────────────────────────────────────────

def get_top_posts(analytics_data=None, n=10):
    """Get top N performing posts by views."""
    if analytics_data is None:
        analytics_data = _load_latest()
    return analytics_data[:n]


def get_underperforming(analytics_data=None, threshold=None):
    """Get posts below the view threshold."""
    config = load_config()
    if threshold is None:
        threshold = config.get("analytics", {}).get("min_views_threshold", 100)

    if analytics_data is None:
        analytics_data = _load_latest()

    return [p for p in analytics_data if p.get("views", 0) < threshold]


def get_performance_summary(analytics_data=None):
    """Get a high-level performance summary for the feedback loop."""
    if analytics_data is None:
        analytics_data = _load_latest()

    if not analytics_data:
        return {
            "total_posts": 0,
            "total_views": 0,
            "avg_views": 0,
            "top_performing_topics": [],
            "underperforming_topics": [],
            "trends": "No data available yet."
        }

    total_views = sum(p.get("views", 0) for p in analytics_data)
    avg_views = total_views / len(analytics_data) if analytics_data else 0

    top_posts = analytics_data[:5]
    bottom_posts = analytics_data[-3:] if len(analytics_data) >= 3 else []

    return {
        "total_posts": len(analytics_data),
        "total_views": total_views,
        "avg_views": round(avg_views, 1),
        "top_performing_topics": [
            {"title": p["title"], "views": p.get("views", 0), "slug": p.get("slug", "")}
            for p in top_posts
        ],
        "underperforming_topics": [
            {"title": p["title"], "views": p.get("views", 0)}
            for p in bottom_posts
        ],
        "trends": _detect_trends(analytics_data),
    }


def _detect_trends(analytics_data):
    """Simple trend detection from analytics data."""
    if len(analytics_data) < 3:
        return "Not enough data for trend analysis."

    # Extract keywords from top vs bottom performers
    top_titles = " ".join(p["title"].lower() for p in analytics_data[:3])
    bottom_titles = " ".join(p["title"].lower() for p in analytics_data[-3:])

    keyword_hints = []
    tech_keywords = ["ai", "automation", "inspection", "quality", "manufacturing",
                     "pcba", "smt", "aoi", "defect", "machine learning", "industry 4.0"]

    for kw in tech_keywords:
        if kw in top_titles and kw not in bottom_titles:
            keyword_hints.append(f"'{kw}' appears in top-performing posts")

    if keyword_hints:
        return "Trend signals: " + "; ".join(keyword_hints)
    return "No strong topic trends detected yet. More data needed."


# ──────────────────────────────────────────────
# Data Persistence
# ──────────────────────────────────────────────

def _save_snapshot(analytics_data):
    """Save analytics snapshot."""
    # Latest
    with open(LATEST_ANALYTICS, "w", encoding="utf-8") as f:
        json.dump(analytics_data, f, indent=2, ensure_ascii=False)
    logger.info(f"💾 Saved analytics snapshot ({len(analytics_data)} posts)")

    # History (append)
    history = _load_history()
    history.append({
        "timestamp": datetime.now().isoformat(),
        "post_count": len(analytics_data),
        "total_views": sum(p.get("views", 0) for p in analytics_data),
        "top_post": analytics_data[0]["title"] if analytics_data else "N/A",
    })
    # Keep last 90 entries
    if len(history) > 90:
        history = history[-90:]
    with open(ANALYTICS_HISTORY, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def _load_latest():
    """Load latest analytics data."""
    if LATEST_ANALYTICS.exists():
        try:
            with open(LATEST_ANALYTICS, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            return []
    return []


def _load_history():
    """Load analytics history."""
    if ANALYTICS_HISTORY.exists():
        try:
            with open(ANALYTICS_HISTORY, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            return []
    return []


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("""
Blog Analytics

Usage:
    python blog_analytics.py fetch [days]       # Fetch analytics (default: 30 days)
    python blog_analytics.py top [n]            # Show top N posts
    python blog_analytics.py underperforming    # Show underperforming posts
    python blog_analytics.py summary            # Performance summary
    python blog_analytics.py --test             # Test analytics connection
""")
        return

    cmd = sys.argv[1]

    if cmd == "fetch":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        print(f"📊 Fetching blog analytics (last {days} days)...\n")
        data = fetch_blog_performance(days=days)
        if data:
            print(f"\n{'Title':<50} {'Views':<10} {'Unique':<10} {'Bounce':<10}")
            print("─" * 85)
            for p in data:
                print(f"{p['title'][:50]:<50} {p['views']:<10} {p['unique_views']:<10} {p['bounce_rate']:<10}")
            print(f"\n✅ Data saved to {LATEST_ANALYTICS}")

    elif cmd == "top":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        top = get_top_posts(n=n)
        if top:
            print(f"\n🏆 Top {n} Posts:\n")
            for i, p in enumerate(top, 1):
                print(f"  {i}. {p['title'][:60]} — {p.get('views', 0)} views")
        else:
            print("No analytics data. Run 'fetch' first.")

    elif cmd == "underperforming":
        under = get_underperforming()
        if under:
            print(f"\n⚠️ Underperforming Posts ({len(under)}):\n")
            for p in under:
                print(f"  • {p['title'][:60]} — {p.get('views', 0)} views")
        else:
            print("No underperforming posts (or no data).")

    elif cmd == "summary":
        summary = get_performance_summary()
        print(f"\n📊 Blog Performance Summary:")
        print(f"   Total posts: {summary['total_posts']}")
        print(f"   Total views: {summary['total_views']}")
        print(f"   Avg views/post: {summary['avg_views']}")
        print(f"   Trends: {summary['trends']}")
        if summary['top_performing_topics']:
            print(f"\n   🏆 Top Posts:")
            for t in summary['top_performing_topics']:
                print(f"      • {t['title'][:50]} — {t['views']} views")

    elif cmd == "--test":
        print("🔍 Testing analytics API connection...")
        access_key = load_access_key()
        if access_key:
            headers = get_headers(access_key)
            # Try a simple request
            url = f"{HUBSPOT_API_BASE}/cms/v3/blogs/posts"
            resp = requests.get(url, headers=headers, params={"limit": 1})
            if resp.status_code == 200:
                print("✅ Analytics API connection OK")
            else:
                print(f"❌ API returned {resp.status_code}")
        else:
            print("❌ No access key")

    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
