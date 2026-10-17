<div align="center">

# 🧠 RAG-AI — Local Multimodal RAG & Autonomous Coding Assistant

**A 100% local, privacy-first Retrieval-Augmented Generation (RAG) workspace powered by Ollama, ChromaDB, Flask, and React.**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-4.3-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-1.5-FF6446?style=for-the-badge)](https://www.trychroma.com/)
[![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-FFFFFF?style=for-the-badge&logo=ollama&logoColor=black)](https://ollama.com/)

[Features](#-key-features) • [Architecture](#-system-architecture) • [Quick Start](#-quick-start) • [Supported Formats](#-supported-file-formats) • [Configuration](#%EF%B8%8F-configuration--environment-variables) • [API Reference](#-api-reference)

</div>

---

## 📖 Overview

**RAG-AI** is a full-stack local AI workspace that combines **grounded multilingual document Q&A** with an **autonomous software engineering assistant** (inspired by OpenAI Codex & Claude Code). Everything runs locally on your machine via **Ollama** and **ChromaDB**—no external API keys, zero cloud costs, and complete data privacy.

Switch seamlessly between two specialized operational modes in the UI:
1. **💻 Code AI Mode (`code`)**: Upload entire project `.zip` archives, source code files, Jupyter notebooks, or specification documents. Synthesize SQL schemas from raw document data, generate complete production-ready code, refactor modules, and debug with source citations.
2. **📄 Document Analysis Mode (`analysis`)**: Ask questions across PDFs (including scanned documents via automatic OCR), Word documents, and notes. Features strict language-matching rules (**Arabic, French, English**) and inline `[1]`, `[2]` page-aware source citations.

---

## ✨ Key Features

- 🔒 **100% Local & Private**: Powered by local Ollama models for both embeddings (`bge-m3`, `nomic-embed-text`, etc.) and chat completion (`qwen3`, `qwen2.5-coder`, `gemma3`, `deepseek-r1`).
- 🔀 **Dual-Mode Intelligence**:
  - **Code Mode**: Acts as an autonomous software engineer. Automatically extracts entities/tables from documents to generate SQL schemas, full-stack implementations, and scripts—or works standalone without any uploaded files.
  - **Analysis Mode**: Grounded strictly in uploaded excerpts with zero hallucination and automatic query language detection (**English, Français, العربية**).
- 📄 **3-Stage Smart PDF & OCR Pipeline**:
  1. **PyMuPDF (`fitz`)** for rapid native digital PDF extraction.
  2. **pypdf** fallback layer.
  3. **Zero-Poppler OCR Fallback**: Renders scanned/image-only PDFs at 200 DPI via PyMuPDF and runs **Tesseract OCR** (`eng+fra+ara`) with automatic Windows binary discovery.
- 📦 **Codebase & Multi-Format Ingestion**: Supports **60+ file extensions** including `.pdf`, `.docx`, `.ipynb` (Jupyter Notebooks), `.zip` (entire code repositories, auto-filtering `node_modules`/`.git`/binaries), and source files across Python, JS/TS, Go, Rust, C/C++, Java, SQL, and more.
- ⚡ **Real-Time SSE Streaming**: Token-by-token streaming over Server-Sent Events (`text/event-stream`), complete with collapsible reasoning/thinking blocks and instant citation cards.
- 🎛️ **Smart Model Catalog**: Automatically detects installed Ollama models, classifies them into **Code**, **Analysis**, and **Embedding** categories, displays VRAM/disk sizes, and suggests curated `ollama pull` commands.

---

## 🏗️ System Architecture

```mermaid
flowchart LR
    subgraph Frontend ["Frontend (React 19 + Vite + Tailwind v4)"]
        UI["Chat & Mode Switcher\n(Code / Analysis)"]
        Upload["Drag & Drop Uploader"]
        Sidebar["Document Filter Sidebar"]
    end

    subgraph Backend ["Backend (Flask 3.1 REST + SSE)"]
        Loader["Multi-Format Loader\n(PyMuPDF / OCR / DOCX / ZIP / IPYNB)"]
        Chunker["Page-Aware Chunker\n(Unicode Clean + Overlap)"]
        Pipeline["RAG Pipeline\n(Language Detection + Prompt Builder)"]
        Catalog["Model Catalog\n(Auto Capability Discovery)"]
    end

    subgraph Storage ["Local Persistence"]
        SQLite[("SQLite\ndocuments.db")]
        Chroma[("ChromaDB\nVector Store")]
        Disk[("File System\ndata/uploads/")]
    end

    subgraph AI ["Local AI Engine (Ollama)"]
        Embed["Embedding Model\n(bge-m3)"]
        LLM["Chat / Code LLMs\n(qwen2.5-coder / qwen3 / gemma3)"]
    end

    Upload -->|POST /api/documents| Loader
    Loader --> Chunker
    Chunker -->|Batch Embed| Embed
    Embed --> Chroma
    Loader --> SQLite
    Loader --> Disk

    UI -->|POST /api/chat (SSE)| Pipeline
    Sidebar -->|Filter doc_ids| Pipeline
    Pipeline -->|Query Vectors| Chroma
    Pipeline -->|Stream Tokens| LLM
    Catalog <-->|GET /api/tags| AI
```

---

## 📂 Project Structure

```text
RAG-AI/
├── backend/
│   ├── rag/
│   │   ├── chunking.py          # Unicode normalization & overlapping text chunker
│   │   ├── loader.py            # PDF (PyMuPDF + Tesseract OCR), DOCX, IPYNB, ZIP & code parsers
│   │   ├── pipeline.py          # Ingestion, vector retrieval, language detection & prompt engineering
│   │   └── vectorstore.py       # ChromaDB persistent collection wrapper
│   ├── routes/
│   │   ├── chat.py              # /api/chat (SSE stream), /api/models, /api/health
│   │   └── documents.py         # /api/documents CRUD & multipart file upload
│   ├── services/
│   │   ├── document_store.py    # SQLite metadata store for uploaded files
│   │   ├── model_catalog.py     # Ollama model classifier & curated recommendations
│   │   └── ollama_client.py     # Ollama REST client (embeddings, streaming chat, health)
│   ├── app.py                   # Flask application factory & error handlers
│   ├── config.py                # Environment configuration & system prompts
│   └── requirements.txt         # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/          # Composer, DocumentSidebar, Message, ModelPicker, UploadZone
│   │   ├── lib/                 # API client & SSE stream reader
│   │   ├── App.jsx              # Main application state & mode management
│   │   └── main.jsx             # React 19 entry point
│   ├── package.json
│   └── vite.config.js           # Vite dev server with /api proxy to Flask
├── data/
│   ├── chroma/                  # Persistent ChromaDB vector indices
│   ├── uploads/                 # Raw uploaded files
│   └── documents.db             # SQLite document registry
├── reindex_all.py               # Utility script to re-embed all stored documents
└── .env                         # Local environment overrides
```

---

## 🚀 Quick Start

### 1. Prerequisites

- **Python 3.10+**
- **Node.js 18+** & **npm**
- **[Ollama](https://ollama.com/)** installed and running (`ollama serve`)
- *(Optional)* **[Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)** for scanned/image-only PDFs (auto-detected on Windows and PATH)

### 2. Pull Recommended Ollama Models

Open a terminal and pull the default embedding model along with your preferred chat and coding models:

```bash
# Required: Multilingual Embedding Model (100+ languages)
ollama pull bge-m3

# Recommended for Document Analysis (Multilingual Q&A: EN / FR / AR)
ollama pull qwen3:8b
ollama pull gemma3:12b

# Recommended for Code AI Mode
ollama pull qwen2.5-coder:7b
```

### 3. Backend Setup

```bash
# Navigate to the backend directory
cd backend

# Create and activate a virtual environment
python -m venv .venv
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the Flask server (runs on http://127.0.0.1:5000)
python app.py
```

### 4. Frontend Setup

Open a second terminal:

```bash
# Navigate to the frontend directory
cd frontend

# Install dependencies
npm install

# Start the Vite development server (runs on http://localhost:5173)
npm run dev
```

Visit **`http://localhost:5173`** in your browser!

---

## 📁 Supported File Formats

| Category | Extensions / Filenames | Special Handling |
| :--- | :--- | :--- |
| **Documents & Notes** | `.pdf`, `.docx`, `.doc`, `.txt`, `.md`, `.rst`, `.rtf`, `.log` | Page-level tracking for PDFs; table & paragraph extraction for DOCX; automatic Tesseract OCR fallback (`eng+fra+ara`) for scanned PDFs. |
| **Web & Frontend** | `.html`, `.css`, `.scss`, `.js`, `.jsx`, `.ts`, `.tsx`, `.vue`, `.svelte`, `.astro` | Syntax-tagged code chunks for LLM context. |
| **Data Science & Python** | `.py`, `.pyw`, `.ipynb` | Jupyter Notebooks are parsed cell-by-cell into structured `[Cell N - Markdown]` and `[Cell N - Code]` blocks. |
| **Systems & Backend** | `.c`, `.cpp`, `.h`, `.cs`, `.java`, `.kt`, `.scala`, `.go`, `.rs`, `.swift`, `.dart`, `.rb`, `.php`, `.lua`, `.r`, `.sh`, `.ps1` | Automatic character encoding detection (UTF-8, UTF-16, CP1252, Arabic/non-Latin charsets). |
| **Data, Config & Schemas** | `.sql`, `.cql`, `.graphql`, `.prisma`, `.json`, `.yaml`, `.toml`, `.xml`, `.csv`, `.tsv`, `.env`, `.ini`, `Dockerfile`, `Makefile` | Direct schema & data synthesis support in Code Mode. |
| **Project Archives** | `.zip` | Extracts all source/text files into a unified codebase manifest while automatically ignoring `node_modules`, `.git`, `.venv`, `__pycache__`, `dist`, and binaries. |

---

## ⚙️ Configuration & Environment Variables

Create or edit the `.env` file in the project root to customize behavior:

```ini
# --- Server ---
HOST=127.0.0.1
PORT=5000
FLASK_DEBUG=0
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:5173

# --- Ollama Models & Inference ---
OLLAMA_HOST=http://localhost:11434
CHAT_MODEL=qwen3:8b
EMBED_MODEL=bge-m3
LLM_THINK=false
LLM_TEMPERATURE=0.2
LLM_CONTEXT_WINDOW=8192
MAX_HISTORY_TURNS=6

# --- RAG Chunking & Retrieval ---
CHUNK_SIZE=1200
CHUNK_OVERLAP=200
TOP_K=5
MAX_UPLOAD_MB=32
```

### 🔄 Switching Embedding Models & Re-indexing

Each embedding model uses its own isolated ChromaDB collection (`rag_<embed_model>`) so vector dimensions never clash. If you change `EMBED_MODEL` in `.env`, run the included utility script to re-index all previously uploaded documents:

```bash
python reindex_all.py
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api` | Service index and list of available routes. |
| `GET` | `/api/health` | Health status of Flask, Ollama connection, active models, and document count. |
| `GET` | `/api/models` | Lists installed Ollama models grouped by capability (`code_chat`, `analysis_chat`, `embedding`) plus curated recommendations. |
| `GET` | `/api/documents` | Lists all uploaded documents with chunk counts, page counts, and indexing status. |
| `POST` | `/api/documents` | Uploads and indexes a file (`multipart/form-data` with field `file`). |
| `GET` | `/api/documents/<id>` | Retrieves metadata and indexed chunk count for a single document. |
| `DELETE` | `/api/documents/<id>` | Deletes a document from SQLite, removes its vectors from ChromaDB, and deletes the file from disk. |
| `POST` | `/api/chat` | Streams an answer via **Server-Sent Events (SSE)**. Emits `sources`, `delta`, `error`, and `done` events. |

### Example `/api/chat` Request Payload

```json
{
  "question": "Generate PostgreSQL tables for all regions and departments mentioned in the protocol document.",
  "mode": "code",
  "model": "qwen2.5-coder:7b",
  "document_ids": ["69a9685a6fe848c7ac62bb74e5a2572f"],
  "history": [
    { "role": "user", "content": "What entities are in the document?" },
    { "role": "assistant", "content": "The document lists regional branches and departments..." }
  ]
}
```

---

## 📄 License

This project is open-source and available under the **MIT License**.
