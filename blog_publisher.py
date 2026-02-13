#!/usr/bin/env python3
"""
Blog Publisher — Orchestration Engine
Coordinates the full pipeline: generate idea → write content → create image → publish to HubSpot.
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

MODULE_DIR = Path(__file__).parent
CONFIG_FILE = MODULE_DIR / "blog_config.json"
PUBLISH_LOG = MODULE_DIR / "publish_log.json"

logger = logging.getLogger("blog_publisher")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


# ──────────────────────────────────────────────
# Full Pipeline
# ──────────────────────────────────────────────

def auto_publish_pipeline(topic=None, dry_run=False):
    """
    Full pipeline: topic idea → write → image → publish as Draft.

    Args:
        topic: Optional topic dict. If None, auto-generates one.
        dry_run: If True, do everything except actually creating the HubSpot post.

    Returns:
        Dict with pipeline results
    """
    config = load_config()
    result = {
        "timestamp": datetime.now().isoformat(),
        "dry_run": dry_run,
        "steps": {},
    }

    # ── Step 1: Topic ──
    if not topic:
        logger.info("💡 Step 1: Generating topic idea...")
        from blog_content_generator import generate_topic_ideas
        ideas = generate_topic_ideas(count=3)
        if not ideas:
            logger.error("❌ Failed to generate topic ideas")
            result["steps"]["topic"] = {"status": "failed"}
            return result
        topic = ideas[0]  # Pick the first idea
        logger.info(f"   Selected: {topic.get('title', '?')}")
    else:
        logger.info(f"💡 Step 1: Using provided topic: {topic.get('title', '?')}")

    result["steps"]["topic"] = {
        "status": "ok",
        "title": topic.get("title", ""),
        "description": topic.get("description", ""),
    }

    # ── Step 2: Write Blog Post ──
    logger.info("✍️ Step 2: Writing blog post...")
    from blog_content_generator import write_blog_post
    word_range = config.get("word_count_range", [800, 1500])
    post = write_blog_post(topic, word_count_min=word_range[0], word_count_max=word_range[1])

    if not post:
        logger.error("❌ Failed to write blog post")
        result["steps"]["write"] = {"status": "failed"}
        return result

    logger.info(f"   Title: {post.get('title', '?')}")
    logger.info(f"   Words: ~{post.get('word_count', 0)}")
    result["steps"]["write"] = {
        "status": "ok",
        "title": post.get("title", ""),
        "word_count": post.get("word_count", 0),
        "slug": post.get("slug", ""),
    }

    # ── Step 3: Generate Featured Image ──
    logger.info("🎨 Step 3: Generating featured image...")
    featured_image_url = None
    try:
        from blog_image_generator import generate_featured_image, upload_to_hubspot

        image_path = generate_featured_image(post.get("title", topic.get("title", "")))
        if image_path:
            logger.info(f"   Image generated: {image_path}")
            if not dry_run:
                featured_image_url = upload_to_hubspot(image_path)
                if featured_image_url:
                    logger.info(f"   Uploaded: {featured_image_url}")
            result["steps"]["image"] = {"status": "ok", "path": image_path, "url": featured_image_url}
        else:
            logger.warning("   ⚠️ Image generation failed, proceeding without image")
            result["steps"]["image"] = {"status": "skipped", "reason": "generation failed"}
    except Exception as e:
        logger.warning(f"   ⚠️ Image step error: {e}")
        result["steps"]["image"] = {"status": "error", "error": str(e)}

    # ── Step 4: Publish to HubSpot (Draft) ──
    if dry_run:
        logger.info("📋 Step 4: [DRY RUN] Skipping HubSpot publish")
        result["steps"]["publish"] = {"status": "dry_run"}
        result["post_id"] = None
    else:
        logger.info("📤 Step 4: Publishing to HubSpot as Draft...")
        from hubspot_blog_client import create_post

        post_id = create_post(
            title=post.get("title", ""),
            body_html=post.get("body_html", ""),
            meta_description=post.get("meta_description", ""),
            slug=post.get("slug", ""),
            featured_image_url=featured_image_url or "",
        )

        if post_id:
            logger.info(f"   ✅ Draft created! Post ID: {post_id}")
            result["steps"]["publish"] = {"status": "ok", "post_id": post_id}
            result["post_id"] = post_id
        else:
            logger.error("   ❌ Failed to create HubSpot draft")
            result["steps"]["publish"] = {"status": "failed"}
            result["post_id"] = None

    # ── Log ──
    _log_publish(result)

    # ── Summary ──
    logger.info(f"\n{'='*60}")
    logger.info("📊 Pipeline Summary:")
    for step, data in result["steps"].items():
        status = data.get("status", "?")
        icon = "✅" if status == "ok" else ("⏭️" if status in ("skipped", "dry_run") else "❌")
        logger.info(f"   {icon} {step}: {status}")
    logger.info(f"{'='*60}\n")

    return result


def batch_generate(count=5, dry_run=False):
    """
    Generate multiple blog posts in one batch.

    Args:
        count: Number of posts to generate
        dry_run: If True, don't actually publish

    Returns:
        List of pipeline results
    """
    logger.info(f"📦 Batch generating {count} blog posts...\n")

    # Generate all topics at once for consistency
    from blog_content_generator import generate_topic_ideas
    ideas = generate_topic_ideas(count=count)

    if not ideas:
        logger.error("❌ Failed to generate topic ideas")
        return []

    results = []
    for i, topic in enumerate(ideas, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"📝 Post {i}/{count}: {topic.get('title', '?')}")
        logger.info(f"{'='*60}\n")

        result = auto_publish_pipeline(topic=topic, dry_run=dry_run)
        results.append(result)

    # Summary
    success = sum(1 for r in results if r.get("post_id"))
    logger.info(f"\n🎯 Batch complete: {success}/{count} posts created")

    return results


def publish_draft(post_id):
    """Push a draft post live."""
    from hubspot_blog_client import push_live
    return push_live(post_id)


# ──────────────────────────────────────────────
# Data-Driven Pipeline (Feedback Loop + Publish)
# ──────────────────────────────────────────────

def smart_publish(count=2, dry_run=False):
    """
    The full intelligent loop:
    1. Fetch analytics
    2. Analyze performance
    3. Generate data-driven topics
    4. Write posts
    5. Publish as drafts

    This is the "one command to rule them all".
    """
    logger.info("🧠 Smart Publish: Data-driven content generation\n")

    # Step 1-3: Use feedback loop to get data-driven topics
    from blog_feedback_loop import auto_iterate
    iteration = auto_iterate(write_posts=False, count=count)

    topics = iteration.get("topics", [])
    if not topics:
        logger.error("❌ No topics generated from feedback loop")
        return []

    # Step 4-5: Write and publish each topic
    results = []
    for i, topic in enumerate(topics, 1):
        logger.info(f"\n📝 Smart Post {i}/{len(topics)}: {topic.get('title', '?')}\n")
        result = auto_publish_pipeline(topic=topic, dry_run=dry_run)
        results.append(result)

    success = sum(1 for r in results if r.get("post_id"))
    logger.info(f"\n🎯 Smart publish complete: {success}/{len(topics)} drafts created")
    return results


# ──────────────────────────────────────────────
# Publish Log
# ──────────────────────────────────────────────

def _log_publish(result):
    """Log publishing activity."""
    log = []
    if PUBLISH_LOG.exists():
        try:
            with open(PUBLISH_LOG, "r") as f:
                log = json.load(f)
        except (json.JSONDecodeError, Exception):
            log = []

    log.append({
        "timestamp": result.get("timestamp"),
        "post_id": result.get("post_id"),
        "title": result.get("steps", {}).get("write", {}).get("title", ""),
        "dry_run": result.get("dry_run", False),
        "steps_status": {k: v.get("status") for k, v in result.get("steps", {}).items()},
    })

    # Keep last 100
    if len(log) > 100:
        log = log[-100:]

    with open(PUBLISH_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("""
