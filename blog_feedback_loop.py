#!/usr/bin/env python3
"""
Blog Feedback Loop
The intelligent core: analyzes blog performance data, identifies what works,
and automatically generates new content ideas based on data-driven insights.
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

MODULE_DIR = Path(__file__).parent
CONFIG_FILE = MODULE_DIR / "blog_config.json"
LINEAGE_FILE = MODULE_DIR / "topic_lineage.json"
ITERATION_LOG = MODULE_DIR / "iteration_log.json"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBqQF9-ivsvkAjbGhb-OIvDv6dbtBmK38M")

logger = logging.getLogger("blog_feedback")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def init_gemini():
    if not GEMINI_AVAILABLE:
        logger.error("❌ google-generativeai not installed")
        return None
    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel("gemini-2.5-flash")


# ──────────────────────────────────────────────
# Performance Analysis
# ──────────────────────────────────────────────

def analyze_performance_trends(analytics_data):
    """
    Use AI to deeply analyze blog performance and extract actionable insights.

    Args:
        analytics_data: List of post analytics dicts

    Returns:
        Dict with insights, patterns, and recommendations
    """
    model = init_gemini()
    if not model:
        return {"error": "Gemini not available"}

    # Prepare data summary for the AI
    posts_summary = []
    for p in analytics_data:
        posts_summary.append({
            "title": p.get("title", ""),
            "views": p.get("views", 0),
            "unique_views": p.get("unique_views", 0),
            "bounce_rate": p.get("bounce_rate", 0),
            "avg_time_on_page": p.get("avg_time_on_page", 0),
            "published_date": p.get("published_date", ""),
        })

    prompt = f"""You are a content analytics expert. Analyze this blog performance data for a B2B manufacturing tech company (AI-powered optical inspection for PCBA).

BLOG PERFORMANCE DATA:
{json.dumps(posts_summary, indent=2)}

Provide a comprehensive analysis. Return ONLY valid JSON:
{{
    "overall_health": "good/average/poor",
    "total_views": 0,
    "avg_views_per_post": 0,
    "top_performing_themes": ["theme1", "theme2"],
    "underperforming_themes": ["theme1", "theme2"],
    "content_format_insights": "What formats/structures perform best",
    "audience_interests": ["interest1", "interest2"],
    "keyword_opportunities": ["keyword1", "keyword2"],
    "posting_frequency_recommendation": "Increase/maintain/adjust",
    "specific_recommendations": [
        "recommendation 1",
        "recommendation 2",
        "recommendation 3"
    ],
    "content_gaps": ["gap1", "gap2"],
    "predicted_high_value_topics": ["topic1", "topic2", "topic3"]
}}
"""

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=4096,
                temperature=0.4,  # Lower temp for analysis
            )
        )

        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        insights = json.loads(text)
        logger.info(f"✅ Performance analysis complete. Health: {insights.get('overall_health', '?')}")
        return insights

    except Exception as e:
        logger.error(f"❌ Performance analysis failed: {e}")
        return {"error": str(e)}


def suggest_next_topics(analytics_data, count=5):
    """
    Generate next batch of topic ideas based on performance data.

    This is the core of the feedback loop: data → insights → new topics.
    """
    model = init_gemini()
    if not model:
        return []

    config = load_config()

    # Get existing topic lineage to avoid repetition
    lineage = _load_lineage()
    existing_titles = [entry.get("title", "") for entry in lineage]

    # Get performance summary
    from blog_analytics import get_performance_summary
    summary = get_performance_summary(analytics_data)

    prompt = f"""You are a data-driven content strategist for a B2B AI tech company in manufacturing.

COMPANY CONTEXT:
{config.get('company_context', 'AI visual inspection for PCBA manufacturing')}

PERFORMANCE DATA:
- Total posts: {summary.get('total_posts', 0)}
- Average views/post: {summary.get('avg_views', 0)}
- Top performing: {json.dumps(summary.get('top_performing_topics', []), indent=2)}
- Underperforming: {json.dumps(summary.get('underperforming_topics', []), indent=2)}
- Trends: {summary.get('trends', 'N/A')}

