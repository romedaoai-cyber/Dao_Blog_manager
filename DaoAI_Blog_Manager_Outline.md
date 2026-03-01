# DaoAI Blog Manager — 系統架構大綱 / System Architecture Outline

---

## 一、系統概述 / System Overview

| 繁體中文 | English |
|---|---|
| AI 驅動的部落格管理系統 | AI-Powered Blog Management System |
| 技術棧：Python + Streamlit + Google Gemini + HubSpot API | Tech Stack: Python + Streamlit + Google Gemini + HubSpot API |
| 目標：自動化 DaoAI 的 B2B 部落格內容生產與發佈流程 | Goal: Automate DaoAI's B2B blog content production and publishing pipeline |

---

## 二、主要頁面（前端） / Main Pages (Frontend)

### 2.1 題目發想頁 / Topic Ideation Page

| 繁體中文 | English |
|---|---|
| 透過 Gemini AI 依據公司背景與 SEO 策略自動產生題目構想 | Generate topic ideas via Gemini AI based on company context and SEO strategy |
| 使用者可編輯題目標題並勾選儲存至題目佇列 | Users can edit topic titles and save selected topics to the queue |
| 顯示目前題目佇列（Topic Queue）列表與狀態 | Display current topic queue list with status |

### 2.2 內容工作室 / Content Studio

| 繁體中文 | English |
|---|---|
| **Tab 1 — 規劃大綱** 自動生成文章 Outline（Markdown 格式），可人工修改 | **Tab 1 — Plan Outline** Auto-generate article outline (Markdown format), editable by user |
| **Tab 2 — 撰寫草稿** 依 Outline 生成完整 HTML 文章，支援 AI 潤稿指令 | **Tab 2 — Draft Article** Generate full HTML article based on outline, supports AI refinement instructions |
| **Tab 3 — 發佈** 將文章推送至 HubSpot（以 Draft 模式發佈） | **Tab 3 — Publish** Push article to HubSpot (published as draft mode) |

### 2.3 圖片工作室 / Image Studio

| 繁體中文 | English |
|---|---|
| 輸入 Prompt 生成文章封面圖（開發中，模組已預留） | Input prompt to generate article featured image (in development, module reserved) |

### 2.4 應用程式設定 / App Settings

| 繁體中文 | English |
|---|---|
| 設定公司背景描述（Company Context） | Configure company background description |
| 設定語氣（Tone of Voice） | Configure tone of voice |
| 設定目標受眾（Target Audience） | Configure target audience |

---

## 三、後端模組 / Backend Modules

### 3.1 `blog_content_generator.py` — AI 內容引擎 / AI Content Engine

| 繁體中文 | English |
|---|---|
| `generate_topic_ideas()` — 產生題目構想清單（JSON） | `generate_topic_ideas()` — Generate topic idea list (JSON) |
| `generate_outline()` — 產生文章大綱（Markdown） | `generate_outline()` — Generate article outline (Markdown) |
| `write_blog_post()` — 撰寫完整文章並輸出 HTML + SEO metadata | `write_blog_post()` — Write full article, output HTML + SEO metadata |
| `refine_content()` — 依使用者指令潤稿（保留 HTML 格式） | `refine_content()` — Refine content per user instruction (preserve HTML format) |
| `generate_seo_metadata()` — 從現有內容自動生成 Meta Description 與關鍵字 | `generate_seo_metadata()` — Auto-generate meta description and keywords from existing content |

### 3.2 `hubspot_blog_client.py` — HubSpot API 客戶端 / HubSpot API Client

| 繁體中文 | English |
|---|---|
| 封裝 HubSpot REST API | Encapsulate HubSpot REST API |
| `create_post()` — 建立並上傳文章至 HubSpot（Draft 模式） | `create_post()` — Create and upload article to HubSpot (draft mode) |

### 3.3 `blog_publisher.py` — 發佈協調器 / Publishing Orchestrator

