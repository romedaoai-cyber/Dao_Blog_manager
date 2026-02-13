import streamlit as st
import json
import os
from pathlib import Path
from datetime import datetime
import pandas as pd

# Import local modules
import blog_content_generator as content_gen
import blog_image_generator as image_gen
import hubspot_blog_client as hubspot_client

# ──────────────────────────────────────────────
# Config & Setup
# ──────────────────────────────────────────────

st.set_page_config(
    page_title="DaoAI Blog Studio",
    page_icon="✍️",
    layout="wide",
)

MODULE_DIR = Path(__file__).parent
TOPIC_QUEUE_FILE = MODULE_DIR / "topic_queue.json"
CONFIG_FILE = MODULE_DIR / "blog_config.json"

# Initialize session state for workflow
if "generated_topics" not in st.session_state:
    st.session_state.generated_topics = []
if "current_draft" not in st.session_state:
    st.session_state.current_draft = {}
if "outline" not in st.session_state:
    st.session_state.outline = ""
if "full_post" not in st.session_state:
    st.session_state.full_post = {}

def load_queue():
    if TOPIC_QUEUE_FILE.exists():
        try:
            with open(TOPIC_QUEUE_FILE, "r") as f:
                return json.load(f)
        except:
            return []
    return []

def save_queue(queue):
    with open(TOPIC_QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)

def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

# ──────────────────────────────────────────────
# UI: Sidebar & Navigation
# ──────────────────────────────────────────────

st.sidebar.title("DaoAI Blog Studio 🚀")
page = st.sidebar.radio("Navigate", ["Topic Ideation", "Content Studio", "Image Studio", "App Settings"])

st.sidebar.markdown("---")
st.sidebar.info(f"**HubSpot Portal**: {load_config().get('hubspot_portal_id', 'Unknown')}")

# ──────────────────────────────────────────────
# Page 1: Topic Ideation
# ──────────────────────────────────────────────

if page == "Topic Ideation":
    st.header("💡 Topic Ideation")
    st.markdown("Generate new blog ideas based on data and strategy.")

    col1, col2 = st.columns([1, 2])
    
    with col1:
        count = st.slider("Number of ideas", 3, 10, 5)
        if st.button("✨ Generate Ideas"):
            with st.spinner("Brainstorming with Gemini..."):
                try:
                    ideas = content_gen.generate_topic_ideas(count=count)
                    st.session_state.generated_topics = ideas
                    st.success(f"Generated {len(ideas)} ideas!")
                except Exception as e:
                    st.error(f"Error: {e}")

    with col2:
        if st.session_state.generated_topics:
            queue = load_queue()
            st.subheader("Results")
            
            # Form to select and save topics
            with st.form("topic_selection"):
                selected_indices = []
                edited_topics = []
                
                for i, topic in enumerate(st.session_state.generated_topics):
                    st.markdown(f"**{i+1}. {topic.get('title')}**")
                    new_title = st.text_input(f"Edit Title #{i+1}", topic.get('title'))
                    st.caption(topic.get('description'))
                    if st.checkbox(f"Select #{i+1}", key=f"dtopic_{i}"):
                        topic['title'] = new_title  # Save edited title
                        selected_indices.append(topic)
                    st.markdown("---")
                
                if st.form_submit_button("💾 Save Selected to Queue"):
                    for t in selected_indices:
                        t['status'] = 'planned'
                        t['created_at'] = datetime.now().isoformat()
                        queue.append(t)
                    save_queue(queue)
                    st.success(f"Saved {len(selected_indices)} topics to queue!")
                    st.session_state.generated_topics = [] # Clear after save

    # Show Current Queue
    st.markdown("### 📋 Topic Queue")
    queue = load_queue()
    if queue:
        df = pd.DataFrame(queue)
        st.dataframe(df[['title', 'status', 'content_pillar']], use_container_width=True)
    else:
        st.info("Queue is empty. Generate some ideas first!")


# ──────────────────────────────────────────────
# Page 2: Content Studio (The "Modify then Modify" Workflow)
# ──────────────────────────────────────────────

