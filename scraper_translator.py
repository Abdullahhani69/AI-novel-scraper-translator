import re
import os
import time
import json
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime


# =========================
# CONFIG
# =========================

BOOK_ID = "564986"
BASE_URL = f"https://ixdzs8.com/read/{BOOK_ID}/p{{chapter}}.html"

RAW_DIR = Path("chapters_raw")
EN_DIR = Path("chapters_translated")
CONSOLIDATED_FILE = EN_DIR / "all_chapters_en.txt"
PROGRESS_FILE = Path("translation_progress.json")

RAW_DIR.mkdir(exist_ok=True)
EN_DIR.mkdir(exist_ok=True)

# =========================
# TRANSLATION BACKEND SELECTION
# =========================
# Choose your translation backend:
# 1. "ollama" - Local, free, no API key needed
#    Requires: ollama serve running
# 2. "groq" - FREE, fastest, ChatGPT-quality
#    Get free API key at: https://console.groq.com
# 
# 3. "ollama_groq_polish" - Ollama creates the draft, Groq polishes it
# 4. "deepl" - FREE tier (500K chars/month), excellent quality
#    Get free API key at: https://www.deepl.com/pro-api

TRANSLATION_BACKEND = os.getenv("TRANSLATION_BACKEND", "ollama_groq_polish")

# Groq API (Free tier) - set GROQ_API_KEY in your environment if you use it.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# DeepL API (Free tier: 500K chars/month) - Get key from https://www.deepl.com/pro-api
DEEPL_API_KEY = ""  # Set your key here or use environment variable

# Ollama (Local, free, requires ollama running)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "4096"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "5000"))
TRANSLATION_CHUNK_SIZE = int(os.getenv("TRANSLATION_CHUNK_SIZE", "1200"))

# Concurrent processing settings
MAX_WORKERS = 2  # Number of concurrent chapter downloads (be careful not to hammer the server)
USE_BROWSER = True  # Set to True if site requires JavaScript rendering (needed for security verification)

# Your current translation style preferences.
# Calibrated against the chapter-186 sample style the reader preferred.
TRANSLATION_STYLE = """You are translating a Chinese psychological thriller web novel into polished English fiction.

Target style:
- Natural, fluent English like a professionally edited novel chapter.
- Short, clear thriller sentences when tension rises.
- Preserve strategic reasoning, suspicion, and internal calculations.
- Do not sound literal, machine translated, or explanatory.
- Do not summarize, condense, add commentary, or skip any line.

CRITICAL TRANSLATION RULES:
1. Translate EVERY line - do NOT summarize or skip anything
2. Chinese inner thoughts may appear as 【...】 or [...]. Translate them as separate [square bracket] lines.
3. Preserve all dialogue exactly with proper quotes
4. Use character and skill names from the glossary EXACTLY
5. Use technical terms from the glossary EXACTLY
6. Use natural English while preserving original meaning
7. Maintain the thriller/psychological tone
8. Do not put ordinary narration inside square brackets
9. Preserve paragraph structure and scene breaks
10. Do not add any translator notes or explanations
11. Do not add a trailing chapter-number footer

FORMATTING:
- Dialogue: "Character dialogue here."
- Inner thought: [Character's internal reasoning.] Only use this when the source has bracketed/inner-thought text.
- Action: Character did something.
- Skill/ability names must match the glossary exactly.

CHARACTER VOICE AND PRONOUNS:
- Chen Ran: male, analytical and calm.
- Qiu Yinong: female, controlled, exhausted when using Wheel of Time.
- Duo Jie: male.
- Diwu Zeyi: male.
- Long Hui: male.

GLOSSARY DISCIPLINE:
- Never use variants such as "Time Wheel" for "Wheel of Time".
- Never use "Sophist" if the glossary says "Deceiver".
- Never use "Lie-Killer" if the glossary says "Lie Slayer".
- Keep ability names exact.

TONE: Intellectual, strategic, dark thriller atmosphere.
"""

