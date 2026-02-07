<div align="center">

# 🧠 LearnWeave

### _Learning Outcome–Aligned Study Support System_

**🏆 Hackathon Submission — Problem Statement 1**

> _"Design a learning companion that ingests academic PDFs and maps content directly to Bloom's Taxonomy levels. It must generate assessments that test 'Application' and 'Synthesis' rather than just 'Recall', providing hints that encourage reasoning."_

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white)](https://react.dev)
[![Google ADK](https://img.shields.io/badge/Google_ADK-Gemini_2.5-4285F4?logo=google&logoColor=white)](https://google.github.io/adk-docs/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_DB-FF6F00)](https://www.trychroma.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docker.com)

</div>

---

## 📌 Problem Statement

Indian students often focus on **memorization over deep understanding**. Most AI tutors simply summarize text without checking if the output aligns with specific **curriculum learning outcomes**.

**LearnWeave** tackles this by building an AI-powered learning companion that:

- 📄 **Ingests academic PDFs** and maps content to **Bloom's Taxonomy** levels
- 🎯 **Generates assessments** targeting **Application, Analysis & Synthesis** — not just Recall
- 💡 **Provides reasoning-based feedback** with hints that encourage critical thinking
- 🌐 **Supports vernacular contexts** — generate courses in any language (Hindi, Tamil, etc.)

---

## ✨ Key Features

### 🤖 Multi-Agent AI Architecture (8 Specialized Agents)

LearnWeave uses **[Google's Agent Development Kit (ADK)](https://google.github.io/adk-docs/)** with **Gemini 2.5 Flash** to orchestrate a team of specialized AI agents:

| Agent | Role |
|-------|------|
| **PlannerRetrieverAgent** | Ingests PDFs + user parameters → produces a structured course plan with chapters and learning objectives |
| **ExplainerAgent** | Generates **interactive React/JSX visual explanations** per chapter (charts, code, LaTeX, diagrams) with ESLint auto-validation |
| **TesterAgent** | Creates **MCQ + open-text assessments** as interactive React components; explicitly prioritizes _understanding over memorization_ |
| **GraderAgent** | Grades open-text answers on a rubric (0–2 points) with **reasoning-based feedback** and correct-answer explanations |
| **ChatAgent** | Per-chapter AI tutor with **persistent session history**, streaming responses via SSE |
| **FlashcardAgent** | Full PDF → Flashcard pipeline with **Anki `.apkg` export** for spaced repetition |
| **ImageAgent** | Generates domain-aware SVG cover images algorithmically (no external API needed) |
| **ValidatedCodeAgent** | Reusable ESLint validation loop — auto-corrects generated JSX up to 5 iterations |

### 📚 PDF-to-Course Pipeline

```
Upload PDFs/Images → PyMuPDF Extraction → ChromaDB Embedding (RAG)
       ↓
PlannerRetrieverAgent → Structured Course Plan (chapters, time, difficulty)
       ↓
  ┌────────────────────────────────┐
  │  Per Chapter (in parallel):    │
  │  • RAG retrieval from PDFs     │
  │  • ExplainerAgent → Visual JSX │
  │  • TesterAgent → Assessments   │
  │  • ImageAgent → Cover SVG      │
  └────────────────────────────────┘
       ↓
Interactive Course with Quizzes, Chat, Notes, Flashcards
```

### 🎯 Bloom's Taxonomy Alignment

| Bloom's Level | How LearnWeave Addresses It |
|:---:|---|
| **Remember** | Flashcard active recall cards (front/back); MCQ questions testing definitions |
| **Understand** | ExplainerAgent generates visual, interactive explanations with concrete examples, diagrams, and LaTeX |
| **Apply** | TesterAgent creates scenario-based questions with interactive visualizations (e.g., "Which function produces this graph?") |
| **Analyze** | Mixed-format assessments force pattern recognition across visual & textual content |
| **Evaluate** | GraderAgent provides rubric-based scoring with detailed reasoning feedback |
| **Create** | Per-chapter AI Chat encourages open-ended exploration and synthesis of concepts |

### 💡 Reasoning-Based Feedback

- **GraderAgent** scores open-text answers (0–2 points) and provides **explanatory feedback** with the correct answer
- Assessments explicitly **"prioritize fostering understanding over memorization"** (built into agent instructions)
- Interactive React-based questions go beyond plain text — students interpret graphs, code, and diagrams

### 🌐 Multilingual / Vernacular Support

- **Backend**: Every agent receives a `language` parameter — course content, explanations, questions, and feedback are all generated in the user's chosen language
- **Frontend**: i18next infrastructure for UI translations with language detector

### 🃏 Flashcard System with Anki Export

- PDF → chapter detection → MCQ & learning card generation → **`.apkg` Anki export**
- Difficulty levels (Easy / Medium / Hard)
- Chunk-based parallel generation for large PDFs
- Styled HTML templates with interactive MCQ

---

## 🛠️ Tech Stack

### Backend

| Layer | Technology |
|-------|-----------|
| **Framework** | [FastAPI](https://fastapi.tiangolo.com/) (Python 3.12) |
| **AI / LLM** | [Google ADK](https://google.github.io/adk-docs/) + Gemini 2.5 Flash, [LiteLLM](https://github.com/BerriAI/litellm) |
| **Vector DB (RAG)** | [ChromaDB](https://www.trychroma.com/) with SentenceTransformers embeddings |
| **Relational DB** | MySQL (SQLAlchemy ORM) |
| **PDF Processing** | PyMuPDF (fitz), pdf2image |
| **Flashcard Export** | genanki (Anki `.apkg`) |
| **Auth** | Google OAuth (Authlib) + JWT (python-jose) |
| **Deployment** | Docker, Docker Compose, Cloud Run, Cloud Build |

### Frontend

| Layer | Technology |
|-------|-----------|
| **Library** | [React 18](https://react.dev/) + [Vite](https://vitejs.dev/) |
| **Styling** | [Tailwind CSS 4](https://tailwindcss.com/) + [Mantine UI](https://mantine.dev/) |
| **Visualization** | Recharts, Plotly.js, react-mermaid-diagram, KaTeX (math) |
| **i18n** | [i18next](https://www.i18next.com/) + react-i18next |
| **Animation** | Motion (Framer Motion successor) |
| **Code Display** | react-code-blocks, react-syntax-highlighter |
| **Routing** | react-router-dom v6 |

---

## 📐 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React + Vite)                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │ Courses  │ │ Quizzes  │ │ Chat AI  │ │  Flashcards   │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬────────┘  │
│       └─────────────┴────────────┴──────────────┘           │
│                          REST API / SSE                     │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                   Backend (FastAPI + Python)                 │
│                                                             │
│  ┌─────────────────── Agent Service ──────────────────────┐ │
│  │                                                        │ │
│  │  PlannerRetriever → Explainer → Tester → Grader        │ │
│  │       ↕                ↕           ↕                   │ │
│  │  ImageAgent      ValidatedCode  ChatAgent              │ │
│  │                  (ESLint loop)  (SSE stream)           │ │
│  │                                                        │ │
│  │         All agents powered by Google ADK               │ │
│  │              + Gemini 2.5 Flash                        │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │    MySQL      │  │   ChromaDB   │  │  FlashcardAgent  │  │
│  │  (users,      │  │  (PDF embed  │  │  (PDF → Anki     │  │
│  │   courses,    │  │   RAG store) │  │   .apkg export)  │  │
│  │   questions)  │  │              │  │                  │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

> **Prerequisites:** Python 3.12+, Node.js (LTS), Docker, MySQL

```bash
# 1. Check all requirements
./scripts/check-requirements.sh

# 2. Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env with your Google Cloud / Gemini API credentials

# 3. Install dependencies
cd backend && pip install -r requirements.txt && cd ..
cd frontend && npm install && cd ..

# 4. Start ChromaDB (vector database)
./scripts/start-chromadb.sh

# 5. Setup MySQL database + tables + admin user
./scripts/setup-db.sh

# 6. Start backend (Terminal 1)
./scripts/start-backend.sh

# 7. Start frontend (Terminal 2)
./scripts/start-frontend.sh
```

| Service | URL |
|---------|-----|
| **Frontend** | http://localhost:3000 |
| **Backend API** | http://localhost:8000 |
| **API Docs (Swagger)** | http://localhost:8000/api/docs |
| **ChromaDB** | http://localhost:8001 |

📖 For detailed setup instructions, see [RUN.md](RUN.md)

---

## 📁 Project Structure

```
learnweave/
├── backend/
│   ├── src/
│   │   ├── agents/               # 🤖 AI Agent implementations
│   │   │   ├── planner_retriever_agent/  # Course planning from PDFs
│   │   │   ├── explainer_agent/          # Interactive JSX explanations
│   │   │   ├── tester_agent/             # Assessment generation
│   │   │   ├── grader_agent/             # Answer grading + feedback
│   │   │   ├── chat_agent/              # Per-chapter AI tutor
│   │   │   ├── flashcard_agent/         # PDF → Anki flashcards
│   │   │   ├── image_agent/             # SVG cover generation
│   │   │   └── tools/                   # Shared agent tools (RAG, etc.)
│   │   ├── api/routers/          # FastAPI route handlers
│   │   ├── services/             # Business logic layer
│   │   ├── db/                   # Database models & CRUD
│   │   ├── core/                 # Auth, security, lifespan
│   │   └── main.py              # Application entry point
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/           # React UI components
│   │   ├── pages/                # Route pages
│   │   ├── contexts/             # React Context providers
│   │   ├── hooks/                # Custom React hooks
│   │   ├── i18n/                 # Internationalization
│   │   ├── api/                  # API client layer
│   │   └── utils/                # Shared utilities
│   ├── package.json
│   └── vite.config.js
├── scripts/                      # Setup & run scripts
├── hackathon/PS.md               # Problem statement
└── README.md
```

---

## 🎯 Hackathon Evaluation Criteria

| Criterion | How LearnWeave Addresses It |
|-----------|---------------------------|
| **Alignment accuracy with learning outcomes** | Multi-agent pipeline maps PDF content → structured chapters → Bloom's-aligned assessments. TesterAgent instructions explicitly target higher-order thinking over recall. |
| **Quality of reasoning-based feedback** | GraderAgent provides rubric-scored (0–2) explanatory feedback. Interactive visual questions (graphs, code, diagrams) test comprehension, not memorization. |
| **Support for vernacular contexts** | Language parameter propagated to every agent — all generated content (explanations, questions, grading) adapts to the user's chosen language. i18next infrastructure on frontend. |

---

## 🗓️ Feature Checklist

- [x] PDF ingestion with RAG (ChromaDB + SentenceTransformers)
- [x] Multi-agent course generation (Google ADK + Gemini 2.5)
- [x] Interactive visual explanations (React/JSX with charts, LaTeX, code)
- [x] Bloom's Taxonomy–aligned assessments (MCQ + open-text)
- [x] Reasoning-based grading with feedback
- [x] Per-chapter AI Chat assistant (SSE streaming)
- [x] Flashcard generation with Anki export
- [x] Multilingual content generation
- [x] Configurable difficulty (Beginner / Intermediate / Advanced)
- [x] ESLint auto-validation loop for generated code
- [x] Google OAuth authentication
- [x] Public course sharing
- [x] Domain-aware SVG cover image generation
- [ ] Progressive hint system (Socratic scaffolding)
- [ ] Explicit Bloom's level tags per question
- [ ] Frontend i18n for regional languages
- [ ] Collaborative course editing

---

## 🧠 Built With

- 🤖 **AI Agents:** [Google ADK](https://google.github.io/adk-docs/) + Gemini 2.5 Flash
- 🔍 **RAG Pipeline:** [ChromaDB](https://www.trychroma.com/) + SentenceTransformers
- ⚡ **Backend:** [FastAPI](https://fastapi.tiangolo.com/) + SQLAlchemy + Docker
- 💻 **Frontend:** React 18 + Vite + Tailwind CSS + Mantine UI
- 📄 **PDF Processing:** PyMuPDF + pdf2image
- 🃏 **Flashcards:** genanki (Anki `.apkg`)
- 📊 **Visualization:** Recharts, Plotly.js, Mermaid, KaTeX

---

## 👥 Team

> Made with 💡 and 🧠 by the **LearnWeave Team**