| 繁體中文 | English |
|---|---|
| `auto_publish_pipeline()` — 全自動流水線（選題 → 撰文 → 配圖 → 發佈） | `auto_publish_pipeline()` — Fully automated pipeline (topic → write → image → publish) |
| 支援 `dry_run` 模式（執行流程但不真正發佈） | Supports `dry_run` mode (run full pipeline without actual publishing) |

### 3.4 `blog_analytics.py` — 數據分析模組 / Analytics Module

| 繁體中文 | English |
|---|---|
| 從 HubSpot 抓取文章瀏覽數與互動數據 | Fetch article views and engagement data from HubSpot |
| 識別表現最佳的文章（Top Performers） | Identify top-performing articles |
| 將數據存入 `analytics_data/` 資料夾 | Save data to `analytics_data/` folder |

### 3.5 `blog_feedback_loop.py` — 反饋迴路 / Feedback Loop

| 繁體中文 | English |
|---|---|
| 將 Analytics 數據回饋給 AI 題目生成 | Feed analytics data back into AI topic generation |
| 讓下一批題目更貼近高流量內容方向 | Guide next batch of topics toward high-traffic content patterns |

### 3.6 `blog_image_generator.py` — 圖片生成模組 / Image Generator

| 繁體中文 | English |
|---|---|
| 為文章生成封面圖並儲存至 `generated_images/` | Generate featured images and save to `generated_images/` |
| 目前與前端介面尚未完整串接 | Currently not fully integrated with frontend UI |

---

## 四、資料與設定檔 / Data & Config Files

| 檔案 / File | 繁體中文說明 | English Description |
|---|---|---|
| `blog_config.json` | 核心設定（公司背景、SEO 關鍵字、目標受眾、發文排程、語氣） | Core config (company context, SEO keywords, target audience, schedule, tone) |
| `topic_queue.json` | 題目佇列（追蹤 planned / published 狀態） | Topic queue (tracks planned / published status) |
| `generated_content/` | 存放 AI 生成的題目與完整文章 JSON | Stores AI-generated topic ideas and full article JSON files |
| `generated_images/` | 存放生成的封面圖 | Stores generated featured images |
| `analytics_data/` | 存放從 HubSpot 抓回的分析數據 | Stores analytics data fetched from HubSpot |
| `.env` | API 金鑰（HubSpot Token、Gemini API Key） | API keys (HubSpot token, Gemini API key) |

---

## 五、使用者工作流程 / User Workflow

| 步驟 / Step | 繁體中文 | English |
|---|---|---|
| 1 | 進入「題目發想」，AI 產生題目清單，選擇並存入佇列 | Enter "Topic Ideation", AI generates topic list, select and save to queue |
| 2 | 進入「內容工作室」，選取題目，點擊生成 Outline | Enter "Content Studio", select topic, click to generate outline |
| 3 | 人工審閱並修改 Outline 結構 | Manually review and edit outline structure |
| 4 | 點擊「寫全文」，AI 依 Outline 撰寫完整 HTML 文章 | Click "Write Full Draft", AI writes complete HTML article following outline |
| 5 | 可使用 AI 潤稿功能（輸入指令如「更專業」、「擴充第二段」） | Optionally use AI refinement (input instruction, e.g., "more professional", "expand section 2") |
| 6 | 審閱 Meta 資訊（Slug、Meta Description）並預覽文章 | Review meta info (slug, meta description) and preview article |
| 7 | 點擊「發佈至 HubSpot」，以 Draft 模式推送上線 | Click "Publish to HubSpot", push as draft mode |
| 8 | Analytics 模組定期抓取數據，Feedback Loop 優化下一批題目 | Analytics module periodically fetches data, Feedback Loop optimizes next topic batch |

---

## 六、AI 模型與外部服務 / AI Models & External Services

| 服務 / Service | 用途（繁體中文） | Purpose (English) |
|---|---|---|
| Google Gemini 2.5 Flash | 題目生成、Outline 生成、文章撰寫、內容潤稿、SEO metadata | Topic generation, outline creation, article writing, content refinement, SEO metadata |
| HubSpot CMS API | 文章建立與發佈、數據分析抓取 | Article creation and publishing, analytics data fetching |
| Streamlit | 網頁前端介面框架 | Web frontend UI framework |