POLISH_STYLE = """You are a senior English fiction editor polishing a Chinese-to-English web novel translation.

Your job:
- Use the Chinese source only to verify meaning and catch omissions.
- Polish the English draft into natural, flowing novel prose like the approved Chapter 186 style.
- Preserve every event, dialogue line, reasoning step, and paragraph beat.
- Keep the psychological thriller tone: calm, tense, strategic, and readable.
- Keep inner thoughts in [square brackets] only where the source/draft has inner thoughts.
- Fix awkward literal phrasing, wrong pronouns, wrong names, glossary drift, and incomplete sentences.
- Do not summarize, add commentary, explain your edits, or include notes.
- Output only the polished English translation.

Hard glossary rules:
- 陈然 = Chen Ran
- 秋意浓 = Qiu Yinong
- 第五择一 = Diwu Zeyi
- 龙回 = Long Hui
- 多杰 = Duo Jie
- 李知童 = Li Zhitong
- 张美丽 = Zhang Meili
- 时间之轮 = Wheel of Time
- 颠三倒四 = Reversing and Confusing the Order
- 三缄其口 = Three Seals of Silence
- 帝出三江 = Emperor Emerges from Three Rivers
- 黑色生命力 = Black Vitality
- 杀谎者 = Lie Slayer
- 诡语者 = Deceiver
- 密室 = locked room
- 副本 = instance
- 审判 = judgment
- 谎言 = lie
- 说谎 = lying
"""

