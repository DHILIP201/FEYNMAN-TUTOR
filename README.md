# 🎓 The Feynman AI Tutor

> Master complex subjects through the power of teaching.

Built for **HACKHAZARDS '26** — **EdTech & Active Learning Track**

---

## ⚠️ The Problem

Most students rely on passive learning methods such as reading textbooks, highlighting text, and watching lectures.

This often creates the **Illusion of Competence** — the feeling that you understand a topic until exam day arrives and you realize you cannot explain or recall it effectively.

---

## 💡 The Solution

**The Feynman AI Tutor** forces active recall using the famous **Feynman Technique**, a learning method based on explaining concepts in simple language.

Instead of students asking questions to an AI, the AI reads the study material and asks the student questions.

Powered by **Google Gemini 2.5 Flash**, the AI acts as a rigorous yet supportive examiner that focuses on genuine understanding rather than memorization.

### Key Learning Flow

#### 📄 Context Ingestion
Upload any PDF, including:

- Lecture slides
- Class notes
- Textbook chapters
- Study guides

The system extracts the content and treats it as the **ground truth** for the learning session.

#### 🎯 Active Interrogation

The AI asks questions such as:

> "Explain this concept as if you're teaching it to a 5-year-old."

This forces students to actively reconstruct knowledge rather than passively recognize it.

#### 🔍 Analogy Generation

When a student struggles, the AI provides intuitive analogies and hints instead of immediately revealing the answer.

#### 📊 Real-Time Mastery Tracking

A dynamic mastery score updates continuously based on the AI's hidden evaluation of the student's explanations.

---

## 🚀 Features

### 🧠 Persistent Chat Sessions

- Switch seamlessly between different subjects.
- Conversation history is saved locally.
- Mastery scores persist across sessions.
- Data survives server restarts through local storage.

### 🔐 Zero-Friction Authentication

- Lightweight local authentication system.
- User profiles remain tied to study sessions.
- No external authentication provider required.

### 📝 Exam Prep Mode

The AI prompt is optimized specifically for:

- Deep conceptual understanding
- Knowledge gaps detection
- Active recall reinforcement
- Exam readiness assessment

### 🎨 Premium SaaS UI

Built using:

- Raw HTML5
- TailwindCSS
- FastAPI-served frontend

Inspired by the design language of tools like:

- ChatGPT
- Notion

---

## 🛠️ Tech Stack

| Category | Technology |
|-----------|------------|
| Backend | Python, FastAPI |
| AI Engine | Google Gemini 2.5 Flash |
| Document Processing | pypdf |
| Frontend | HTML5, TailwindCSS, Font Awesome, Marked.js |
| Database | SQLite & SQLAlchemy ORM, ChromaDB (Vector Store) |
| Security | JWT (JSON Web Tokens), bcrypt hashing |

---

## 🏁 Running Locally

### 1. Navigate to the Project Directory

```bash
cd 02-feynman-tutor
```

### 2. Activate the Virtual Environment

#### Windows

```bash
venv\Scripts\activate
```

#### macOS / Linux

```bash
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install fastapi uvicorn google-generativeai pypdf python-dotenv pydantic python-multipart sqlalchemy pyjwt bcrypt chromadb
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_api_key_here
```

### 5. Start the Server

```bash
uvicorn main:app --reload
```

### 6. Open the Application

Visit:

```text
http://127.0.0.1:8000/
```

The application will automatically launch in your default browser.

---

## 🔮 Future Roadmap

### 🎙️ Voice-to-Text Learning

Enable students to verbally explain concepts through:

- Speech recognition
- Real-time transcription
- Oral exam simulation
- Hands-free learning sessions

### 📈 Advanced Analytics

Future versions may include:

- Topic-level mastery breakdown
- Learning trend visualization
- Weak-area detection
- Personalized revision plans

---

## 🎯 Why It Works

The Feynman AI Tutor is built on a simple principle:

> **If you can't explain it simply, you don't understand it well enough.**

By transforming passive study sessions into active teaching exercises, students develop stronger comprehension, better retention, and greater exam confidence.

---

### Built with ❤️ for HACKHAZARDS '26