#!/usr/bin/env python3
"""Generate interactive quiz app HTML with selector, quiz taking, and results."""

import json
import os
import html
import re
import glob

OUTPUT_DIR = '/Users/javascript/Desktop/kt/quiz_data'
HTML_OUTPUT = '/Users/javascript/Desktop/kt/quiz_app.html'
MEDIA_DIR = os.path.join(OUTPUT_DIR, 'media')


def escape_js(text):
    """Escape text for embedding in JavaScript."""
    if not text:
        return ''
    return text.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n').replace('\r', '').replace('\t', '\\t')


def resolve_media_path(url):
    if not url:
        return None
    if url.startswith('http'):
        fname = url.split('/')[-1].split('?')[0]
    elif url.startswith('/'):
        fname = url.split('/')[-1].split('?')[0]
    else:
        fname = url.split('/')[-1].split('?')[0]
    for subdir in ['audio', 'img']:
        local = os.path.join(MEDIA_DIR, subdir, fname)
        if os.path.exists(local):
            return f'media/{subdir}/{fname}'
    if url.startswith('http'):
        return url
    return f'https://zhay.piupiu.kz/{url}' if url.startswith('/') else url


def clean_text(text):
    if not text:
        return ''
    text = re.sub(r'\[IMAGE:\s*[^\]]+\]', '', text)
    text = re.sub(r'\[AUDIO:\s*[^\]]+\]', '', text)
    return text.strip()


def process_question(q, has_answers):
    """Process a question into a JS-friendly dict."""
    text = clean_text(q.get('text', ''))
    blocks = q.get('blocks', [])
    options = q.get('options', [])
    explanation = q.get('explanation', '')
    correct_ids = q.get('correct_option_ids', [])

    # If no correct_ids but options have is_correct
    if not correct_ids and has_answers:
        correct_ids = [o['id'] for o in options if o.get('is_correct')]

    # Process blocks for media
    proc_blocks = []
    for b in sorted(blocks, key=lambda x: x.get('position', 0)):
        btype = b.get('type', '').upper()
        payload = b.get('payload', {})
        content = b.get('content', '')
        if btype == 'IMAGE':
            url = content or (payload.get('url') if payload else '')
            if url:
                proc_blocks.append({'type': 'image', 'url': resolve_media_path(url)})
        elif btype == 'AUDIO':
            url = content or (payload.get('url') or payload.get('original_url') if payload else '')
            if url:
                proc_blocks.append({'type': 'audio', 'url': resolve_media_path(url)})
        elif btype in ('CODE', 'code'):
            code = content or (payload.get('code') or payload.get('text') if payload else '')
            if code:
                proc_blocks.append({'type': 'code', 'content': code})
        elif btype == 'TEXT':
            t = content or (payload.get('text') if payload else '')
            if t:
                proc_blocks.append({'type': 'text', 'content': t})

    proc_options = []
    for o in options:
        proc_options.append({
            'id': o.get('id', ''),
            'text': o.get('text', ''),
            'is_correct': o.get('id') in correct_ids if correct_ids else o.get('is_correct', False),
        })

    return {
        'question_id': q.get('question_id', ''),
        'subject': q.get('subject', ''),
        'topic': q.get('topic', ''),
        'type': q.get('type', 'single_choice'),
        'difficulty': q.get('difficulty', ''),
        'text': text,
        'blocks': proc_blocks,
        'options': proc_options,
        'explanation': explanation,
        'correct_ids': correct_ids,
    }