GLOSSARY = {
    # =========================
    # Main Characters
    # =========================
    "陈然": "Chen Ran",
    "秋意浓": "Qiu Yinong",
    "第五择一": "Diwu Zeyi",
    "龙回": "Long Hui",
    "多杰": "Duo Jie",
    "李知童": "Li Zhitong",
    "张美丽": "Zhang Meili",

    # =========================
    # General World Terms
    # =========================
    "地狱": "hell",
    "十八层地狱": "Eighteen Levels of Hell",
    "玩家": "player",
    "三星玩家": "three-star player",
    "高星玩家": "high-star player",
    "一星": "one-star",
    "二星": "two-star",
    "三星": "three-star",
    "四星": "four-star",
    "五星": "five-star",
    "真我": "True Self",
    "真我级": "True Self-level",
    "真我级玩家": "True Self-level player",
    "副本": "instance",
    "副本BOS": "instance boss",
    "BOS": "boss",
    "密室": "locked room",
    "第一个密室": "the first locked room",
    "第二个密室": "the second locked room",
    "第三个密室": "the third locked room",
    "时间线": "timeline",
    "初始时间线": "initial timeline",
    "新时间线": "new timeline",
    "当前时间线": "current timeline",
    "第N个时间线": "the Nth timeline",
    "时间重置": "time reset",
    "重置时间": "reset time",
    "轮回": "loop",
    "重置": "reset",
    "技能": "ability",
    "技能效果": "ability effect",
    "效果": "effect",
    "第一个效果": "first effect",
    "第二个效果": "second effect",
    "延伸效果": "extended effect",
    "特殊技能": "special ability",
    "普通技能": "ordinary ability",
    "口令": "activation phrase",
    "技能口令": "ability activation phrase",
    "点数": "points",

    # =========================
    # Factions / Roles
    # =========================
    "杀谎者": "Lie Slayer",
    "杀谎者联盟": "Lie Slayer Alliance",
    "诡语者": "Deceiver",
    "诡语者联盟": "Deceiver Alliance",

    # =========================
    # Lie System Terms
    # =========================
    "说谎": "lying",
    "说谎者": "liar",
    "谎言": "lie",
    "骗谎": "lie-baiting",
    "判谎": "lie-judgment",
    "审判": "judgment",
    "审判成功": "successful judgment",
    "审判失败": "failed judgment",
    "客观判谎": "objective lie-judgment",
    "主观判谎": "subjective lie-judgment",
    "客观说谎": "objective lying",
    "主观说谎": "subjective lying",
    "未知谎言": "unknown lie",
    "常识谎言": "common-sense lie",
    "未来谎言": "future lie",
    "情绪说谎": "emotional lying",
    "常识说谎": "common-sense lying",
    "情感说谎": "sentimental lying",
    "未知说谎": "unknown lying",
    "禁止跨时间审判": "cross-time judgment is forbidden",
    "跨时间审判": "cross-time judgment",
    "红线": "red line",
    "陷阱": "trap",
    "骗局": "trap",
    "把戏": "trick",
    "布局": "setup",
    "破局": "break the game",
    "反制": "countermeasure",
    "心理反制": "psychological countermeasure",
    "反向推理": "reverse reasoning",
    "正向推理": "forward reasoning",
    "底层逻辑": "underlying logic",
    "逻辑": "logic",
    "过程": "process",
    "结果": "result",
    "推理": "reasoning",
    "密室推理": "locked-room deduction",
    "常识": "common sense",
    "客观事实": "objective fact",
    "未知信息": "unknown information",
    "未知": "unknown",
    "已知": "known",
    "确定": "confirm",
    "判断": "judge",
    "赌": "gamble",
    "赌赢": "win the gamble",
    "赌输": "lose the gamble",

    # =========================
    # Deception / Language Terms
    # =========================
    "诡语": "deceptive speech",
    "语言诡语": "linguistic deception",
    "诡语形成": "deception forms",
    "诡语被破": "deception is broken",
    "语言陷阱": "language trap",
    "话术": "wording strategy",
    "骗谎话术": "lie-baiting wording",
    "引导": "guide",
    "诱导": "lead",
    "嫁接": "graft",
    "明牌": "open-card",
    "明牌打法": "open-card playstyle",

    # =========================
    # Important Abilities
    # =========================
    "时间之轮": "Wheel of Time",
    "杀谎者·时间之轮": "Lie Slayer: Wheel of Time",

    "颠三倒四": "Reversing and Confusing the Order",
    "杀谎者·颠三倒四": "Lie Slayer: Reversing and Confusing the Order",

    "帝出三江": "Emperor Emerges from Three Rivers",
    "杀谎者·帝出三江": "Lie Slayer: Emperor Emerges from Three Rivers",

    "三缄其口": "Three Seals of Silence",
    "杀谎者·三缄其口": "Lie Slayer: Three Seals of Silence",

    "黑色生命力": "Black Vitality",

    # =========================
    # Ability Mechanics
    # =========================
    "记忆锚点": "memory anchor",
    "标记记忆锚点": "mark a memory anchor",
    "标记": "mark",
    "锚点": "anchor",
    "保留记忆": "retain memories",
    "丧失记忆": "lose memories",
    "失忆": "lose memories",
    "不会失忆": "will not lose memories",
    "记忆恢复": "memory recovery",
    "接收记忆": "receive memories",
    "大量记忆": "massive amount of memories",
    "强化": "strengthen",
    "削弱": "weaken",
    "掌控": "control",
    "控制": "control",
    "收回技能": "withdraw the ability",
    "使用技能": "use the ability",
    "技能结束": "ability ends",
    "技能拥有者": "ability owner",
    "零帧起手": "zero-frame activation",
    "持续时间": "duration",
    "枪口指向": "point the gun at",
    "拔枪": "draw the gun",
    "出枪": "draw/fire the gun",
    "举枪指顶": "raise the gun and aim it at one's own head",
    "开枪": "fire",
    "枪声": "gunshot",
    "子弹": "bullet",

    # =========================
    # True Self / Corpse System
    # =========================
    "一尸": "corpse",
    "完整一尸": "complete corpse",
    "情绪一尸": "emotional corpse",
    "斩出一尸": "cut out a corpse",
    "斩出完整一尸": "cut out a complete corpse",
    "心理防线": "psychological defense",
    "击溃心理防线": "break down the psychological defense",
    "镇压情绪": "suppress emotions",
    "绝对理智": "absolute rationality",
    "精神攻击": "mental attack",
    "精神虚脱": "mental exhaustion",
    "大脑过载": "brain overload",
    "脑损伤": "brain damage",
    "高负荷": "high load",

    # =========================
    # Arcs / Instances
    # =========================
    "新手教程副本": "beginner tutorial instance",
    "牧狼羊副本": "shepherd-wolf-sheep instance",
    "孤独的复仇副本": "lonely revenge instance",
    "百诡盛宴": "Feast of a Hundred Ghosts",

    # =========================
    # Chapter Titles / Scene Titles
    # =========================
    "上一章": "Previous Chapter",
    "下一章": "Next Chapter",
    "书籍页": "Book Page",
    "三座大山": "Three Great Mountains",
    "心战": "Psychological Warfare",
    "心战（一）": "Psychological Warfare (1)",
    "心战（二）": "Psychological Warfare (2)",
    "心战（三）": "Psychological Warfare (3)",
    "抓到狗了": "Caught the Dog",
    "落下帷幕": "The Curtain Falls",
    "最终对决": "final showdown",
    "拉开序幕": "begins",
    "第二个密室最终对决拉开序幕": "The Final Showdown of the Second Locked Room Begins",
    "两百次轮回，只为杀你": "Two Hundred Loops, Just to Kill You",
    "第三个密室": "The Third Locked Room",

    # =========================
    # Common Reasoning / Battle Phrases
    # =========================
    "同归于尽": "mutual destruction",
    "威慑": "deterrence",
    "上帝视角": "God's-eye view",
    "极限推理": "extreme reasoning",
    "心战": "psychological battle",
    "心理战": "psychological warfare",
    "将计就计": "turn the scheme back on them",
    "死循环": "dead loop",
    "备选方案": "backup plan",
    "方案": "plan",
    "计划": "plan",
    "漏洞": "loophole",
    "缺陷": "flaw",
    "破绽": "opening",
    "打断": "interrupt",
    "喝止": "shout to stop",
    "提醒": "reminder",
    "提示": "hint",
    "复盘": "review",
    "总结": "summarize",
    "推敲": "scrutinize",
    "验证": "verify",
    "实验": "test",
    "结论": "conclusion",
    "前提": "premise",
    "线索": "clue",
    "证实": "confirm",
    "排除": "rule out",
    "锁定": "lock onto",
    "怀疑": "suspicion",
    "嫌疑": "suspicion",
    "机会": "opportunity",
    "时间差": "time gap",
    "动作": "action",
    "第一个动作": "first action",
    "第二个动作": "second action",

    # =========================
    # Novel / Author Flashback Terms
    # =========================
    "小说作者": "novelist",
    "编辑": "editor",
    "大纲": "outline",
    "章节": "chapter",
    "修改章节": "revise the chapter",
    "码字": "write",
    "卡文": "writer's block",
    "卡文经验": "writer's block experience",
    "读者": "readers",
    "追更": "follow the update",
    "后台": "backend",
    "评论": "comments",
    "剧情": "plot",
    "主角": "protagonist",
    "太子": "crown prince",
    "皇帝": "emperor",
    "老皇帝": "old emperor",
    "皇位": "throne",
    "登上皇位": "ascend the throne",
    "传位顺序": "order of succession",
    "底层逻辑": "underlying logic",
    "王朝末期": "final years of the dynasty",
    "幽州": "Youzhou",
    "发配幽州": "send to Youzhou",
    "反贼": "rebels",
    "国都": "capital",
    "诸侯争霸": "feudal lords fight for supremacy",
    "世家贵族": "aristocratic families",
    "地主豪绅": "landed gentry and local tyrants",
    "大洗牌": "massive reshuffling",
    "振臂一呼": "raise his arm and call",
    "朱棣": "Zhu Di",
    "朱高炽": "Zhu Gaochi",
    "李唐皇室": "Li-Tang imperial clan",
    "朱明皇室": "Zhu-Ming imperial clan",
    "好圣孙": "good imperial grandson",
    "刘秀": "Liu Xiu",
    "再造大汉": "restore the Han",

    # =========================
    # Common Web-Novel Tone / Slang
    # =========================
    "卧槽": "Holy crap",
    "我勒个骚刚": "Holy freaking crap",
    "妈了个巴子的": "Motherfucker",
    "鳖孙": "bastard",
    "瘪犊子玩意": "bastards",
    "开什么玩笑": "What kind of joke is this?",
    "还玩个屁": "Who the hell would keep playing?",
    "人个锤子": "People, my ass",
    "脑溢血": "cerebral hemorrhage",
    "心态爆炸": "mental state exploded",
    "人麻了": "went numb",
    "怪物": "monster",
    "妖孽": "freak",
    "无解": "unsolvable",
    "强无敌": "invincible",
    "超模": "overpowered",
    "天都要塌了": "it felt as if the sky had collapsed",
    "美滋滋": "happily",
    "光棍道": "said bluntly",
    "有气无力": "weakly and without much energy",
    "眼皮一跳": "eyelids twitched",
    "心神俱震": "mind shook violently",
    "翻江倒海": "stormy waves overturned inside him",
    "瞳孔骤缩": "pupils suddenly contracted",
    "面色煞白": "face turned deathly pale",
    "天旋地转": "the world spun around him",
    "耳鸣": "ringing in the ears",
    "吐了": "vomited",

    # =========================
    # Life / Backstory Terms
    # =========================
    "生前": "while alive",
    "死后": "after death",
    "作恶": "commit evil",
    "恶事": "evil deeds",
    "刑法": "criminal law",
    "犯过刑法": "violated criminal law",
    "没犯过刑法": "never violated criminal law",
    "人命": "human lives",
    "死在我手里": "died by my hands",
    "几条人命": "several lives",
    "杀人": "kill someone",
    "抢劫": "rob someone",
    "调戏良家妇女": "flirt with decent women",
    "活佛": "living Buddha",
    "圆寂": "pass away",
    "灵童": "reincarnated child",
    "佛学院": "Buddhist institute",
    "藏区": "Tibetan region",
    "大都市": "big city",
    "娶妻生子": "get married and have children",
    "拖欠工资": "delayed wages",
    "买房烂尾": "buying a house that ended up unfinished",
    "烂尾": "unfinished/abandoned",
    "失败": "failure",
    "逃避": "run away",
    "解脱": "freedom",

    # =========================
    # Physical Room / Objects
    # =========================
    "地板": "floor",
    "地板消失": "floor disappeared",
    "深渊": "abyss",
    "电脑桌": "computer desk",
    "纸": "paper",
    "手表": "watch",
    "烟": "cigarette",
    "点烟": "light a cigarette",
    "烟头": "cigarette butt",
    "茶": "tea",
    "口香糖": "chewing gum",
    "包装": "wrapper",
    "摩斯密码": "Morse code",

    # =========================
    # Useful Fixed Phrases
    # =========================
    "杀谎者·": "Lie Slayer: ",
    "如果我没猜错": "if I'm not mistaken",
    "换句话说": "in other words",
    "简单来说": "simply put",
    "也就是说": "that is to say",
    "果不其然": "sure enough",
    "想到此处": "thinking up to this point",
    "说罢": "after saying this",
    "闻言": "hearing this",
    "与此同时": "at the same time",
    "大概率": "most likely",
    "按理说": "logically speaking",
    "毫无防备": "without any guard",
    "得不偿失": "the gain is not worth the loss",
    "尘归尘土归土": "return to dust",
}


