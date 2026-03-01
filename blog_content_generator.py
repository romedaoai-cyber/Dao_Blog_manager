#!/usr/bin/env python3
"""
Blog Content Generator
Uses Gemini AI to generate blog topic ideas, write full articles, and create SEO metadata.
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
CONTENT_DIR = MODULE_DIR / "generated_content"
CONTENT_DIR.mkdir(exist_ok=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBqQF9-ivsvkAjbGhb-OIvDv6dbtBmK38M")

logger = logging.getLogger("blog_content")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def load_config():
    """Load blog configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def init_gemini():
    """Initialize Gemini model."""
    if not GEMINI_AVAILABLE:
        logger.error("❌ google-generativeai not installed. Run: pip install google-generativeai")
        return None
    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel("gemini-2.5-flash")


# ──────────────────────────────────────────────
# Topic Ideation
# ──────────────────────────────────────────────

def generate_topic_ideas(analytics_summary=None, count=5):
    """
    Generate blog topic ideas based on company context and optional analytics.

    Args:
        analytics_summary: Optional dict with top-performing topics and trends
        count: Number of ideas to generate

    Returns:
        List of topic dicts: [{title, description, keywords, target_audience, content_pillar}]
    """
    config = load_config()
    model = init_gemini()
    if not model:
        return []

    analytics_context = ""
    if analytics_summary:
        top_topics = analytics_summary.get("top_performing_topics", [])
        trends = analytics_summary.get("trends", "")
        analytics_context = f"""
PERFORMANCE DATA (use this to guide new topics):
- Top performing topics: {json.dumps(top_topics, indent=2)}
- Observed trends: {trends}
- Generate topics that are SIMILAR to high-performers but explore new angles.
- Avoid repeating exact topics that have already been covered.
"""

    prompt = f"""You are a content strategist for a B2B technology company.

COMPANY CONTEXT:
{config.get('company_context', 'AI visual inspection company for PCBA manufacturing')}

TARGET AUDIENCE:
{json.dumps(config.get('target_audience', []), indent=2)}

CONTENT PILLARS:
{json.dumps(config.get('content_pillars', []), indent=2)}

SEO FOCUS KEYWORDS:
{json.dumps(config.get('seo', {}).get('focus_keywords', []), indent=2)}

{analytics_context}

Generate exactly {count} blog post topic ideas. For each topic provide:
1. title — compelling, SEO-friendly blog title
2. description — 2-3 sentence summary of what the post will cover
3. keywords — 3-5 target SEO keywords
4. target_audience — primary reader persona
5. content_pillar — which content pillar this aligns with
6. estimated_search_volume — low/medium/high (your best guess)

Output ONLY valid JSON array. No markdown, no explanation.
Example: [{{"title": "...", "description": "...", "keywords": ["..."], "target_audience": "...", "content_pillar": "...", "estimated_search_volume": "medium"}}]
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
        # Clean up markdown code blocks if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        ideas = json.loads(text)
        logger.info(f"✅ Generated {len(ideas)} topic ideas")

        # Save ideas to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ideas_file = CONTENT_DIR / f"ideas_{timestamp}.json"
        with open(ideas_file, "w", encoding="utf-8") as f:
            json.dump(ideas, f, indent=2, ensure_ascii=False)
        logger.info(f"   Saved to {ideas_file}")

        return ideas

    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse AI response as JSON: {e}")
        logger.error(f"   Raw response: {text[:500]}")
        return []
    except Exception as e:
        logger.error(f"❌ Topic generation failed: {e}")
        return []


# ──────────────────────────────────────────────
# Outline Generation
# ──────────────────────────────────────────────

def generate_outline(topic):
    """
    Generate a detailed blog post outline for user review/editing.

    Args:
        topic: Dict with 'title', 'description', etc.

    Returns:
        String containing the outline (Markdown format)
    """
    config = load_config()
    model = init_gemini()
    if not model:
        return ""

    title = topic.get("title", "Untitled")
    description = topic.get("description", "")
    audience = topic.get("target_audience", "manufacturing professionals")
    keywords = topic.get("keywords", [])

    prompt = f"""You are an expert content strategist. Create a detailed outline for a B2B blog post.

TITLE: {title}
TOPIC: {description}
TARGET AUDIENCE: {audience}
KEYWORDS: {', '.join(keywords)}

COMPANY CONTEXT:
{config.get('company_context', '')}

REQUIREMENTS:
1. Structure with standard Introduction, Body Paragraphs (H2s), and Conclusion.
2. Under each H2, list 3-5 bullet points of key information to cover.
3. Ensure the flow is logical and persuasive.
4. CRITICAL: For EVERY heading (H1, H2) and EVERY bullet point, you MUST provide the English original first, followed immediately by the Traditional Chinese (zh-TW) translation on a new line, italicized or separated clearly. For example:
   - English point here.
   *(中文翻譯放這裡)*
5. return ONLY the outline in Markdown format.
"""

    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"❌ Outline generation failed: {e}")
        return ""


# ──────────────────────────────────────────────
# Blog Post Writing
# ──────────────────────────────────────────────

def write_blog_post(topic, word_count_min=800, word_count_max=1500):
    """
    Write a full blog post from a topic.

    Args:
        topic: Dict with at least 'title' and 'description'
        word_count_min: Minimum word count
        word_count_max: Maximum word count

    Returns:
        Dict with {title, meta_description, body_html, slug, keywords, word_count}
    """
    config = load_config()
    model = init_gemini()
    if not model:
        return None

    title = topic.get("title", "Untitled")
    description = topic.get("description", "")
    keywords = topic.get("keywords", [])
    audience = topic.get("target_audience", "manufacturing professionals")

    prompt = f"""You are an expert B2B content writer specializing in manufacturing technology.