def build_js_data(all_data):
    """Build JavaScript data object."""
    categories = []

    # Demo
    if 'demo' in all_data:
        v = all_data['demo']
        results = v.get('results', {})
        result_qs = results.get('questions', [])
        raw_qs = v.get('questions', [])
        has_answers = bool(result_qs)
        qs = result_qs if result_qs else raw_qs
        proc_qs = [process_question(q, has_answers) for q in qs]
        categories.append({
            'id': 'demo',
            'title': 'Демо-тест',
            'icon': '🎯',
            'has_answers': has_answers,
            'questions': proc_qs,
        })

    # angl_tgo
    if 'angl_tgo' in all_data:
        cat_variants = []
        for v in all_data['angl_tgo']:
            results = v.get('results', {})
            result_qs = results.get('questions', [])
            raw_qs = v.get('questions', [])
            has_answers = bool(result_qs)
            qs = result_qs if result_qs else raw_qs
            proc_qs = [process_question(q, has_answers) for q in qs]
            cat_variants.append({
                'id': v.get('variant_id', ''),
                'title': v.get('title', ''),
                'has_answers': has_answers,
                'questions': proc_qs,
            })
        categories.append({
            'id': 'angl_tgo',
            'title': 'Английский + ТГО',
            'icon': '🇬🇧',
            'variants': cat_variants,
        })

    # algo_db
    if 'algo_db' in all_data:
        cat_variants = []
        for v in all_data['algo_db']:
            results = v.get('results', {})
            result_qs = results.get('questions', [])
            raw_qs = v.get('questions', [])
            has_answers = bool(result_qs)
            qs = result_qs if result_qs else raw_qs
            proc_qs = [process_question(q, has_answers) for q in qs]
            cat_variants.append({
                'id': v.get('variant_id', ''),
                'title': v.get('title', ''),
                'has_answers': has_answers,
                'questions': proc_qs,
            })
        categories.append({
            'id': 'algo_db',
            'title': 'Алгоритмы + БД',
            'icon': '💻',
            'variants': cat_variants,
        })

    return categories


def generate_html(all_data):
    categories = build_js_data(all_data)
    js_data = json.dumps(categories, ensure_ascii=False)

    total_q = 0
    total_v = 0
    for cat in categories:
        if 'questions' in cat:
            total_q += len(cat['questions'])
            total_v += 1
        if 'variants' in cat:
            for v in cat['variants']:
                total_q += len(v['questions'])
                total_v += 1

    html_doc = f'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Quiz App — Interactive Quiz</title>
<style>
:root {{
    --bg: #f5f5f7;
    --surface: #ffffff;
    --surface2: #f0f0f3;
    --text: #1a1a2e;
    --muted: #6b7280;
    --accent: #6c63ff;
    --accent2: #a78bfa;
    --green: #10b981;
    --red: #ef4444;
    --yellow: #f59e0b;
    --border: #e5e7eb;
    --radius: 12px;
}}
[data-theme="dark"] {{
    --bg: #0f0f1a;
    --surface: #1a1a2e;
    --surface2: #252538;
    --text: #e4e4e7;
    --muted: #9ca3af;
    --border: #2e2e3e;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    transition: background 0.3s, color 0.3s;
}}

/* Theme toggle */
.theme-btn {{
    position: fixed; top: 20px; right: 20px;
    z-index: 100;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 50%;
    width: 44px; height: 44px;
    cursor: pointer;
    font-size: 1.2rem;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.2s;
}}
.theme-btn:hover {{ box-shadow: 0 4px 12px rgba(0,0,0,0.15); }}

/* ── Home / Selector ── */
#home {{
    max-width: 900px;
    margin: 0 auto;
    padding: 20px;
}}
.home-header {{
    text-align: center;
    padding: 40px 20px 30px;
}}
.home-header h1 {{ font-size: 2rem; font-weight: 800; margin-bottom: 8px; }}
.home-header p {{ color: var(--muted); font-size: 1rem; }}

.category-section {{ margin-bottom: 32px; }}
.category-title {{
    font-size: 1.3rem;
    font-weight: 800;
    margin-bottom: 16px;
    display: flex; align-items: center; gap: 10px;
    padding-bottom: 10px;
    border-bottom: 2px solid var(--accent);
}}
.variant-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 16px;
}}
.variant-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
    cursor: pointer;
    transition: all 0.2s;
    text-align: center;
    position: relative;
    overflow: hidden;
}}
.variant-card:hover {{
    box-shadow: 0 8px 24px rgba(108,99,255,0.15);
    border-color: var(--accent);
    transform: translateY(-2px);
}}
.variant-card .v-icon {{ font-size: 2rem; margin-bottom: 10px; }}
.variant-card .v-title {{ font-weight: 700; font-size: 0.95rem; margin-bottom: 6px; }}
.variant-card .v-info {{ font-size: 0.82rem; color: var(--muted); }}
.variant-card .v-badge {{
    position: absolute; top: 8px; right: 8px;
    font-size: 0.7rem; padding: 3px 8px; border-radius: 20px;
    font-weight: 600;
}}
.badge-answers {{ background: rgba(16,185,129,0.1); color: var(--green); }}
.badge-locked {{ background: rgba(245,158,11,0.1); color: var(--yellow); }}