# =========================
# PROGRESS TRACKING
# =========================

def load_progress() -> dict:
    """Load translation progress from file."""
    if PROGRESS_FILE.exists():
        try:
            progress = json.loads(PROGRESS_FILE.read_text())
            progress.setdefault("completed", [])
            progress.setdefault("failed", [])
            progress.setdefault("in_progress", [])
            progress.setdefault("needs_review", [])
            return progress
        except:
            return {"completed": [], "failed": [], "in_progress": [], "needs_review": []}
    return {"completed": [], "failed": [], "in_progress": [], "needs_review": []}


def save_progress(progress: dict):
    """Save translation progress to file."""
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2))


def mark_chapter_complete(chapter: int, progress: dict):
    """Mark a chapter as completed."""
    if chapter not in progress["completed"]:
        progress["completed"].append(chapter)
        if chapter in progress["failed"]:
            progress["failed"].remove(chapter)
    if "needs_review" in progress and chapter in progress["needs_review"]:
        progress["needs_review"].remove(chapter)
    if chapter in progress["in_progress"]:
        progress["in_progress"].remove(chapter)
    save_progress(progress)


def mark_chapter_failed(chapter: int, progress: dict):
    """Mark a chapter as failed."""
    if chapter not in progress["failed"]:
        progress["failed"].append(chapter)
    if chapter in progress["in_progress"]:
        progress["in_progress"].remove(chapter)
    save_progress(progress)


