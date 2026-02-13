#!/usr/bin/env python3
"""
Blog Image Generator
Generates featured images and inline images for blog posts using Gemini Imagen.
Uploads to HubSpot File Manager.
"""

import os
import sys
import json
import logging
import base64
import requests
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
IMAGES_DIR = MODULE_DIR / "generated_images"
IMAGES_DIR.mkdir(exist_ok=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBqQF9-ivsvkAjbGhb-OIvDv6dbtBmK38M")

logger = logging.getLogger("blog_image")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def init_gemini():
    """Initialize Gemini for image generation."""
    if not GEMINI_AVAILABLE:
        logger.error("❌ google-generativeai not installed")
        return None
    genai.configure(api_key=GEMINI_API_KEY)
    return True


# ──────────────────────────────────────────────
# Image Generation
# ──────────────────────────────────────────────

def generate_featured_image(topic_title, style="modern corporate tech"):
    """
    Generate a featured/hero image for a blog post.

    Args:
        topic_title: Blog post title to create image for
        style: Visual style hint

    Returns:
        Path to saved image file, or None on failure
    """
    if not init_gemini():
        return None

    prompt = f"""Create a professional blog featured image for this article:

Title: "{topic_title}"

Style requirements:
- {style}
- Clean, modern design suitable for a B2B tech blog
- Related to manufacturing, PCB inspection, or AI technology
- Color palette: deep blue, white, subtle orange/gold accents
- Photorealistic or high-quality illustration
- 16:9 aspect ratio
- No text overlay (title will be added separately)
- Professional, enterprise-grade feel
"""

    try:
        # Use Gemini Imagen model
        imagen_model = genai.ImageGenerationModel("imagen-3.0-generate-002")
        result = imagen_model.generate_images(
            prompt=prompt,
            number_of_images=1,
            aspect_ratio="16:9",
            safety_filter_level="block_only_high",
        )

        if result.images:
            # Save image
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            slug = topic_title.lower().replace(" ", "-")[:40]
            slug = "".join(c for c in slug if c.isalnum() or c == "-")
            image_path = IMAGES_DIR / f"featured_{slug}_{timestamp}.png"

            result.images[0].save(str(image_path))
            logger.info(f"✅ Featured image saved: {image_path}")
            return str(image_path)
        else:
            logger.warning("⚠️ No images generated")
            return None

    except Exception as e:
        logger.error(f"❌ Image generation failed: {e}")
        # Fallback: try with text model to get image prompt for external use
        return _generate_with_fallback(topic_title, style)


def _generate_with_fallback(topic_title, style):
    """Fallback: use Gemini text model to generate an image via multimodal."""
    try:
        model = genai.GenerativeModel("gemini-2.0-flash-exp")

        prompt = f"""Generate a professional blog hero image for the article titled: "{topic_title}".
Style: {style}, B2B tech manufacturing, clean modern design.
Color palette: deep navy, white, with subtle orange/gold accents.
No text in the image. 16:9 aspect ratio. Photorealistic quality."""

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="image/png",
            )
        )

        if response.parts:
            for part in response.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    image_data = part.inline_data.data
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    slug = topic_title.lower().replace(" ", "-")[:40]
                    slug = "".join(c for c in slug if c.isalnum() or c == "-")
                    image_path = IMAGES_DIR / f"featured_{slug}_{timestamp}.png"

                    with open(image_path, "wb") as f:
                        f.write(image_data)

                    logger.info(f"✅ Featured image (fallback) saved: {image_path}")
                    return str(image_path)

        logger.warning("⚠️ Fallback image generation returned no image data")
        return None

    except Exception as e:
        logger.error(f"❌ Fallback image generation also failed: {e}")
        return None


def generate_image_prompt(topic_title):
    """
    Generate a detailed image prompt (for use with external tools if API fails).

    Returns:
        String prompt that can be used with any image generation tool.
    """
    if not init_gemini():
        return None

    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""Create a detailed image generation prompt for a blog featured image.

Blog title: "{topic_title}"
Context: B2B tech company that makes AI-powered optical inspection machines for PCB manufacturing.

Requirements for the prompt:
- Professional, modern, clean
- Suitable for a corporate tech blog
- 16:9 aspect ratio
- No text in the image
- Color scheme: navy blue, white, subtle gold accents

Output ONLY the image prompt text, nothing else. Make it 2-3 sentences, very specific and descriptive.
"""

    try:
        response = model.generate_content(prompt)
        image_prompt = response.text.strip()
        logger.info(f"📝 Generated image prompt: {image_prompt[:100]}...")
        return image_prompt
    except Exception as e:
        logger.error(f"Image prompt generation failed: {e}")
        return None


def upload_to_hubspot(image_path):
    """Upload generated image to HubSpot File Manager."""
    from hubspot_blog_client import upload_file
    return upload_file(image_path, folder_path="/blog-images")


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("""
Blog Image Generator

Usage:
    python blog_image_generator.py generate "Blog Post Title"    # Generate featured image
    python blog_image_generator.py prompt "Blog Post Title"      # Generate image prompt only
    python blog_image_generator.py upload <image_path>           # Upload to HubSpot
""")
        return

    cmd = sys.argv[1]

    if cmd == "generate":
        title = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "AI in Manufacturing"
        path = generate_featured_image(title)
        if path:
            print(f"\n✅ Image saved: {path}")
        else:
            print("\n❌ Image generation failed")
            # Offer prompt as fallback
            prompt = generate_image_prompt(title)
            if prompt:
                print(f"\n📝 You can use this prompt with your image tool:\n{prompt}")

    elif cmd == "prompt":
        title = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "AI in Manufacturing"
        prompt = generate_image_prompt(title)
        if prompt:
            print(f"\n📝 Image prompt:\n{prompt}")

    elif cmd == "upload":
        if len(sys.argv) < 3:
            print("Usage: python blog_image_generator.py upload <image_path>")
            return
        url = upload_to_hubspot(sys.argv[2])
        if url:
            print(f"\n✅ Uploaded: {url}")

    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