/* ── Quiz View ── */
#quiz {{
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
    display: none;
}}
.quiz-header {{
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 20px;
    flex-wrap: wrap; gap: 10px;
}}
.btn-back {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px 16px;
    cursor: pointer;
    font-size: 0.9rem;
    color: var(--text);
    transition: all 0.2s;
}}
.btn-back:hover {{ background: var(--surface2); }}
.quiz-title {{ font-size: 1.2rem; font-weight: 700; }}
.timer {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 0.9rem;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
}}

.progress-bar {{
    height: 6px;
    background: var(--surface2);
    border-radius: 3px;
    margin-bottom: 20px;
    overflow: hidden;
}}
.progress-fill {{
    height: 100%;
    background: var(--accent);
    border-radius: 3px;
    transition: width 0.3s;
}}

.nav-dots {{
    display: flex; flex-wrap: wrap; gap: 6px;
    margin-bottom: 24px;
    justify-content: center;
}}
.q-dot {{
    width: 32px; height: 32px;
    display: flex; align-items: center; justify-content: center;
    border-radius: 8px;
    font-size: 0.78rem;
    font-weight: 700;
    cursor: pointer;
    background: var(--surface);
    border: 1px solid var(--border);
    transition: all 0.15s;
    color: var(--muted);
}}
.q-dot:hover {{ border-color: var(--accent); }}
.q-dot.current {{ background: var(--accent); color: white; border-color: var(--accent); }}
.q-dot.answered {{ background: rgba(16,185,129,0.15); border-color: var(--green); color: var(--green); }}
.q-dot.correct {{ background: var(--green); color: white; border-color: var(--green); }}
.q-dot.incorrect {{ background: var(--red); color: white; border-color: var(--red); }}

.question-area {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    margin-bottom: 20px;
}}
.q-meta {{
    display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px;
}}
.meta-tag {{
    background: var(--surface2);
    padding: 4px 10px; border-radius: 6px;
    font-size: 0.78rem; color: var(--muted);
}}
.q-text {{
    font-size: 1.1rem; font-weight: 600;
    margin: 12px 0 20px;
    line-height: 1.5;
}}
.block-image {{ margin: 12px 0; }}
.block-image img {{ max-width: 100%; border-radius: 8px; border: 1px solid var(--border); }}
.block-audio {{ margin: 12px 0; }}
.block-audio audio {{ width: 100%; }}
.block-code {{
    background: #1e1e2e; color: #cdd6f4;
    padding: 14px; border-radius: 8px;
    margin: 12px 0; overflow-x: auto;
}}
.block-code pre {{ font-family: 'SF Mono', Monaco, monospace; font-size: 0.85rem; white-space: pre-wrap; }}
.block-text {{ margin: 8px 0; color: var(--muted); font-style: italic; }}

.options {{ display: flex; flex-direction: column; gap: 8px; }}
.option {{
    display: flex; align-items: center; gap: 12px;
    padding: 14px 16px;
    border: 2px solid var(--border);
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s;
    user-select: none;
}}
.option:hover {{ border-color: var(--accent2); background: var(--surface2); }}
.option.selected {{
    border-color: var(--accent);
    background: rgba(108,99,255,0.05);
}}
.option.correct {{
    border-color: var(--green);
    background: rgba(16,185,129,0.08);
}}
.option.incorrect {{
    border-color: var(--red);
    background: rgba(239,68,68,0.08);
}}
.option.show-correct {{
    border-color: var(--green);
    background: rgba(16,185,129,0.08);
    animation: pulse 0.5s;
}}
@keyframes pulse {{
    0% {{ transform: scale(1); }}
    50% {{ transform: scale(1.02); }}
    100% {{ transform: scale(1); }}
}}
.option-letter {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 30px; height: 30px;
    background: var(--surface2);
    border-radius: 50%;
    font-weight: 700; font-size: 0.85rem;
    flex-shrink: 0;
}}
.option.selected .option-letter {{ background: var(--accent); color: white; }}
.option.correct .option-letter, .option.show-correct .option-letter {{ background: var(--green); color: white; }}
.option.incorrect .option-letter {{ background: var(--red); color: white; }}
.option-text {{ flex: 1; font-size: 0.95rem; }}
.option-icon {{ font-size: 1.2rem; }}