elif page == "Content Studio":
    st.header("✍️ Content Studio")
    queue = load_queue()
    planned_topics = [t for t in queue if t.get('status') == 'planned']
    
    if not planned_topics:
        st.warning("No planned topics found. Go to 'Topic Ideation' to add some!")
        st.stop()

    # Select workflow stage
    topic_titles = [t['title'] for t in planned_topics]
    selected_topic_title = st.selectbox("Select Topic to Write", topic_titles)
    selected_topic = next((t for t in planned_topics if t['title'] == selected_topic_title), None)

    if selected_topic:
        st.info(f"**Description**: {selected_topic.get('description')}")
        st.caption(f"Keywords: {', '.join(selected_topic.get('keywords', []))}")

        # Workflow: 1. Outline -> 2. Edit Outline -> 3. Write Post -> 4. Edit Post -> 5. Publish
        
        tab1, tab2, tab3 = st.tabs(["1. Plan Outline", "2. Draft Article", "3. Publish"])

        # TAB 1: OUTLINE
        with tab1:
            if st.button("📑 Generate Outline"):
                with st.spinner("Structuring thoughts..."):
                    outline = content_gen.generate_outline(selected_topic)
                    st.session_state.outline = outline
            
            if st.session_state.outline:
                st.markdown("### Edit Outline")
                new_outline = st.text_area("Refine the structure before writing:", 
                                          value=st.session_state.outline, 
                                          height=400)
                st.session_state.outline = new_outline
                st.success("Tip: Adjust headlines and bullet points here. The AI will follow this structure.")

        # TAB 2: DRAFT
        with tab2:
            if not st.session_state.outline:
                st.warning("Please generate an outline in Tab 1 first.")
            else:
                if st.button("📝 Write Full Draft"):
                    with st.spinner("Writing article based on your outline..."):
                        # We need to hack write_blog_post or prompt it to use this outline
                        # For now, we'll append the outline to the topic description/instructions
                        topic_with_outline = selected_topic.copy()
                        topic_with_outline['description'] += f"\n\nFOLLOW THIS OUTLINE STRICTLY:\n{st.session_state.outline}"
                        
                        post = content_gen.write_blog_post(topic_with_outline)
                        if post:
                            st.session_state.full_post = post
                            st.success("Draft generated!")
                
                if st.session_state.full_post:
                    st.markdown("### Edit Draft")

                    # AI Refinement
                    with st.expander("✨ AI Refinement", expanded=False):
                        refine_instruction = st.text_input("Instruction (e.g., 'Make it more professional', 'Expand the second section')", key="refine_inst")
                        if st.button("Refine with AI"):
                            if refine_instruction:
                                with st.spinner("Refining content..."):
                                    current_content = st.session_state.full_post.get('body_html', '')
                                    refined = content_gen.refine_content(current_content, refine_instruction)
                                    st.session_state.full_post['body_html'] = refined
                                    st.success("Content refined! Check the editor below.")
                            else:
                                st.warning("Please enter an instruction.")

                    with st.expander("Review Meta Info"):
                        st.text_input("Slug", value=st.session_state.full_post.get('slug', ''))
                        st.text_area("Meta Description", value=st.session_state.full_post.get('meta_description', ''))

                    # Simple HTML editor (TextArea for now)
                    new_body = st.text_area("Article Body (HTML)", 
                                           value=st.session_state.full_post.get('body_html', ''), 
                                           height=600)
                    st.session_state.full_post['body_html'] = new_body
                    
                    st.markdown("### Preview")
                    st.markdown(new_body, unsafe_allow_html=True)

        # TAB 3: PUBLISH
        with tab3:
            if not st.session_state.full_post:
                st.warning("Please write the draft in Tab 2 first.")
            else:
                st.subheader("Ready to Publish?")
                if st.button("📤 Publish Draft to HubSpot"):
                    with st.spinner("Uploading..."):
                        p = st.session_state.full_post
                        post_id = hubspot_client.create_post(
                            title=p.get('title'),
                            body_html=p.get('body_html'),
                            meta_description=p.get('meta_description'),
                            slug=p.get('slug')
                        )
                        
                        if post_id:
                            st.balloons()
                            st.success(f"✅ Published! Post ID: {post_id}")
                            st.markdown(f"[View in HubSpot](https://app.hubspot.com/blog/{load_config().get('hubspot_portal_id')}/edit/{post_id})")
                            
                            # Update queue status
                            queue = load_queue() # reload to avoid race
                            for t in queue:
                                if t['title'] == selected_topic['title']:
                                    t['status'] = 'published'
                                    t['post_id'] = post_id
                            save_queue(queue)
                        else:
                            st.error("Publish failed. Check logs.")

# ──────────────────────────────────────────────
# Page 3: Image Studio
# ──────────────────────────────────────────────

elif page == "Image Studio":
    st.header("🎨 Image Studio")
    
    prompt = st.text_area("Image Prompt", "Modern corporate office, bright, technology visualization, blue tones")
    if st.button("Generate Image"):
        with st.spinner("Painting pixels..."):
             # Placeholder for image gen integration
             st.info("Image generation integration would go here. (Using blog_image_generator module)")
             # In a real run, we'd call image_gen.generate_featured_image(prompt)
             # image_path = image_gen.generate_featured_image_from_prompt(prompt)
             # st.image(image_path)

# ──────────────────────────────────────────────
# Page 4: Settings
# ──────────────────────────────────────────────

elif page == "App Settings":
    st.header("⚙️ Configuration")
    
    config = load_config()
    
    with st.form("settings_form"):
        st.subheader("Company Context")
        new_context = st.text_area("Context", config.get('company_context', ''), height=150)
        
        st.subheader("Tone of Voice")
        new_tone = st.text_input("Tone", config.get('tone', ''))
        
        st.subheader("Target Audience")
        current_audience = "\n".join(config.get('target_audience', []))
        new_audience = st.text_area("Audience (one per line)", current_audience)
        
        if st.form_submit_button("Update Settings"):
            config['company_context'] = new_context
            config['tone'] = new_tone
            config['target_audience'] = [a.strip() for a in new_audience.split('\n') if a.strip()]
            save_config(config)
            st.success("Settings updated!")