ALREADY COVERED TOPICS (do NOT repeat):
{json.dumps(existing_titles[-20:], indent=2)}

CONTENT PILLARS:
{json.dumps(config.get('content_pillars', []), indent=2)}

TARGET AUDIENCE:
{json.dumps(config.get('target_audience', []), indent=2)}

INSTRUCTIONS:
1. Analyze what topics/formats performed well
2. Generate {count} NEW topic ideas that build on successful patterns
3. Each topic should explore a fresh angle, not repeat existing content
4. Prioritize topics likely to get high engagement based on the data
5. Mix evergreen content with timely/trending topics

Return ONLY valid JSON array:
[{{
    "title": "Blog post title",
    "description": "2-3 sentence brief",
    "keywords": ["kw1", "kw2", "kw3"],
    "target_audience": "primary reader",
    "content_pillar": "which pillar",
    "inspired_by": "which top post inspired this (or 'original')",
    "expected_performance": "high/medium",
    "rationale": "why this topic should perform well based on data"
}}]
"""

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=4096,
                temperature=0.8,
            )
        )

        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        topics = json.loads(text)
        logger.info(f"✅ Generated {len(topics)} data-driven topic ideas")

        # Save to lineage
        for topic in topics:
            _add_to_lineage(topic)

        return topics

    except Exception as e:
        logger.error(f"❌ Topic suggestion failed: {e}")
        return []


# ──────────────────────────────────────────────
# Full Iteration Cycle
# ──────────────────────────────────────────────

def auto_iterate(write_posts=False, count=3):
    """
    Full feedback loop iteration:
    1. Fetch latest analytics
    2. Analyze performance
    3. Generate new topics
    4. (Optional) Write new blog posts

    Args:
        write_posts: If True, also write the blog posts
        count: Number of new topics to generate

    Returns:
        Dict with iteration results
    """
    logger.info("🔄 Starting feedback loop iteration...\n")

    # Step 1: Fetch analytics
    logger.info("📊 Step 1: Fetching analytics...")
    from blog_analytics import fetch_blog_performance
    analytics_data = fetch_blog_performance(days=30)

    if not analytics_data:
        logger.warning("⚠️ No analytics data. Generating fresh topics without data.")
        from blog_content_generator import generate_topic_ideas
        topics = generate_topic_ideas(count=count)
        result = {
            "iteration": "fresh_start",
            "timestamp": datetime.now().isoformat(),
            "analytics_count": 0,
            "topics_generated": len(topics),
            "topics": topics,
            "posts_written": 0,
        }
        _log_iteration(result)
        return result

    # Step 2: Analyze performance
    logger.info("🧠 Step 2: Analyzing performance trends...")
    insights = analyze_performance_trends(analytics_data)
    logger.info(f"   Health: {insights.get('overall_health', '?')}")
    logger.info(f"   Top themes: {insights.get('top_performing_themes', [])}")

    # Step 3: Generate new topics based on data
    logger.info(f"💡 Step 3: Generating {count} new data-driven topics...")
    topics = suggest_next_topics(analytics_data, count=count)

    if topics:
        logger.info(f"   Generated {len(topics)} topics:")
        for i, t in enumerate(topics, 1):
            logger.info(f"      {i}. {t.get('title', '?')}")
            logger.info(f"         Inspired by: {t.get('inspired_by', '?')}")

    # Step 4: Optionally write posts
    posts_written = 0
    written_posts = []
    if write_posts and topics:
        logger.info(f"\n✍️ Step 4: Writing {len(topics)} blog posts...")
        from blog_content_generator import write_blog_post
        for topic in topics:
            post = write_blog_post(topic)
            if post:
                written_posts.append(post)
                posts_written += 1
                logger.info(f"   ✅ Written: {post.get('title', '?')}")

    # Build result
    result = {
        "iteration": "data_driven",
        "timestamp": datetime.now().isoformat(),
        "analytics_count": len(analytics_data),
        "insights": insights,
        "topics_generated": len(topics),
        "topics": topics,
        "posts_written": posts_written,
    }

    _log_iteration(result)

    logger.info(f"\n🎯 Iteration complete:")
    logger.info(f"   Posts analyzed: {len(analytics_data)}")
    logger.info(f"   New topics: {len(topics)}")
    logger.info(f"   Posts written: {posts_written}")

    return result


# ──────────────────────────────────────────────
# Topic Lineage Tracking
# ──────────────────────────────────────────────

def _load_lineage():
    """Load topic lineage tracking."""
    if LINEAGE_FILE.exists():
        try:
            with open(LINEAGE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            return []
    return []


def _add_to_lineage(topic):
    """Add a topic to the lineage tracker."""
    lineage = _load_lineage()
    lineage.append({
        "title": topic.get("title", ""),
        "content_pillar": topic.get("content_pillar", ""),
        "inspired_by": topic.get("inspired_by", "original"),
        "created_at": datetime.now().isoformat(),
        "performance": None,  # Will be filled in after analytics
    })
    # Keep last 200 entries
    if len(lineage) > 200:
        lineage = lineage[-200:]
    with open(LINEAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(lineage, f, indent=2, ensure_ascii=False)


def _log_iteration(result):
    """Log iteration cycle for tracking."""
    log = []
    if ITERATION_LOG.exists():
        try:
            with open(ITERATION_LOG, "r") as f:
                log = json.load(f)
        except (json.JSONDecodeError, Exception):
            log = []

    # Summarize (don't store full post content in log)
    summary = {
        "timestamp": result.get("timestamp"),
        "type": result.get("iteration"),
        "posts_analyzed": result.get("analytics_count", 0),
        "topics_generated": result.get("topics_generated", 0),
        "posts_written": result.get("posts_written", 0),
        "topic_titles": [t.get("title", "") for t in result.get("topics", [])],
    }
    log.append(summary)

    # Keep last 50 iterations
    if len(log) > 50:
        log = log[-50:]

    with open(ITERATION_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("""