# =========================
# SCRAPING
# =========================

def clean_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_chapter_from_html(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")

    # Remove junk
    for tag in soup(["script", "style", "noscript", "iframe", "form", "button"]):
        tag.decompose()

    title = None
    for selector in ["h1", ".title", ".chapter-title", "#title", ".bookname h1"]:
        node = soup.select_one(selector)
        if node:
            title = node.get_text(strip=True)
            break

    # Common Chinese novel site content selectors
    possible_selectors = [
        "#content",
        "#chaptercontent",
        ".chapter-content",
        ".chapter_content",
        ".read-content",
        ".read_content",
        ".content",
        ".article",
        "article",
        ".txt",
        ".text",
        ".book-content",
    ]

    content_node = None
    for selector in possible_selectors:
        node = soup.select_one(selector)
        if node:
            txt = node.get_text("\n", strip=True)
            if len(txt) > 500:
                content_node = node
                break

    # Fallback: choose largest text block
    if not content_node:
        candidates = soup.find_all(["div", "section", "article"])
        best_node = None
        best_len = 0
        for node in candidates:
            txt = node.get_text("\n", strip=True)
            if len(txt) > best_len:
                best_node = node
                best_len = len(txt)
        content_node = best_node

    if not content_node:
        raise RuntimeError("Could not find chapter content.")

    body = content_node.get_text("\n", strip=True)

    # Remove common navigation/footer junk
    junk_patterns = [
        r"上一章",
        r"下一章",
        r"书籍页",
        r"返回目录",
        r"加入书签",
        r"请收藏",
        r"最新网址",
        r"本章未完",
    ]

    lines = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if any(re.search(p, line) for p in junk_patterns):
            continue
        lines.append(line)

    body = "\n".join(lines)

    if not title:
        # Try title from first line
        first_line = lines[0] if lines else "Untitled"
        title = first_line[:80]

    return clean_text(title), clean_text(body)


def scrape_with_requests(url: str) -> tuple[str, str]:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    r.encoding = r.apparent_encoding

    if "安全验证" in r.text or "正在验证" in r.text:
        raise RuntimeError("Site returned a security verification page.")

    return extract_chapter_from_html(r.text)


def scrape_with_playwright(url: str) -> tuple[str, str]:
    """
    Opens a real browser. If the site shows a verification page,
    solve it manually in the browser window. The script will wait.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        print("\nIf the website shows security verification, complete it in the browser.")
        print("Waiting 20 seconds before extracting...\n")
        time.sleep(20)

        html = page.content()
        browser.close()

    return extract_chapter_from_html(html)


def save_raw_chapter(chapter: int) -> Path:
    url = BASE_URL.format(chapter=chapter)

    print(f"[SCRAPE] Fetching chapter {chapter}: {url}")

    try:
        if USE_BROWSER:
            title, body = scrape_with_playwright(url)
        else:
            title, body = scrape_with_requests(url)
    except Exception as e:
        print(f"[ERROR] Chapter {chapter} scraping failed: {e}")
        raise

    output_path = RAW_DIR / f"{chapter}.txt"
    output_path.write_text(f"{title}\n\n{body}", encoding="utf-8")

    print(f"[OK] Saved raw chapter: {output_path}")
    return output_path


# =========================
# TRANSLATION
# =========================

def split_text(text: str, max_chars: int = TRANSLATION_CHUNK_SIZE) -> list[str]:
    """
    Splits by paragraphs so the model does not lose context.
    """
    paragraphs = text.splitlines()
    chunks = []
    current = ""

    for p in paragraphs:
        p = p.strip()
        if not p:
            continue

        if len(current) + len(p) + 1 > max_chars:
            if current.strip():
                chunks.append(current.strip())
            current = p
        else:
            current += "\n" + p

    if current.strip():
        chunks.append(current.strip())

    return chunks


def glossary_text() -> str:
    return "\n".join([f"{k} = {v}" for k, v in GLOSSARY.items()])


POST_TRANSLATION_REPLACEMENTS = {
    "Chu Jie": "Duo Jie",
    "Time Wheel": "Wheel of Time",
    "time wheel": "Wheel of Time",
    "third-star": "three-star",
    "Lie-Killer": "Lie Slayer",
    "Lie Killer": "Lie Slayer",
    "Sophist Alliance": "Deceiver Alliance",
    "Sophist": "Deceiver",
    "Qiu Yinong's eyes looked exhausted. He": "Qiu Yinong's eyes looked exhausted. She",
    "Qiu Yinong rubbed his": "Qiu Yinong rubbed her",
    "All three stared at him": "All three stared at her",
}

BANNED_TRANSLATION_PATTERNS = [
    "Time Wheel",
    "Lie-Killer",
    "Lie Killer",
    "Sophist",
    "Chu Jie",
    "thinking to himself",
    "third-star players",
    "third-star",
]


def postprocess_translation(text: str, chapter: int | None = None) -> str:
    """Fix deterministic glossary drift and obvious formatting leftovers."""
    for source, target in POST_TRANSLATION_REPLACEMENTS.items():
        text = text.replace(source, target)

    text = re.sub(r"\n{3,}", "\n\n", text)
    if chapter is not None:
        text = re.sub(rf"\n*Chapter {chapter}\s*$", "", text).strip()
    return text.strip()


def validate_translation_quality(text: str) -> list[str]:
    """Return automatic issues that should block approval/review."""
    issues = []
    for pattern in BANNED_TRANSLATION_PATTERNS:
        if pattern in text:
            issues.append(f"Found banned/weak phrase: {pattern}")

    return issues


def groq_translate(prompt: str) -> str:
    """Use Groq API (FREE, unlimited, fastest). Get key from https://console.groq.com"""
    import os
    api_key = GROQ_API_KEY or os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set. Get it from https://console.groq.com")
    
    # Extract just the Chinese text and system prompt for better results
    system_prompt = TRANSLATION_STYLE
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,
        "max_tokens": 5000,
        "top_p": 0.95,
    }
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        print(f"[DEBUG] Groq response status: {response.status_code}")
        if response.status_code != 200:
            print(f"[DEBUG] Groq response: {response.text[:500]}")
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except requests.exceptions.HTTPError as e:
        print(f"[DEBUG] HTTP Error: {e}")
        print(f"[DEBUG] Response: {e.response.text[:500] if hasattr(e, 'response') else 'N/A'}")
        raise