.explanation {{
    background: linear-gradient(135deg, rgba(108,99,255,0.05), rgba(167,139,250,0.03));
    border: 1px solid rgba(108,99,255,0.2);
    border-radius: 10px;
    padding: 16px;
    margin-top: 16px;
    display: none;
}}
.explanation.show {{ display: block; animation: fadeIn 0.3s; }}
@keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
.explanation-label {{ font-weight: 700; color: var(--accent); font-size: 0.85rem; margin-bottom: 8px; }}
.explanation-text {{ font-size: 0.92rem; line-height: 1.6; }}

.quiz-nav {{
    display: flex; justify-content: space-between; gap: 12px;
    margin-bottom: 20px;
}}
.btn {{
    padding: 12px 24px;
    border-radius: 10px;
    border: none;
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
}}
.btn-primary {{ background: var(--accent); color: white; }}
.btn-primary:hover {{ opacity: 0.9; }}
.btn-primary:disabled {{ opacity: 0.4; cursor: not-allowed; }}
.btn-secondary {{ background: var(--surface); border: 1px solid var(--border); color: var(--text); }}
.btn-secondary:hover {{ background: var(--surface2); }}
.btn-success {{ background: var(--green); color: white; }}
.btn-success:hover {{ opacity: 0.9; }}

/* ── Results View ── */
#results {{
    max-width: 700px;
    margin: 0 auto;
    padding: 20px;
    display: none;
    text-align: center;
}}
.score-circle {{
    width: 180px; height: 180px;
    border-radius: 50%;
    margin: 30px auto;
    display: flex; align-items: center; justify-content: center;
    position: relative;
}}
.score-circle::before {{
    content: '';
    position: absolute;
    inset: 10px;
    border-radius: 50%;
    background: var(--surface);
}}
.score-num {{
    position: relative;
    font-size: 2.5rem;
    font-weight: 800;
}}
.result-headline {{ font-size: 1.5rem; font-weight: 800; margin-bottom: 8px; }}
.result-sub {{ color: var(--muted); margin-bottom: 24px; }}
.result-stats {{
    display: flex; gap: 16px; justify-content: center; flex-wrap: wrap;
    margin-bottom: 24px;
}}
.stat-box {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px 24px;
    min-width: 100px;
}}
.stat-num {{ font-size: 1.8rem; font-weight: 800; }}
.stat-label {{ font-size: 0.8rem; color: var(--muted); margin-top: 4px; }}
.result-actions {{
    display: flex; gap: 12px; justify-content: center; flex-wrap: wrap;
    margin-top: 20px;
}}

.show-answers-toggle {{
    margin: 20px 0;
    display: flex; gap: 12px; justify-content: center;
}}

.no-answer-warning {{
    background: rgba(245,158,11,0.08);
    border: 1px solid rgba(245,158,11,0.2);
    border-radius: 10px;
    padding: 16px;
    margin: 20px 0;
    color: var(--yellow);
    font-size: 0.9rem;
}}

@media (max-width: 600px) {{
    .variant-grid {{ grid-template-columns: 1fr 1fr; }}
    .nav-dots {{ gap: 4px; }}
    .q-dot {{ width: 28px; height: 28px; font-size: 0.7rem; }}
}}
</style>
</head>
<body>

<button class="theme-btn" id="theme-btn" onclick="toggleTheme()">🌙</button>

<!-- Home / Selector -->
<div id="home">
    <div class="home-header">
        <h1>🧪 Quiz App</h1>
        <p>{total_q} questions · {total_v} variants</p>
    </div>
    <div id="home-content"></div>
</div>