Write a complete blog post with the following specifications:

TITLE: {title}
TOPIC: {description}
TARGET KEYWORDS: {', '.join(keywords)}
TARGET AUDIENCE: {audience}
WORD COUNT: {word_count_min}-{word_count_max} words
TONE: {config.get('tone', 'professional and accessible')}

COMPANY CONTEXT (weave naturally, don't force):
{config.get('company_context', '')}

REQUIREMENTS:
1. Write in English
2. Use HTML formatting (h2, h3, p, ul, li, strong, em — no h1, the title is separate)
3. Start with a compelling hook, NOT "In today's rapidly evolving..." cliché
4. Include 3-5 clear sections with h2 headers
5. Include practical takeaways and data points where possible
6. End with a clear conclusion and subtle CTA related to learning more about AI-powered inspection
7. Naturally incorporate target keywords for SEO (don't stuff)
8. Make it genuinely educational and valuable — not a sales pitch
9. Use short paragraphs (2-3 sentences max) for readability

OUTPUT FORMAT:
Return ONLY valid JSON with these keys:
{{
    "title": "Final polished title",
    "meta_description": "155 characters max SEO meta description",
    "body_html": "<h2>...</h2><p>...</p>...",
    "slug": "url-friendly-slug",
    "keywords": ["keyword1", "keyword2"],
    "word_count": 1200
}}
"""

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=8192,
                temperature=0.7,
            )
        )

        text = response.text.strip()
        # Clean up markdown code blocks if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        post = json.loads(text)
        actual_words = len(post.get("body_html", "").split())
        post["word_count"] = actual_words

        logger.info(f"✅ Blog post written: {post.get('title', title)}")
        logger.info(f"   Word count: ~{actual_words}")

        # Save the full post
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = post.get("slug", "untitled")
        post_file = CONTENT_DIR / f"post_{slug}_{timestamp}.json"
        with open(post_file, "w", encoding="utf-8") as f:
            json.dump(post, f, indent=2, ensure_ascii=False)
        logger.info(f"   Saved to {post_file}")

        return post

    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse blog post JSON: {e}")
        logger.error(f"   Raw (first 500 chars): {text[:500]}")
        return None
    except Exception as e:
        logger.error(f"❌ Blog writing failed: {e}")
        return None


# ──────────────────────────────────────────────
# Content Refinement
# ──────────────────────────────────────────────

def refine_content(content, instruction):
    """
    Refine existing content based on user instructions.

    Args:
        content: The HTML or text content to refine
        instruction: User's instruction (e.g., "Make it more professional", "Expand section 2")

    Returns:
        Refined content string
    """
    model = init_gemini()
    if not model:
        return content

    prompt = f"""You are an expert editor. Refine the following blog post content based on the user's instruction.

USER INSTRUCTION: {instruction}

CONTENT:
{content}

REQUIREMENTS:
1. Keep HTML formatting intact (if present).
2. Only make changes requested by the user.
3. Return ONLY the refined content.
"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        return text
    except Exception as e:
        logger.error(f"❌ Content refinement failed: {e}")
        return content


# ──────────────────────────────────────────────
# SEO Metadata
# ──────────────────────────────────────────────

def generate_seo_metadata(body_html, title):
    """Generate SEO meta description and keywords from existing content."""
    model = init_gemini()
    if not model:
        return {"meta_description": "", "keywords": []}

    # Truncate body for prompt efficiency
    body_preview = body_html[:3000] if len(body_html) > 3000 else body_html

    prompt = f"""Analyze this blog post and generate SEO metadata.

TITLE: {title}
CONTENT (preview): {body_preview}

Return ONLY valid JSON:
{{
    "meta_description": "Max 155 chars, compelling, includes primary keyword",
    "keywords": ["5-8 relevant SEO keywords"],
    "reading_time_minutes": 5
}}
"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        return json.loads(text)
    except Exception as e:
        logger.error(f"SEO metadata generation failed: {e}")
        return {"meta_description": "", "keywords": []}


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("""
Blog Content Generator

Usage:
    python blog_content_generator.py ideas [count]     # Generate topic ideas
    python blog_content_generator.py write "Title"     # Write a post from title
    python blog_content_generator.py auto              # Generate ideas → pick best → write
""")
        return

    cmd = sys.argv[1]

    if cmd == "ideas":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        ideas = generate_topic_ideas(count=count)
        if ideas:
            print(f"\n💡 Generated {len(ideas)} ideas:\n")
            for i, idea in enumerate(ideas, 1):
                print(f"  {i}. {idea.get('title', '?')}")
                print(f"     {idea.get('description', '')[:100]}")
                print(f"     Keywords: {', '.join(idea.get('keywords', []))}")
                print()

    elif cmd == "write":
        title = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None
        if not title:
            print("Usage: python blog_content_generator.py write \"Your Blog Title\"")
            return
        topic = {"title": title, "description": title, "keywords": [], "target_audience": ""}
        post = write_blog_post(topic)
        if post:
            print(f"\n✅ Post written: {post.get('title', title)}")
            print(f"   Meta: {post.get('meta_description', '')[:80]}...")
            print(f"   Words: ~{post.get('word_count', 0)}")

    elif cmd == "auto":
        print("🤖 Auto mode: generating ideas and writing best topic...\n")
        ideas = generate_topic_ideas(count=3)
        if ideas:
            # Pick first idea (in production, could rank by search volume)
            best = ideas[0]
            print(f"📝 Selected: {best.get('title', '?')}\n")
            post = write_blog_post(best)
            if post:
                print(f"\n✅ Done! Post saved to generated_content/")

    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