def groq_polish(chinese_text: str, draft_text: str, chapter: int, part: int, total_parts: int) -> str:
    """Use Groq as a polishing editor over an Ollama draft."""
    api_key = GROQ_API_KEY or os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set. Set it before using ollama_groq_polish.")

    user_prompt = f"""
Chapter: {chapter}
Part: {part}/{total_parts}

Chinese source:
{chinese_text}

Ollama English draft:
{draft_text}

Polished English translation:
"""

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": POLISH_STYLE},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 5000,
            "top_p": 0.9,
        },
        timeout=120,
    )
    print(f"[DEBUG] Groq polish response status: {response.status_code}")
    if response.status_code != 200:
        print(f"[DEBUG] Groq polish response: {response.text[:500]}")
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def deepl_translate(prompt: str) -> str:
    """Use DeepL API (FREE tier: 500K chars/month). Get key from https://www.deepl.com/pro-api"""
    import os
    api_key = DEEPL_API_KEY or os.getenv("DEEPL_API_KEY")
    if not api_key:
        raise ValueError("DEEPL_API_KEY not set. Get it from https://www.deepl.com/pro-api")
    
    response = requests.post(
        "https://api-free.deepl.com/v1/translate",
        data={
            "auth_key": api_key,
            "text": prompt,
            "target_lang": "EN",
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["translations"][0]["text"].strip()


def ollama_translate(prompt: str) -> str:
    """Use Ollama (Local, free, requires ollama serve running)"""
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.25,
                "top_p": 0.9,
                "repeat_penalty": 1.05,
                "num_ctx": OLLAMA_NUM_CTX,
                "num_predict": OLLAMA_NUM_PREDICT,
            },
        },
        timeout=600,
    )
    response.raise_for_status()
    return response.json()["response"].strip()