<!-- Quiz View -->
<div id="quiz">
    <div class="quiz-header">
        <button class="btn-back" onclick="goHome()">← К вариантам</button>
        <div class="quiz-title" id="quiz-title"></div>
        <div class="timer" id="timer">00:00</div>
    </div>
    <div class="progress-bar"><div class="progress-fill" id="progress-fill" style="width:0%"></div></div>
    <div class="nav-dots" id="nav-dots"></div>
    <div class="question-area" id="question-area"></div>
    <div class="quiz-nav">
        <button class="btn btn-secondary" id="btn-prev" onclick="prevQuestion()">← Назад</button>
        <button class="btn btn-primary" id="btn-next" onclick="nextQuestion()">Далее →</button>
        <button class="btn btn-success" id="btn-submit" onclick="submitQuiz()" style="display:none">Завершить тест ✓</button>
    </div>
</div>

<!-- Results View -->
<div id="results">
    <div class="score-circle" id="score-circle">
        <div class="score-num" id="score-num">0%</div>
    </div>
    <div class="result-headline" id="result-headline"></div>
    <div class="result-sub" id="result-sub"></div>
    <div class="result-stats" id="result-stats"></div>
    <div id="result-extra"></div>
    <div class="result-actions">
        <button class="btn btn-secondary" onclick="goHome()">← К вариантам</button>
        <button class="btn btn-primary" id="btn-review" onclick="reviewAnswers()">Просмотреть ответы →</button>
        <button class="btn btn-secondary" id="btn-retry" onclick="retryQuiz()">↻ Пройти заново</button>
    </div>
</div>

<script>
const QUIZ_DATA = {js_data};

// ── State ──
let currentVariant = null;
let currentQuestions = [];
let currentIndex = 0;
let answers = {{}};  // question_id -> [option_id, ...]
let startTime = 0;
let timerInterval = null;
let submitted = false;
let showCorrectMode = false;

// ── Theme ──
function toggleTheme() {{
    let theme = document.documentElement.getAttribute('data-theme');
    theme = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    document.getElementById('theme-btn').textContent = theme === 'dark' ? '☀️' : '🌙';
}}
(function() {{
    const t = localStorage.getItem('theme') || 'light';
    if (t === 'dark') {{ document.documentElement.setAttribute('data-theme', 'dark'); document.getElementById('theme-btn').textContent = '☀️'; }}
}})();

// ── Home / Selector ──
function renderHome() {{
    let html = '';
    QUIZ_DATA.forEach(cat => {{
        html += '<div class="category-section">';
        html += '<div class="category-title">' + cat.icon + ' ' + cat.title + '</div>';
        html += '<div class="variant-grid">';

        if (cat.questions) {{
            // Single variant (demo)
            html += renderVariantCard(cat, cat);
        }} else if (cat.variants) {{
            cat.variants.forEach((v, i) => {{
                html += renderVariantCard(cat, v, i + 1);
            }});
        }}

        html += '</div></div>';
    }});
    document.getElementById('home-content').innerHTML = html;
}}

function renderVariantCard(cat, v, num) {{
    const qCount = v.questions.length;
    const hasAns = v.has_answers;
    const badge = hasAns
        ? '<span class="v-badge badge-answers">✅ Ответы</span>'
        : '<span class="v-badge badge-locked">🔒 Без ответов</span>';
    const icon = cat.icon;
    const title = num ? cat.title + ' — Вариант ' + num : v.title;
    return '<div class="variant-card" onclick="startQuiz(\\''+cat.id+'\\','+(num||0)+')">' +
        badge +
        '<div class="v-icon">' + icon + '</div>' +
        '<div class="v-title">' + escapeHtml(title) + '</div>' +
        '<div class="v-info">' + qCount + ' вопросов</div>' +
    '</div>';
}}

function escapeHtml(s) {{
    if (!s) return '';
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}}

function findVariant(catId, num) {{
    for (const cat of QUIZ_DATA) {{
        if (cat.id === catId) {{
            if (cat.questions && num === 0) return {{ variant: cat, cat: cat }};
            if (cat.variants && num > 0) return {{ variant: cat.variants[num-1], cat: cat }};
        }}
    }}
    return null;
}}

