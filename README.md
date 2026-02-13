# DaoAI Blog Manager ✍️

A streamlined, AI-powered blog management system for HubSpot.

## Features
- **Topic Ideation**: Generate blog topics based on strategy.
- **Content Studio**: AI-assisted writing (Outline -> Draft -> Refine).
- **HubSpot Integration**: Publish directly to your HubSpot portal.
- **Analytics**: Track views and engagement.

## Setup

1. **Clone the repo**
   ```bash
   git clone https://github.com/srs0319/Daoai-Blog-manager.git
   cd Daoai-Blog-manager
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Secrets**
   - Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env
     ```
   - Edit `.env` and add your keys:
     - `HUBSPOT_ACCESS_KEY`: Your HubSpot Private App Token.
     - `GEMINI_API_KEY`: Google Gemini API Key.

4. **Run the Dashboard**
   ```bash
   streamlit run blog_dashboard.py
   ```

## Cloud Deployment (Streamlit Cloud)

1. Push this repo to GitHub.
2. Connect to Streamlit Cloud.
3. Add the contents of your `.env` file to the **Secrets** section in Streamlit Cloud settings.