Blog Publisher — Full Pipeline Orchestrator

Usage:
    python blog_publisher.py run                 # Generate 1 post → Draft
    python blog_publisher.py run --dry-run       # Full pipeline without publishing
    python blog_publisher.py batch <count>       # Batch generate N posts
    python blog_publisher.py smart [count]       # Data-driven: analyze → generate → publish
    python blog_publisher.py publish <post_id>   # Push a draft live
    python blog_publisher.py status              # Show recent publish log
""")
        return

    cmd = sys.argv[1]

    if cmd == "run":
        dry_run = "--dry-run" in sys.argv
        if dry_run:
            print("🏃 Running pipeline in DRY RUN mode...\n")
        else:
            print("🏃 Running full pipeline...\n")
        auto_publish_pipeline(dry_run=dry_run)

    elif cmd == "batch":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        dry_run = "--dry-run" in sys.argv
        batch_generate(count=count, dry_run=dry_run)

    elif cmd == "smart":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 2
        dry_run = "--dry-run" in sys.argv
        smart_publish(count=count, dry_run=dry_run)

    elif cmd == "publish":
        if len(sys.argv) < 3:
            print("Usage: python blog_publisher.py publish <post_id>")
            return
        publish_draft(sys.argv[2])

    elif cmd == "status":
        if PUBLISH_LOG.exists():
            with open(PUBLISH_LOG, "r") as f:
                log = json.load(f)
            print(f"\n📋 Recent Publishes ({len(log)} total):\n")
            for entry in log[-10:]:
                ts = entry.get("timestamp", "?")[:19]
                title = entry.get("title", "?")[:45]
                pid = entry.get("post_id", "N/A")
                dry = " [DRY]" if entry.get("dry_run") else ""
                print(f"  {ts} | {title:<45} | ID: {pid}{dry}")
        else:
            print("No publish log yet.")

    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