// ── Quiz ──
function startQuiz(catId, num) {{
    const found = findVariant(catId, num);
    if (!found) return;
    currentVariant = found.variant;
    currentQuestions = found.variant.questions;
    currentIndex = 0;
    answers = {{}};
    submitted = false;
    showCorrectMode = false;

    document.getElementById('home').style.display = 'none';
    document.getElementById('results').style.display = 'none';
    document.getElementById('quiz').style.display = 'block';

    const title = num > 0 ? found.cat.title + ' — Вариант ' + num : currentVariant.title;
    document.getElementById('quiz-title').textContent = title;

    renderNavDots();
    renderQuestion(0);
    startTimer();
}}

function startTimer() {{
    startTime = Date.now();
    if (timerInterval) clearInterval(timerInterval);
    timerInterval = setInterval(() => {{
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        const m = String(Math.floor(elapsed / 60)).padStart(2, '0');
        const s = String(elapsed % 60).padStart(2, '0');
        document.getElementById('timer').textContent = m + ':' + s;
    }}, 1000);
}}

function renderNavDots() {{
    const nav = document.getElementById('nav-dots');
    nav.innerHTML = currentQuestions.map((q, i) => {{
        let cls = 'q-dot';
        if (i === currentIndex) cls += ' current';
        if (answers[q.question_id]) cls += ' answered';
        return '<div class="' + cls + '" id="dot-' + i + '" onclick="jumpTo(' + i + ')">' + (i+1) + '</div>';
    }}).join('');
}}

function updateDots() {{
    currentQuestions.forEach((q, i) => {{
        const dot = document.getElementById('dot-' + i);
        if (!dot) return;
        let cls = 'q-dot';
        if (i === currentIndex) cls += ' current';
        if (answers[q.question_id]) cls += ' answered';
        if (submitted && showCorrectMode) {{
            if (isCorrectAnswer(q)) cls += ' correct';
            else if (answers[q.question_id]) cls += ' incorrect';
        }}
        dot.className = cls;
    }});
}}

function renderQuestion(index) {{
    currentIndex = index;
    const q = currentQuestions[index];
    if (!q) return;

    const isMulti = q.type === 'multiple_choice';
    const multiHint = isMulti ? ' <span style="font-size:0.8rem;color:var(--accent)">(несколько вариантов)</span>' : '';

    let blocksHtml = '';
    if (q.blocks && q.blocks.length > 0) {{
        q.blocks.forEach(b => {{
            if (b.type === 'image') {{
                blocksHtml += '<div class="block-image"><img src="' + b.url + '" alt="Image" /></div>';
            }} else if (b.type === 'audio') {{
                blocksHtml += '<div class="block-audio"><audio controls src="' + b.url + '"></audio></div>';
            }} else if (b.type === 'code') {{
                blocksHtml += '<div class="block-code"><pre>' + escapeHtml(b.content) + '</pre></div>';
            }} else if (b.type === 'text') {{
                blocksHtml += '<div class="block-text">' + escapeHtml(b.content) + '</div>';
            }}
        }});
    }}

    const saved = answers[q.question_id] || [];
    const letters = ['A','B','C','D','E','F','G','H'];

    let optionsHtml = '<div class="options">';
    q.options.forEach((opt, i) => {{
        let cls = 'option';
        if (saved.includes(opt.id)) cls += ' selected';
        if (submitted && showCorrectMode) {{
            if (opt.is_correct) cls += ' show-correct';
            if (saved.includes(opt.id) && !opt.is_correct) cls += ' incorrect';
        }}
        let icon = '';
        if (submitted && showCorrectMode) {{
            if (opt.is_correct) icon = '✅';
            else if (saved.includes(opt.id)) icon = '❌';
        }}
        optionsHtml += '<div class="' + cls + '" id="opt-' + opt.id + '" onclick="selectOption(\\''+opt.id+'\\','+isMulti+')">' +
            '<span class="option-letter">' + (letters[i] || (i+1)) + '</span>' +
            '<span class="option-text">' + escapeHtml(opt.text) + '</span>' +
            '<span class="option-icon">' + icon + '</span>' +
        '</div>';
    }});
    optionsHtml += '</div>';

    // Explanation (only in review mode)
    let explHtml = '';
    if (submitted && showCorrectMode && q.explanation) {{
        explHtml = '<div class="explanation show"><div class="explanation-label">💡 Объяснение</div><div class="explanation-text">' + escapeHtml(q.explanation) + '</div></div>';
    }}

    const diffTag = q.difficulty ? '<span class="meta-tag">⚡ ' + escapeHtml(q.difficulty) + '</span>' : '';

    document.getElementById('question-area').innerHTML =
        '<div class="q-meta">' +
        '<span class="meta-tag">📚 ' + escapeHtml(q.subject || 'Тест') + '</span>' +
        '<span class="meta-tag">📖 ' + escapeHtml(q.topic || '') + '</span>' +
        diffTag +
        '</div>' +
        blocksHtml +
        '<div class="q-text">Вопрос ' + (index+1) + ' из ' + currentQuestions.length + multiHint + '<br><br>' + escapeHtml(q.text) + '</div>' +
        optionsHtml + explHtml;

    // Progress
    const pct = ((index + 1) / currentQuestions.length) * 100;
    document.getElementById('progress-fill').style.width = pct + '%';

    // Nav buttons
    const isLast = index === currentQuestions.length - 1;
    document.getElementById('btn-prev').disabled = index === 0;
    document.getElementById('btn-prev').style.opacity = index === 0 ? '0.4' : '1';
    document.getElementById('btn-next').style.display = isLast ? 'none' : 'inline-block';
    document.getElementById('btn-submit').style.display = isLast ? 'inline-block' : 'none';

    updateDots();
}}