def translate_with_backend(prompt: str) -> str:
    """Route to the selected translation backend"""
    if TRANSLATION_BACKEND == "groq":
        return groq_translate(prompt)
    elif TRANSLATION_BACKEND == "deepl":
        return deepl_translate(prompt)
    elif TRANSLATION_BACKEND == "ollama":
        return ollama_translate(prompt)
    else:
        raise ValueError(f"Unknown backend: {TRANSLATION_BACKEND}")


def translate_chunk(chunk: str, prompt: str, chapter: int, part: int, total_parts: int) -> str:
    """Translate a single chunk, optionally using Ollama draft + Groq polish."""
    if TRANSLATION_BACKEND == "ollama_groq_polish":
        print("[DRAFT] Ollama drafting...")
        draft = postprocess_translation(ollama_translate(prompt), chapter=chapter)
        print("[POLISH] Groq polishing Ollama draft...")
        polished = groq_polish(chunk, draft, chapter, part, total_parts)
        return postprocess_translation(polished, chapter=chapter)

    return postprocess_translation(translate_with_backend(prompt), chapter=chapter)


def translate_chapter(chapter: int) -> str:
    raw_path = RAW_DIR / f"{chapter}.txt"
    if not raw_path.exists():
        raise FileNotFoundError(f"Missing raw chapter file: {raw_path}")

    raw_text = raw_path.read_text(encoding="utf-8")
    chunks = split_text(raw_text)

    translated_parts = []

    for i, chunk in enumerate(chunks, start=1):
        print(f"[TRANSLATE] Chapter {chapter}, part {i}/{len(chunks)} (using {TRANSLATION_BACKEND})...")

        prompt = f"""
{TRANSLATION_STYLE}

Glossary:
{glossary_text()}

Chapter number: {chapter}
Part: {i}/{len(chunks)}

Chinese text:
{chunk}

English translation:
"""

        translated = translate_chunk(chunk, prompt, chapter, i, len(chunks))
        translated_parts.append(translated)

    final_text = "\n\n".join(translated_parts)
    final_text = postprocess_translation(final_text, chapter=chapter)

    issues = validate_translation_quality(final_text)
    if issues:
        print("[QUALITY WARNING]")
        for issue in issues:
            print(f"  - {issue}")

    return final_text


def append_to_consolidated_file(chapter: int, translated_text: str):
    """Append translated chapter to consolidated file."""
    separator = "\n" + "="*80 + "\n"
    
    if CONSOLIDATED_FILE.exists():
        current = CONSOLIDATED_FILE.read_text(encoding="utf-8")
        CONSOLIDATED_FILE.write_text(
            current + separator + translated_text + "\n",
            encoding="utf-8"
        )
    else:
        CONSOLIDATED_FILE.write_text(translated_text + "\n", encoding="utf-8")
    
    print(f"[SAVED] Chapter {chapter} appended to {CONSOLIDATED_FILE}")


def save_translated_chapter(chapter: int, translated_text: str) -> Path:
    """Save a standalone translated chapter for safer resume/rebuilds."""
    output_path = EN_DIR / f"chapter_{chapter}_en.txt"
    output_path.write_text(translated_text.strip() + "\n", encoding="utf-8")
    print(f"[SAVED] Chapter {chapter} file: {output_path}")
    return output_path