Blog Feedback Loop — Data-Driven Content Iteration

Usage:
    python blog_feedback_loop.py analyze          # Analyze current performance
    python blog_feedback_loop.py suggest [count]  # Generate data-driven topics
    python blog_feedback_loop.py iterate [count]  # Full cycle: analyze → suggest
    python blog_feedback_loop.py iterate-write [count]  # Full cycle + write posts
    python blog_feedback_loop.py lineage          # Show topic lineage
""")
        return

    cmd = sys.argv[1]

    if cmd == "analyze":
        print("🧠 Analyzing blog performance...\n")
        from blog_analytics import fetch_blog_performance
        data = fetch_blog_performance()
        if data:
            insights = analyze_performance_trends(data)
            print(json.dumps(insights, indent=2, ensure_ascii=False))
        else:
            print("No analytics data available.")

    elif cmd == "suggest":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        print(f"💡 Generating {count} data-driven topic ideas...\n")
        from blog_analytics import fetch_blog_performance
        data = fetch_blog_performance()
        topics = suggest_next_topics(data, count=count)
        if topics:
            for i, t in enumerate(topics, 1):
                print(f"\n  {i}. {t.get('title', '?')}")
                print(f"     {t.get('description', '')[:120]}")
                print(f"     Keywords: {', '.join(t.get('keywords', []))}")
                print(f"     Inspired by: {t.get('inspired_by', '?')}")
                print(f"     Expected: {t.get('expected_performance', '?')}")

    elif cmd == "iterate":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        result = auto_iterate(write_posts=False, count=count)
        print(f"\n✅ Iteration complete. {result.get('topics_generated', 0)} new topics generated.")

    elif cmd == "iterate-write":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        result = auto_iterate(write_posts=True, count=count)
        print(f"\n✅ Iteration complete. {result.get('posts_written', 0)} posts written.")

    elif cmd == "lineage":
        lineage = _load_lineage()
        if lineage:
            print(f"\n📜 Topic Lineage ({len(lineage)} entries):\n")
            for entry in lineage[-15:]:
                print(f"  • {entry.get('title', '?')}")
                print(f"    Pillar: {entry.get('content_pillar', '?')} | From: {entry.get('inspired_by', '?')}")
                print(f"    Created: {entry.get('created_at', '?')}")
                print()
        else:
            print("No lineage data yet.")

    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