function selectOption(optId, isMulti) {{
    if (submitted && showCorrectMode) return;  // lock after submit in review mode
    const q = currentQuestions[currentIndex];
    const qid = q.question_id;
    const current = answers[qid] || [];

    if (isMulti) {{
        if (current.includes(optId)) {{
            answers[qid] = current.filter(id => id !== optId);
        }} else {{
            answers[qid] = [...current, optId];
        }}
    }} else {{
        answers[qid] = [optId];
    }}

    // Update option UI
    q.options.forEach(opt => {{
        const el = document.getElementById('opt-' + opt.id);
        if (el) {{
            let cls = 'option';
            if (answers[qid].includes(opt.id)) cls += ' selected';
            el.className = cls;
        }}
    }});

    updateDots();
}}

function nextQuestion() {{
    if (currentIndex < currentQuestions.length - 1) renderQuestion(currentIndex + 1);
}}
function prevQuestion() {{
    if (currentIndex > 0) renderQuestion(currentIndex - 1);
}}
function jumpTo(index) {{
    if (index !== currentIndex) renderQuestion(index);
}}

function isCorrectAnswer(q) {{
    const saved = answers[q.question_id] || [];
    if (!saved.length) return false;
    const correctIds = q.correct_ids || q.options.filter(o => o.is_correct).map(o => o.id);
    if (!correctIds.length) return false;
    return correctIds.every(id => saved.includes(id)) && saved.every(id => correctIds.includes(id));
}}

