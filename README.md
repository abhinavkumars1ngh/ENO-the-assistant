# ENO — Local-First AI Assistant 🧠⚡

[![Next.js](https://img.shields.io/badge/Next.js-black?style=flat&logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Apple MLX](https://img.shields.io/badge/Apple_MLX-000000?style=flat&logo=apple&logoColor=white)](https://github.com/ml-explore/mlx)
[![Qdrant](https://img.shields.io/badge/Qdrant-E2104C?style=flat&logo=qdrant&logoColor=white)](https://qdrant.tech/)

A local-first AI assistant built around on-device LLM inference, real-time streaming, voice interaction, retrieval, and web search.

ENO is an AI assistant designed to keep the core intelligence and data pipeline local instead of relying entirely on cloud-hosted AI APIs. It combines locally running Gemma and Qwen models, Apple MLX, Whisper-based speech recognition, Qdrant, Redis, and a FastAPI/WebSocket backend with a remotely accessible Next.js frontend.

The goal is simple: **build an assistant where I have control over the models, inference pipeline, memory, tools, and infrastructure instead of treating an LLM API as a black box.**

---

## 🏗 Architecture

The system is split into three major layers:

```text
                         ┌──────────────────────┐
                         │      User Device     │
                         │   Browser / Phone    │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Next.js Frontend   │
                         │ React + TypeScript   │
                         │      Tailwind        │
                         └──────────┬───────────┘
                                    │
                              WebSocket / API
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │       ngrok          │
                         │   Secure Tunnel      │
                         └──────────┬───────────┘
                                    │
                                    ▼
                    ┌──────────────────────────────┐
                    │       FastAPI Backend        │
                    │     Main Orchestration       │
                    └──────────────┬───────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
       ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
       │ Gemma / Qwen│      │   Qdrant    │      │    Redis    │
       │    + MLX    │      │  Retrieval  │      │ State/Cache │
       └─────────────┘      └─────────────┘      └─────────────┘
              │                    │
              ▼                    ▼
       Local Inference       Memory / RAG
              │
              ├──────────────────────┐
              ▼                      ▼
        ┌─────────────┐       ┌─────────────┐
        │   Whisper   │       │ DuckDuckGo  │
        │ Speech→Text │       │ Web Search  │
        └─────────────┘       └─────────────┘
```

### Request Flow
A typical text request follows this path:

`User` → `Next.js UI` → `WebSocket` → `ngrok` → `FastAPI` → `Conversation / Context` → `Qdrant Retrieval` → `Gemma or Qwen via MLX` → `Token Streaming` → `WebSocket` → `Next.js UI`

When external information is required, the backend can additionally use DuckDuckGo Lite as a web-search tool. For voice input, audio is processed through the local Whisper pipeline before being passed into the normal assistant workflow.

---

## 🛡 Why Local-First?

ENO was built around a simple question: **What if the assistant didn’t need to send every piece of context to a cloud AI provider?**

Instead of making the backend dependent on a hosted inference API, ENO loads locally available model weights and performs inference entirely on the machine. This gives complete, unmetered control over:

* Which model is being used
* Model quantization
* Inference configuration
* Context construction & Retrieval
* Conversation state & Tool usage
* Data storage & Network boundaries

On Apple Silicon, ENO utilizes **Apple MLX** to make local inference practical and blazing fast, alongside **4-bit quantized model weights** to drastically reduce memory requirements.

---

## 🧩 Core Components

### 🖥 Frontend (Next.js + React + TypeScript + Tailwind CSS)
The frontend provides the interaction layer for ENO. It handles the chat interface, real-time streaming responses, markdown rendering (with code blocks), assistant mode selection (Standard vs. Bro), WebSocket communication, and voice interaction UI. The frontend is deployed independently through Vercel.

### ⚙️ Backend (Python + FastAPI)
FastAPI is the central orchestration layer. Rather than having the frontend communicate directly with every service, requests flow through the backend, which coordinates conversation processing, prompt construction, model selection, local inference, retrieval, web search, voice processing, and application state. This keeps the frontend blissfully unaware of the complex AI pipeline underneath.

### 🧠 Local LLM Inference
ENO currently supports natively locally hosted models including **Gemma 2** and **Qwen**. Inference is handled using Apple MLX on Apple Silicon. Models are explicitly excluded from the Git repository due to their massive size; they are dynamically loaded into unified memory by the backend.

### 🗜 Quantization
Running massive LLMs locally creates an immediate memory bottleneck. To make this practical on edge hardware, ENO uses **4-bit quantized variants** (e.g., `gemma-2-2b-it-4bit`). This slashes the memory footprint down to ~1.6GB, keeping local inference snappy and leaving room for the Vector DB and OS.

### 🗄 Memory & Retrieval (Qdrant & Redis)
* **Qdrant:** Provides the vector storage layer for RAG (Retrieval-Augmented Generation). Conversations and coding styles are embedded as vectors. When a new query arrives, relevant historical context is retrieved via Cosine Similarity and injected into the LLM prompt.
* **Redis:** Used for fast transient application state and supporting backend operations, allowing Qdrant to focus strictly on semantic retrieval.

### 🎙 Voice
ENO supports voice interaction through a fully local speech-processing pipeline using **Whisper**.
`Microphone` → `Audio` → `Whisper` → `Text Transcript` → `Normal ENO Pipeline`

### 🌐 Web Search
ENO can break out of its local bounds using DuckDuckGo Lite. The assistant smartly distinguishes between its *Local Knowledge* and *Web Search*, preventing it from being strictly limited to its localized parametric memory.

### ⚡ Real-Time Streaming
Instead of forcing the user to wait for the entire response to generate, ENO streams the output out of the LLM token-by-token.
`LLM` → `FastAPI` → `WebSocket` → `Next.js Frontend`

---

## 🛠 Project Orchestration

ENO contains a robust startup/orchestration script (`start_project.py`) that brings the entire multi-service stack together. Instead of manually starting 5 different terminals, this single Python script orchestrates:

* **FastAPI** (Backend)
* **Next.js** (Frontend)
* **ngrok** (Secure Tunneling)
* **Qdrant** (Vector DB - Docker or Local Fallback)
* **Redis** (State)
* **Celery** (Background workers)

It dynamically checks for Docker, routes to local fallbacks if needed, and gracefully handles OS-level port cleanup and shutdown on `Ctrl+C`.

---

## 📂 Repository Structure

```text
ENO/
├── frontend/             # Next.js UI
│   ├── app/
│   ├── components/
│   └── package.json
│
├── backend/              # FastAPI Backend
│   ├── api/
│   │   └── websockets.py
│   ├── services/
│   │   └── llm_service.py
│   └── core/
│       └── qdrant_setup.py
│
├── start_project.py      # The Master Orchestrator
├── requirements.txt
├── .gitignore
└── README.md
```

### What Stays Local?
Some components are deliberately excluded from Git via `.gitignore`:
* **Model Weights:** `mlx_models/`, `qwen_local_weights/`, `whisper-tiny-mlx/` (Massive `.safetensors` files)
* **Qdrant Storage:** `storage/qdrant/` (Generated binary database segments)
* **Dependencies:** `venv312/`, `node_modules/` (Platform-specific bloat)

---

## 🚀 Current State & Roadmap

ENO is an actively developing experiment in understanding end-to-end AI systems.

**Working / Implemented:**
- [x] Local LLM inference (Apple MLX)
- [x] Dual-model support (Gemma / Qwen)
- [x] 4-bit Quantized inference
- [x] Real-time WebSocket token streaming
- [x] Local Voice input (Whisper)
- [x] Vector storage / RAG (Qdrant)
- [x] Redis state integration
- [x] Web search (DuckDuckGo Lite)
- [x] Multi-service automated orchestration
- [x] Remote frontend → local backend Ngrok workflow

**In Progress:**
- [ ] Robust document ingestion (PDFs → chunks → embeddings → Qdrant)
- [ ] Improved multi-hop RAG pipeline
- [ ] Expanded function-calling and tool integrations
- [ ] Robust deployment/build workflow

---

## 🛠 Tech Stack

| Layer | Technology |
| :--- | :--- |
| **Frontend** | Next.js, React, TypeScript, Tailwind CSS |
| **Backend** | Python, FastAPI |
| **Communication** | WebSockets |
| **Local AI** | Gemma 2 (2B), Qwen |
| **Inference Framework** | Apple MLX |
| **Optimization** | 4-bit Quantization |
| **Speech-to-Text** | Whisper |
| **Vector Database** | Qdrant |
| **State / Cache** | Redis |
| **Web Search** | DuckDuckGo Lite |
| **Tunneling** | ngrok |
| **Frontend Hosting** | Vercel |
| **Orchestration** | Python (`start_project.py`) |

---

## 🤔 Why I Built It

I wanted to understand what actually happens between **"I send a message"** and **"the AI responds."** 

Building ENO forced me to deal with every single layer in between: model loading, hardware memory limits, quantization, semantic retrieval, WebSockets, streaming buffers, service orchestration, local networking, voice processing, and web tools. 

ENO is less about building another chat interface and more about building an ecosystem where **every layer is something I can inspect, modify, and experiment with.** That is the main reason I built ENO this way.
