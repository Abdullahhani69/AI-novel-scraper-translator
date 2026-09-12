# 📚 AI-Powered Novel Scraper & Translator

An automated Python pipeline for extracting Chinese web-novel chapters and translating them into polished English using local and cloud-based LLMs.

The project combines **web scraping, browser automation, NLP/LLM translation, terminology control, quality validation, progress tracking, and batch processing** into a single workflow.

---

## ✨ Features

- 🌐 Automated web-novel chapter scraping
- 🔎 HTML parsing with BeautifulSoup
- 🌐 Browser automation with Playwright
- 🤖 LLM-powered translation
- 🧠 Local translation using Ollama
- ⚡ Cloud-based translation/polishing using Groq
- 📖 Custom translation glossary
- ✂️ Automatic text chunking for large chapters
- ✅ Translation quality validation
- 💾 Automatic progress tracking and resume support
- 🔄 Retry handling for failed chapters
- ⚙️ Multiple translation backends
- 🚀 Batch chapter processing
- 📄 Consolidated English output

---

## 🏗️ Pipeline

```text
Chinese Novel Website
        │
        ▼
   Web Scraper
        │
   ┌────┴────┐
   │         │
Requests  Playwright
   │         │
   └────┬────┘
        ▼
   HTML Parser
  (BeautifulSoup)
        │
        ▼
  Clean Chapter Text
        │
        ▼
   Text Chunking
        │
        ▼
 ┌───────────────────────┐
 │   Translation Layer   │
 │                       │
 │ Ollama → Groq Polish  │
 │ Groq                  │
 │ DeepL                 │
 │ Ollama                │
 └───────────┬───────────┘
             │
             ▼
    Post-Processing
             │
             ▼
   Quality Validation
             │
             ▼
     Save Translation
             │
       ┌─────┴─────┐
       ▼           ▼
 Individual     Combined
 Chapters        Output

 | Technology         | Purpose                         |
| ------------------ | ------------------------------- |
| Python             | Core application                |
| Requests           | HTTP requests                   |
| BeautifulSoup      | HTML parsing                    |
| Playwright         | Browser automation              |
| Ollama             | Local LLM translation           |
| Groq API           | Cloud LLM translation/polishing |
| DeepL API          | Alternative translation backend |
| JSON               | Progress/configuration data     |
| ThreadPoolExecutor | Concurrent processing           |


📖 Glossary System

The project includes a custom terminology glossary to maintain consistency across chapters.

For example:

陈然       → Chen Ran
秋意浓     → Qiu Yinong
时间之轮   → Wheel of Time
杀谎者     → Lie Slayer
诡语者     → Deceiver

This helps prevent terminology from changing between chapters.

🔄 Progress & Resume System

Long-running translation jobs can be interrupted.

The pipeline maintains a progress file containing:

Completed chapters
Failed chapters
Chapters currently being processed
Chapters requiring review

This allows processing to resume without unnecessarily repeating completed work.

⚙️ Supported Translation Backends

The project supports multiple translation configurations:

Ollama
Groq
DeepL
Ollama → Groq Polish

The backend can be selected through configuration.

🚀 Installation
1. Clone the repository
git clone https://github.com/Abdullahhani69/ai-novel-scraper-translator.git
cd ai-novel-scraper-translator
2. Create a virtual environment
python -m venv venv

Activate it on Windows:

venv\Scripts\activate

On Linux/macOS:

source venv/bin/activate
3. Install dependencies
pip install -r requirements.txt
4. Install Playwright browser
playwright install chromium

▶️ Usage

Configure the desired chapter range in the script and run:

python scraper_translator.py

The pipeline will:

Download chapters
Clean the extracted content
Split chapters into manageable chunks
Translate the content
Apply glossary and terminology rules
Polish the translation when configured
Validate the result
Save individual translated chapters
Append chapters to the consolidated output
Track processing progress

📁 Generated Output

The application creates:

chapters_raw/
    ├── 197.txt
    ├── 198.txt
    └── ...

chapters_translated/
    ├── chapter_197_en.txt
    ├── chapter_198_en.txt
    └── ...

translation_progress.json

A consolidated English translation can also be generated.

⚠️ Responsible Use

This project is intended as a demonstration of:

Web scraping
Automation
NLP
LLM integration
Machine translation
Data processing

Users should respect the terms of service, copyright, robots.txt, and applicable laws of websites and content they access.

🎯 Future Improvements
 Web-based interface
 Automatic chapter discovery
 Translation caching
 Better retry and rate-limit handling
 Translation quality scoring
 Database-backed progress tracking
 Docker deployment
 Automatic EPUB generation
 Translation memory
 Multi-language support

 👨‍💻 Author

Abdullah Hani

Computer Science graduate interested in:

Data Analytics • AI/ML • Data Engineering • Web Scraping • Automation