function submitQuiz() {{
    const answeredCount = Object.keys(answers).length;
    const total = currentQuestions.length;
    if (answeredCount < total) {{
        const remaining = total - answeredCount;
        if (!confirm('Вы ответили на ' + answeredCount + ' из ' + total + ' вопросов (' + remaining + ' пропущено). Завершить тест?')) return;
    }}

    submitted = true;
    clearInterval(timerInterval);

    const hasAnswers = currentVariant.has_answers;
    let correctCount = 0;
    currentQuestions.forEach(q => {{
        if (isCorrectAnswer(q)) correctCount++;
    }});

    const pct = Math.round((correctCount / total) * 100);

    // Show results
    document.getElementById('quiz').style.display = 'none';
    document.getElementById('results').style.display = 'block';

    // Score circle
    const deg = (pct / 100) * 360;
    const color = pct >= 70 ? 'var(--green)' : pct >= 50 ? 'var(--yellow)' : 'var(--red)';
    document.getElementById('score-circle').style.background = 'conic-gradient(' + color + ' ' + deg + 'deg, var(--surface2) 0)';

    // Animate score
    let displayed = 0;
    const animInt = setInterval(() => {{
        displayed = Math.min(displayed + 2, pct);
        document.getElementById('score-num').textContent = displayed + '%';
        if (displayed >= pct) clearInterval(animInt);
    }}, 20);

    // Headline
    const headline = pct >= 80 ? '🏆 Отличный результат!' : pct >= 60 ? '👍 Хороший результат!' : '💪 Продолжай практиковаться!';
    document.getElementById('result-headline').textContent = headline;

    // Stats
    let statsHtml = '';
    if (hasAnswers) {{
        statsHtml =
            '<div class="stat-box"><div class="stat-num" style="color:var(--green)">' + correctCount + '</div><div class="stat-label">Правильно</div></div>' +
            '<div class="stat-box"><div class="stat-num" style="color:var(--red)">' + (total - correctCount) + '</div><div class="stat-label">Неправильно</div></div>' +
            '<div class="stat-box"><div class="stat-num">' + total + '</div><div class="stat-label">Всего</div></div>' +
            '<div class="stat-box"><div class="stat-num" style="color:' + color + '">' + pct + '%</div><div class="stat-label">Результат</div></div>';
        document.getElementById('result-sub').textContent = 'Нажмите «Просмотреть ответы» чтобы увидеть правильные ответы и объяснения.';
        document.getElementById('btn-review').style.display = 'inline-block';
    }} else {{
        statsHtml =
            '<div class="stat-box"><div class="stat-num">' + total + '</div><div class="stat-label">Вопросов</div></div>' +
            '<div class="stat-box"><div class="stat-num" style="color:' + color + '">' + pct + '%</div><div class="stat-label">Самооценка</div></div>';
        document.getElementById('result-sub').textContent = 'Ответы недоступны (нет платного доступа). Вы можете проверить себя самостоятельно.';
        document.getElementById('btn-review').style.display = 'inline-block';
        document.getElementById('result-extra').innerHTML = '<div class="no-answer-warning">⚠️ Для этого варианта нет ключа с правильными ответами. Вы можете просмотреть свои ответы и оценить себя самостоятельно.</div>';
    }}
    document.getElementById('result-stats').innerHTML = statsHtml;
}}

function reviewAnswers() {{
    showCorrectMode = true;
    document.getElementById('results').style.display = 'none';
    document.getElementById('quiz').style.display = 'block';
    document.getElementById('btn-submit').style.display = 'none';
    document.getElementById('btn-next').style.display = 'none';
    renderQuestion(0);
    updateDots();
}}

function retryQuiz() {{
    submitted = false;
    showCorrectMode = false;
    answers = {{}};
    currentIndex = 0;
    document.getElementById('results').style.display = 'none';
    document.getElementById('quiz').style.display = 'block';
    document.getElementById('btn-review').style.display = 'inline-block';
    document.getElementById('result-extra').innerHTML = '';
    renderNavDots();
    renderQuestion(0);
    startTimer();
}}

function goHome() {{
    if (timerInterval) clearInterval(timerInterval);
    document.getElementById('quiz').style.display = 'none';
    document.getElementById('results').style.display = 'none';
    document.getElementById('home').style.display = 'block';
    submitted = false;
    showCorrectMode = false;
    answers = {{}};
}}

// ── Init ──
renderHome();
</script>

</body>
</html>'''

    with open(HTML_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(html_doc)
    print(f'✅ Interactive quiz app generated: {HTML_OUTPUT}')
    print(f'   Total questions: {total_q}')
    print(f'   Total variants: {total_v}')
    fsize = os.path.getsize(HTML_OUTPUT)
    print(f'   File size: {fsize / 1024 / 1024:.1f} MB')


def main():
    combined_path = os.path.join(OUTPUT_DIR, 'all_quiz_data.json')
    if os.path.exists(combined_path):
        with open(combined_path, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
    else:
        all_data = {}
        for fpath in glob.glob(os.path.join(OUTPUT_DIR, '*.json')):
            fname = os.path.basename(fpath)
            if fname == 'all_quiz_data.json':
                continue
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            vid = data.get('variant_id', fname.replace('.json', ''))
            if 'demo' in vid:
                all_data['demo'] = data
            elif 'angl_tgo' in vid:
                all_data.setdefault('angl_tgo', []).append(data)
            elif 'algo_db' in vid:
                all_data.setdefault('algo_db', []).append(data)

    generate_html(all_data)


if __name__ == '__main__':
    main()
