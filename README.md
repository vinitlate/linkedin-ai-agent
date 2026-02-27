# 🚀 LinkedIn Value-First AI Agent

A multi-agent system that turns weekly AI/Data Engineering trends into educational LinkedIn posts — optimized for clarity, practicality, and value (not hype).

Built with:
- Python
- Streamlit
- OpenAI API
- RSS ingestion + clustering
- Structured agent memory

---

## 🧠 Why This Exists

Most “AI trend posts” are just summaries.

This system does something different:

1. Ingests weekly AI + Data Engineering signals (RSS feeds)
2. Clusters related topics
3. Ranks them by signal strength (recency + frequency + relevance)
4. Uses an LLM to select the most *teachable* topic
5. Generates a structured LinkedIn post:
   - Hook  
   - Problem  
   - Insight  
   - Example  
   - Takeaway  
   - Question  

**Goal:**  
Produce posts that help junior engineers understand systems — not just news.

---

## 🏗 Architecture
RSS Feeds
↓
Trend Agent
- Fetch headlines
- Cluster similar topics
- Score by signal
- LLM selects most teachable topic
↓
Content Agent
- Plan post (structured JSON)
- Write post draft
- Optional compression
↓
Streamlit UI
- Model selection
- Profile editing
- Feedback loop
↓
Memory (JSON)
- History
- Feedback
- Profile settings


---

## 🔄 Multi-Agent Design

### 1️⃣ Trend Agent
- Fetches AI / ML / Data Engineering RSS feeds
- Clusters topics via fuzzy matching
- Scores clusters using:
  - Frequency
  - Recency decay
  - Source weighting
  - Keyword relevance
- Uses selected model to pick the most educational topic

### 2️⃣ Content Agent
- Generates structured post plan
- Writes LinkedIn draft
- Optionally compresses to ~180 words
- Logs everything to memory

### 3️⃣ Shared LLM Layer
- Single OpenAI client
- Model selected in UI is used everywhere
- Meta logging of actual model used

---

## 🛠 Features

- ✅ Weekly trending AI topic detection
- ✅ Value-first filtering (not just hype)
- ✅ Structured content generation
- ✅ Editable creator profile
- ✅ Memory persistence
- ✅ Feedback loop
- ✅ Dynamic model selection
- ✅ Multi-model compatibility

---

## ⚙️ Setup

### 1️⃣ Clone the repo

```bash
git clone git@github.com:yourusername/linkedin-ai-agent.git
cd linkedin-ai-agent
```
### 2️⃣ Create virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```
### 3️⃣ Install dependencies

If using a requirements file:
```bash
pip install -r requirements.txt
```
Or manually:
```bash
pip install streamlit openai python-dotenv feedparser rapidfuzz
```
### 4️⃣ Create .env
```bash
OPENAI_API_KEY=your_api_key_here
```
### 5️⃣ Run the app
```bash
streamlit run app.py
```

## 🧩 Model Strategy

### The model selected in the UI is used for:
- Trend topic selection
- Post planning
- Writing
- Compression

### Metadata logs:
- Requested model
- Plan model
- Write model
- Compression model
- Trend model

## 📊 Example Output

“If you want LLMs to work at terabytes-of-logs scale, don’t scale the prompt — scale the data model.”

The system doesn’t summarize headlines.
It reframes trends into practical system lessons.

## 📂 Project Structure
```bash
├── app.py
├── agent_core.py
├── trend_agent.py
├── openai_shared.py
├── agent_memory.json
├── .env
├── .gitignore
└── README.md
```

## 🧠 Design Philosophy

- News is a hook.
- Value is clarity.
- LLMs are interfaces to structured systems.
- Production thinking > prompt hacking.

## 🚀 Future Improvements

- Semantic clustering instead of fuzzy matching
- Trend scoring based on engagement signals
- Database-backed memory instead of JSON
- Cost + latency tracking
- Automated weekly scheduling
- Vector-based feedback learning
- Docker deployment