def process_chapter(chapter: int, progress: dict) -> bool:
    """Process a single chapter (scrape + translate). Returns True if successful."""
    try:
        print(f"\n{'='*60}")
        print(f"Processing Chapter {chapter}")
        print(f"{'='*60}")
        
        raw_path = RAW_DIR / f"{chapter}.txt"
        if raw_path.exists():
            print(f"[SCRAPE] Using cached raw chapter: {raw_path}")
        else:
            save_raw_chapter(chapter)
        translated_text = translate_chapter(chapter)
        save_translated_chapter(chapter, translated_text)
        append_to_consolidated_file(chapter, translated_text)
        
        mark_chapter_complete(chapter, progress)
        print(f"[SUCCESS] Chapter {chapter} completed!\n")
        return True
        
    except Exception as e:
        print(f"[FAILED] Chapter {chapter} failed: {e}\n")
        mark_chapter_failed(chapter, progress)
        return False


# =========================
# BATCH PROCESSING
# =========================

def process_chapters_concurrent(chapters: list[int], max_workers: int = 2) -> dict:
    """
    Process multiple chapters concurrently with thread pool.
    WARNING: Be careful with max_workers to avoid hammering the server!
    """
    progress = load_progress()
    results = {"success": [], "failed": []}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_chapter, ch, progress): ch
            for ch in chapters
        }
        
        for future in as_completed(futures):
            chapter = futures[future]
            try:
                success = future.result()
                if success:
                    results["success"].append(chapter)
                else:
                    results["failed"].append(chapter)
                time.sleep(2)  # Rate limiting between requests
            except Exception as e:
                print(f"[EXECUTOR ERROR] Chapter {chapter}: {e}")
                results["failed"].append(chapter)
    
    return results


def process_range_sequential(start: int, end: int):
    """Process chapters sequentially with progress tracking."""
    progress = load_progress()
    completed_count = 0
    failed_count = 0
    
    print(f"\n[START] Processing chapters {start} to {end}")
    print(f"[STATUS] Already completed: {len(progress['completed'])}")
    print(f"[STATUS] Already failed: {len(progress['failed'])}\n")
    
    for chapter in range(start, end + 1):
        if chapter in progress["completed"]:
            print(f"[SKIP] Chapter {chapter} already completed")
            continue
        
        success = process_chapter(chapter, progress)
        if success:
            completed_count += 1
        else:
            failed_count += 1
        
        time.sleep(3)  # Rate limiting between chapters
    
    return {
        "completed": completed_count,
        "failed": failed_count,
        "progress_file": str(PROGRESS_FILE),
        "output_file": str(CONSOLIDATED_FILE)
    }


def process_to_chapter(target_chapter: int, start: int = 1):
    """
    Process all chapters from start to target_chapter.
    Auto-loops and saves progress, can be resumed if interrupted.
    """
    progress = load_progress()
    
    print(f"\n{'='*60}")
    print(f"AUTO-LOOP: Processing chapters from {start} to {target_chapter}")
    print(f"{'='*60}\n")
    print(f"Progress File: {PROGRESS_FILE}")
    print(f"Output File: {CONSOLIDATED_FILE}")
    print(f"Already completed: {len(progress['completed'])} chapters")
    print(f"Already failed: {len(progress['failed'])} chapters\n")
    
    for chapter in range(start, target_chapter + 1):
        # Skip if already completed
        if chapter in progress["completed"]:
            print(f"[SKIP] Chapter {chapter} already completed")
            continue
        
        # Retry failed chapters once
        if chapter in progress["failed"]:
            print(f"[RETRY] Chapter {chapter} (previously failed)")
        
        success = process_chapter(chapter, progress)
        
        if not success:
            print(f"[WARN] Chapter {chapter} failed. Continuing to next chapter...")
        
        time.sleep(3)  # Rate limiting
    
    # Summary
    print(f"\n{'='*60}")
    print(f"COMPLETE: All chapters processed!")
    print(f"Successfully completed: {len(progress['completed'])} chapters")
    print(f"Failed: {len(progress['failed'])} chapters")
    print(f"Output consolidated file: {CONSOLIDATED_FILE}")
    print(f"{'='*60}\n")
    
    return progress


# =========================
# MAIN
# =========================

if __name__ == "__main__":
    # Translate the requested range, then build the reading-copy Word document.
    process_to_chapter(208, start=197)

    try:
        from create_word_document import create_word_document

        create_word_document(
            CONSOLIDATED_FILE,
            EN_DIR / "Novel_Translation.docx",
        )
    except Exception as e:
        print(f"[WARN] Word document creation failed: {e}")
