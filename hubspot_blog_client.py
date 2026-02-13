#!/usr/bin/env python3
"""
HubSpot Blog API Client
Handles all HubSpot CMS Blog API interactions: list, create, update, publish posts.
"""

import os
import sys
import json
import yaml
import requests
from pathlib import Path
from datetime import datetime

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

MODULE_DIR = Path(__file__).parent
ROOT_DIR = MODULE_DIR
HUBSPOT_CONFIG = MODULE_DIR / "hubspot.config.yml"
ENV_FILE = MODULE_DIR / ".env"
CONFIG_FILE = MODULE_DIR / "blog_config.json"
LOCAL_POSTS_DB = MODULE_DIR / "blog_posts_local.json"

HUBSPOT_API_BASE = "https://api.hubapi.com"
CMS_BLOG_POSTS = f"{HUBSPOT_API_BASE}/cms/v3/blogs/posts"
CMS_BLOGS = f"{HUBSPOT_API_BASE}/cms/v3/blogs/posts"  # list endpoint
FILE_MANAGER = f"{HUBSPOT_API_BASE}/filemanager/api/v3/files/upload"


def load_access_key():
    """Load HubSpot access key from env var, hubspot.config.yml, or .env file."""
    # 1. Try environment variable
    env_key = os.environ.get("HUBSPOT_ACCESS_KEY")
    if env_key:
        return env_key

    # 2. Try hubspot.config.yml (most reliable)
    if HUBSPOT_CONFIG.exists():
        try:
            with open(HUBSPOT_CONFIG, "r") as f:
                config = yaml.safe_load(f)
            portals = config.get("portals", [])
            if portals:
                token_info = portals[0].get("auth", {}).get("tokenInfo", {})
                access_token = token_info.get("accessToken", "")
                if access_token:
                    return access_token
                # Also try personalAccessKey
                pak = portals[0].get("personalAccessKey", "")
                if pak:
                    return pak
        except Exception as e:
            print(f"⚠️ Could not read hubspot.config.yml: {e}")

    # 3. Try .env file (may have permission issues)
    try:
        if ENV_FILE.exists():
            with open(ENV_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("HUBSPOT_ACCESS_KEY="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
    except PermissionError:
        pass  # .env may have restricted permissions

    print("❌ No HubSpot access key found. Set HUBSPOT_ACCESS_KEY env var or check hubspot.config.yml")
    return None


def load_config():
    """Load blog configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def get_headers(access_key=None):
    """Build HubSpot API request headers."""
    if not access_key:
        access_key = load_access_key()
    return {
        "Authorization": f"Bearer {access_key}",
        "Content-Type": "application/json",
    }


# ──────────────────────────────────────────────
# Blog Discovery
# ──────────────────────────────────────────────

def list_blogs():
    """List all blogs in the HubSpot portal."""
    access_key = load_access_key()
    if not access_key:
        return []

    url = f"{HUBSPOT_API_BASE}/cms/v3/blogs/posts"
    headers = get_headers(access_key)

    # Get unique blog group IDs from existing posts
    resp = requests.get(url, headers=headers, params={"limit": 10})
    if resp.status_code != 200:
        print(f"❌ Failed to list blogs: {resp.status_code} {resp.text[:200]}")
        return []

    data = resp.json()
    results = data.get("results", [])

    # Extract unique content group IDs (blog IDs)
    blog_ids = set()
    for post in results:
        cg_id = post.get("contentGroupId")
        if cg_id:
            blog_ids.add(cg_id)

    print(f"📝 Found {len(blog_ids)} blog(s) with {len(results)} posts")
    for bid in blog_ids:
        print(f"   Blog ID: {bid}")

    return list(blog_ids)


def detect_blog_id():
    """Auto-detect blog ID from portal, cache to config."""
    config = load_config()
    if config.get("blog_id"):
        return config["blog_id"]

    blog_ids = list_blogs()
    if blog_ids:
        blog_id = blog_ids[0]  # Use first blog
        config["blog_id"] = blog_id
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        print(f"✅ Auto-detected blog ID: {blog_id}")
        return blog_id

    print("⚠️ No blog found. Please create a blog in HubSpot first.")
    return None


# ──────────────────────────────────────────────
# Blog Post CRUD
# ──────────────────────────────────────────────

def create_post(title, body_html, meta_description="", slug="", author_id=None,
                featured_image_url="", tags=None):
    """
    Create a new blog post as DRAFT.
    Returns the post ID or None on failure.
    """
    access_key = load_access_key()
    if not access_key:
        return None

    blog_id = detect_blog_id()
    if not blog_id:
        return None

    # Build slug from title if not provided
    if not slug:
        slug = title.lower().replace(" ", "-").replace("'", "")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        slug = slug[:80]  # Keep URL manageable

    post_data = {
        "name": title,
        "contentGroupId": blog_id,
        "postBody": body_html,
        "slug": slug,
        "metaDescription": meta_description,
        "htmlTitle": title,
        "useFeaturedImage": bool(featured_image_url),
    }

    if author_id:
        post_data["blogAuthorId"] = author_id
    if featured_image_url:
        post_data["featuredImage"] = featured_image_url
    if tags:
        post_data["tagIds"] = tags

    headers = get_headers(access_key)
    resp = requests.post(CMS_BLOG_POSTS, headers=headers, json=post_data)

    if resp.status_code in (200, 201):
        result = resp.json()
        post_id = result.get("id")
        print(f"✅ Draft created: {title}")
        print(f"   Post ID: {post_id}")
        print(f"   Slug: /{slug}")

        # Save to local DB
        _save_local_post(post_id, title, slug, "DRAFT")
        return post_id
    else:
        print(f"❌ Failed to create post: {resp.status_code}")
        print(f"   {resp.text[:300]}")
        return None


def push_live(post_id):
    """Publish a draft post, making it live."""
    access_key = load_access_key()
    if not access_key:
        return False

    url = f"{CMS_BLOG_POSTS}/{post_id}/draft/push-live"
    headers = get_headers(access_key)
    resp = requests.post(url, headers=headers)

    if resp.status_code in (200, 204):
        print(f"✅ Post {post_id} is now LIVE!")
        _update_local_post(post_id, "PUBLISHED")
        return True
    else:
        print(f"❌ Failed to publish: {resp.status_code} {resp.text[:200]}")
        return False


def schedule_post(post_id, publish_date_iso):
    """Schedule a draft for future publication."""
    access_key = load_access_key()
    if not access_key:
        return False

    url = f"{CMS_BLOG_POSTS}/{post_id}/draft/schedule"
    headers = get_headers(access_key)
    data = {"publishDate": publish_date_iso}
    resp = requests.post(url, headers=headers, json=data)

    if resp.status_code in (200, 204):
        print(f"✅ Post {post_id} scheduled for {publish_date_iso}")
        _update_local_post(post_id, f"SCHEDULED:{publish_date_iso}")
        return True
    else:
        print(f"❌ Failed to schedule: {resp.status_code} {resp.text[:200]}")
        return False


def get_post(post_id):
    """Get a single blog post by ID."""
    access_key = load_access_key()
    if not access_key:
        return None

    url = f"{CMS_BLOG_POSTS}/{post_id}"
    headers = get_headers(access_key)
    resp = requests.get(url, headers=headers)

    if resp.status_code == 200:
        return resp.json()
    else:
        print(f"❌ Failed to get post {post_id}: {resp.status_code}")
        return None


def list_posts(limit=20, state=None):
    """
    List blog posts.
    state: 'DRAFT', 'PUBLISHED', 'SCHEDULED', or None for all
    """
    access_key = load_access_key()
    if not access_key:
        return []

    headers = get_headers(access_key)
    params = {"limit": limit, "sort": "-created"}
    if state:
        params["state"] = state

    resp = requests.get(CMS_BLOG_POSTS, headers=headers, params=params)

    if resp.status_code == 200:
        data = resp.json()
        results = data.get("results", [])
        print(f"\n📝 Blog Posts ({state or 'ALL'}):")
        print(f"{'ID':<15} {'State':<12} {'Title':<50}")
        print("─" * 80)
        for post in results:
            state_str = post.get("state", "?")
            title = post.get("name", "Untitled")[:50]
            pid = post.get("id", "?")
            print(f"{pid:<15} {state_str:<12} {title}")
        return results
    else:
        print(f"❌ Failed to list posts: {resp.status_code}")
        return []


def update_post(post_id, updates):
    """Update a blog post with partial data."""
    access_key = load_access_key()
    if not access_key:
        return False

    url = f"{CMS_BLOG_POSTS}/{post_id}"
    headers = get_headers(access_key)
    resp = requests.patch(url, headers=headers, json=updates)

    if resp.status_code == 200:
        print(f"✅ Post {post_id} updated")
        return True
    else:
        print(f"❌ Failed to update post: {resp.status_code} {resp.text[:200]}")
        return False


# ──────────────────────────────────────────────
# File Upload (for images)
# ──────────────────────────────────────────────

def upload_file(file_path, folder_path="/blog-images"):
    """Upload a file to HubSpot File Manager, return the public URL."""
    access_key = load_access_key()
    if not access_key:
        return None

    file_path = Path(file_path)
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return None

    url = f"{HUBSPOT_API_BASE}/files/v3/files"
    headers = {"Authorization": f"Bearer {access_key}"}

    # Multipart upload
    options = json.dumps({
        "access": "PUBLIC_INDEXABLE",
        "overwrite": True
    })
    folder_options = json.dumps({
        "path": folder_path
    })

    with open(file_path, "rb") as f:
        files = {
            "file": (file_path.name, f, "image/png"),
            "options": (None, options, "application/json"),
            "folderPath": (None, folder_path),
        }
        resp = requests.post(url, headers=headers, files=files)

    if resp.status_code in (200, 201):
        result = resp.json()
        file_url = result.get("url", "")
        print(f"✅ Uploaded: {file_path.name} → {file_url}")
        return file_url
    else:
        print(f"❌ Upload failed: {resp.status_code} {resp.text[:200]}")
        return None


# ──────────────────────────────────────────────
# Local Post Database
# ──────────────────────────────────────────────

def _save_local_post(post_id, title, slug, status):
    """Track posts locally for analytics correlation."""
    posts = _load_local_posts()
    posts.append({
        "id": post_id,
        "title": title,
        "slug": slug,
        "status": status,
        "created_at": datetime.now().isoformat(),
        "published_at": None,
    })
    with open(LOCAL_POSTS_DB, "w") as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)


def _update_local_post(post_id, status):
    """Update local post status."""
    posts = _load_local_posts()
    for p in posts:
        if p["id"] == post_id:
            p["status"] = status
            if "PUBLISHED" in status:
                p["published_at"] = datetime.now().isoformat()
            break
    with open(LOCAL_POSTS_DB, "w") as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)


def _load_local_posts():
    """Load local posts database."""
    if LOCAL_POSTS_DB.exists():
        try:
            with open(LOCAL_POSTS_DB, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            return []
    return []


# ──────────────────────────────────────────────
# CLI / Test
# ──────────────────────────────────────────────

def test_connection():
    """Test HubSpot API connection and permissions."""
    print("🔍 Testing HubSpot API connection...")
    access_key = load_access_key()
    if not access_key:
        print("❌ No access key found")
        return False

    headers = get_headers(access_key)

    # Test: list posts
    try:
        resp = requests.get(CMS_BLOG_POSTS, headers=headers, params={"limit": 1}, timeout=15)
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to HubSpot API. Check your network connection.")
        return False
    except requests.exceptions.Timeout:
        print("❌ HubSpot API request timed out.")
        return False

    if resp.status_code == 200:
        data = resp.json()
        total = data.get("total", 0)
        print(f"✅ API connected! Portal has {total} blog posts.")

        # Auto-detect blog ID
        blog_id = detect_blog_id()
        if blog_id:
            print(f"✅ Blog ID: {blog_id}")
        return True
    elif resp.status_code == 401:
        print("❌ Authentication failed. Check your access key.")
        print(f"   Response: {resp.text[:200]}")
        return False
    elif resp.status_code == 403:
        print("❌ Permission denied. Your key may not have 'content' scope.")
        print(f"   Response: {resp.text[:200]}")
        return False
    else:
        print(f"❌ Unexpected response: {resp.status_code}")
        print(f"   {resp.text[:200]}")
        return False


def main():
    if len(sys.argv) < 2:
        print("""
HubSpot Blog API Client

Usage:
    python hubspot_blog_client.py test              # Test connection
    python hubspot_blog_client.py list [state]       # List posts (DRAFT/PUBLISHED)
    python hubspot_blog_client.py publish <post_id>  # Push draft live
    python hubspot_blog_client.py blogs              # List blog IDs
""")
        return

    cmd = sys.argv[1]

    if cmd == "test":
        test_connection()
    elif cmd == "list":
        state = sys.argv[2].upper() if len(sys.argv) > 2 else None
        list_posts(state=state)
    elif cmd == "publish":
        if len(sys.argv) < 3:
            print("Usage: python hubspot_blog_client.py publish <post_id>")
            return
        push_live(sys.argv[2])
    elif cmd == "blogs":
        list_blogs()
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
