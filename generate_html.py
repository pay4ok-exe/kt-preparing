#!/usr/bin/env python3
"""Generate a beautiful HTML quiz review from downloaded JSON data."""

import json
import os
import html
import re
import glob

OUTPUT_DIR = '/Users/javascript/Desktop/kt/quiz_data'
HTML_OUTPUT = '/Users/javascript/Desktop/kt/quiz_review.html'
MEDIA_DIR = os.path.join(OUTPUT_DIR, 'media')


def escape(text):
    if not text:
        return ''
    return html.escape(str(text))


def resolve_media_path(url):
    """Convert a media URL to a local relative path for HTML."""
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


def render_blocks(blocks):
    if not blocks:
        return ''
    parts = []
    for b in sorted(blocks, key=lambda x: x.get('position', 0)):
        btype = b.get('type', '').upper()
        payload = b.get('payload', {})
        content = b.get('content', '')
        if btype == 'IMAGE':
            url = content or (payload.get('url') if payload else '')
            if url:
                local = resolve_media_path(url)
                parts.append(f'<div class="block-image"><img src="{escape(local)}" alt="Question image" /></div>')
        elif btype == 'AUDIO':
            url = content or (payload.get('url') or payload.get('original_url') if payload else '')
            if url:
                local = resolve_media_path(url)
                parts.append(f'<div class="block-audio"><audio controls src="{escape(local)}"></audio></div>')
        elif btype in ('CODE', 'code'):
            code_text = content or (payload.get('code') or payload.get('text') if payload else '')
            if code_text:
                parts.append(f'<div class="block-code"><pre>{escape(code_text)}</pre></div>')
        elif btype == 'TEXT':
            text = content or (payload.get('text') if payload else '')
            if text:
                parts.append(f'<div class="block-text">{escape(text)}</div>')
    return '\n'.join(parts)


def clean_question_text(text):
    if not text:
        return ''
    text = re.sub(r'\[IMAGE:\s*[^\]]+\]', '', text)
    text = re.sub(r'\[AUDIO:\s*[^\]]+\]', '', text)
    return text.strip()


def render_options(options, correct_ids, has_answers):
    if not options:
        return ''
    letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    parts = ['<div class="options">']
    for i, opt in enumerate(options):
        is_correct = False
        if has_answers:
            is_correct = opt.get('id') in correct_ids if correct_ids else opt.get('is_correct', False)
        cls = 'option correct' if is_correct else 'option'
        letter = letters[i] if i < len(letters) else str(i + 1)
        icon = '✅' if is_correct else ''
        parts.append(f'''<div class="{cls}">
            <span class="option-letter">{letter}</span>
            <span class="option-text">{escape(opt.get('text', ''))}</span>
            <span class="option-icon">{icon}</span>
        </div>''')
    parts.append('</div>')
    return '\n'.join(parts)


def render_question(q, index, total, has_answers):
    text = clean_question_text(q.get('text', ''))
    subject = q.get('subject', '')
    topic = q.get('topic', '')
    qtype = q.get('type', '')
    blocks = q.get('blocks', [])
    options = q.get('options', [])
    explanation = q.get('explanation', '')
    correct_ids = q.get('correct_option_ids', [])
    is_correct = q.get('is_correct', None)
    difficulty = q.get('difficulty', '')

    type_label = '🔗 Multiple choice' if 'multiple' in qtype else '① Single choice'

    if has_answers and is_correct is not None:
        result_badge = '✅ Correct' if is_correct else '❌ Incorrect'
        badge_cls = 'correct-badge' if is_correct else 'incorrect-badge'
    elif has_answers:
        result_badge = '💡 Answer shown'
        badge_cls = 'info-badge'
    else:
        result_badge = '🔒 No answer key'
        badge_cls = 'locked-badge'

    diff_tag = f'<span class="meta-tag">⚡ {escape(difficulty)}</span>' if difficulty else ''

    return f'''
    <div class="question-card" id="q{index}">
        <div class="question-header">
            <span class="q-num">Question {index + 1} / {total}</span>
            <span class="q-badge {badge_cls}">{result_badge}</span>
        </div>
        <div class="q-meta">
            <span class="meta-tag">📚 {escape(subject)}</span>
            <span class="meta-tag">📖 {escape(topic)}</span>
            <span class="meta-tag">{type_label}</span>
            {diff_tag}
        </div>
        {render_blocks(blocks)}
        <div class="q-text">{escape(text)}</div>
        {render_options(options, correct_ids, has_answers)}
        {f'<div class="explanation"><div class="explanation-label">💡 Explanation</div><div class="explanation-text">{escape(explanation)}</div></div>' if explanation else ''}
    </div>'''


def render_variant(variant_data, variant_key):
    title = variant_data.get('title', variant_key)
    results = variant_data.get('results', {})
    raw_questions = variant_data.get('questions', [])
    result_questions = results.get('questions', [])
    is_paid = results.get('is_paid', False)
    total = results.get('total', len(raw_questions))
    score = results.get('score_percent', '?')

    # Use result questions (with answers) if available, otherwise raw questions
    if result_questions:
        questions = result_questions
        has_answers = True
    else:
        questions = raw_questions
        has_answers = False

    if not questions:
        return f'<div class="variant-section"><h2>{escape(title)}</h2><p>No data available.</p></div>'

    questions_html = '\n'.join(render_question(q, i, total, has_answers) for i, q in enumerate(questions))

    if has_answers:
        summary_tags = f'''
            <span class="summary-tag">📊 Score: {score}%</span>
            <span class="summary-tag">📝 Questions: {total}</span>
            <span class="summary-tag">✅ Answers included</span>'''
    else:
        summary_tags = f'''
            <span class="summary-tag">📝 Questions: {total}</span>
            <span class="summary-tag locked-tag">🔒 No answer key (unpaid)</span>'''

    return f'''
    <div class="variant-section">
        <h2>{escape(title)}</h2>
        <div class="variant-summary">{summary_tags}</div>
        {questions_html}
    </div>'''


def generate_html(all_data):
    sections = []

    # Table of contents
    toc_items = []

    if 'demo' in all_data:
        toc_items.append(('demo', 'Демо-тест', 15))
    for v in all_data.get('angl_tgo', []):
        toc_items.append((v.get('variant_id', ''), v.get('title', ''), v.get('total_count', 40)))
    for v in all_data.get('algo_db', []):
        toc_items.append((v.get('variant_id', ''), v.get('title', ''), v.get('total_count', 30)))

    toc_html = '<div class="toc">'
    for vid, title, count in toc_items:
        toc_html += f'<a href="#variant-{vid}" class="toc-item"><span class="toc-title">{escape(title)}</span><span class="toc-count">{count} Q</span></a>'
    toc_html += '</div>'

    # Demo
    if 'demo' in all_data:
        vid = 'demo'
        sections.append(f'<div id="variant-{vid}">' + render_variant(all_data['demo'], 'demo') + '</div>')

    for v in all_data.get('angl_tgo', []):
        vid = v.get('variant_id', '')
        sections.append(f'<div id="variant-{vid}">' + render_variant(v, vid) + '</div>')

    for v in all_data.get('algo_db', []):
        vid = v.get('variant_id', '')
        sections.append(f'<div id="variant-{vid}">' + render_variant(v, vid) + '</div>')

    body_content = '\n'.join(sections)

    total_q = sum(t[2] for t in toc_items)

    html_doc = f'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Quiz Review — All Questions & Answers</title>
<style>
:root {{
    --bg: #f5f5f7;
    --surface: #ffffff;
    --text: #1a1a2e;
    --muted: #6b7280;
    --accent: #6c63ff;
    --green: #10b981;
    --red: #ef4444;
    --orange: #f59e0b;
    --border: #e5e7eb;
    --radius: 12px;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 20px;
    max-width: 900px;
    margin: 0 auto;
}}

h1 {{ font-size: 1.8rem; font-weight: 800; margin-bottom: 8px; text-align: center; }}
.subtitle {{ text-align: center; color: var(--muted); margin-bottom: 24px; font-size: 0.95rem; }}

.toc {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px;
    margin-bottom: 32px;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 8px;
}}
.toc-item {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 14px;
    border-radius: 8px;
    text-decoration: none;
    color: var(--text);
    background: var(--bg);
    transition: all 0.2s;
    font-size: 0.88rem;
}}
.toc-item:hover {{ background: rgba(108,99,255,0.1); }}
.toc-title {{ font-weight: 600; }}
.toc-count {{ color: var(--muted); font-size: 0.8rem; }}

.variant-section {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    margin-bottom: 24px;
}}
.variant-section h2 {{
    font-size: 1.4rem;
    font-weight: 800;
    margin-bottom: 12px;
    padding-bottom: 12px;
    border-bottom: 2px solid var(--accent);
}}
.variant-summary {{
    display: flex;
    gap: 12px;
    margin-bottom: 24px;
    flex-wrap: wrap;
}}
.summary-tag {{
    background: var(--bg);
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
}}
.locked-tag {{ background: rgba(245,158,11,0.1); color: var(--orange); }}

.question-card {{
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
    margin-bottom: 16px;
    transition: box-shadow 0.2s;
}}
.question-card:hover {{ box-shadow: 0 4px 12px rgba(0,0,0,0.08); }}

.question-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}}
.q-num {{ font-weight: 700; font-size: 0.95rem; color: var(--accent); }}
.q-badge {{ font-size: 0.8rem; font-weight: 600; padding: 4px 10px; border-radius: 20px; }}
.correct-badge {{ background: rgba(16,185,129,0.1); color: var(--green); }}
.incorrect-badge {{ background: rgba(239,68,68,0.1); color: var(--red); }}
.info-badge {{ background: rgba(108,99,255,0.1); color: var(--accent); }}
.locked-badge {{ background: rgba(245,158,11,0.1); color: var(--orange); }}

.q-meta {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }}
.meta-tag {{
    background: var(--bg);
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.78rem;
    color: var(--muted);
}}

.block-image {{ margin: 12px 0; }}
.block-image img {{ max-width: 100%; border-radius: 8px; border: 1px solid var(--border); }}
.block-audio {{ margin: 12px 0; }}
.block-audio audio {{ width: 100%; border-radius: 8px; }}
.block-code {{
    background: #1e1e2e;
    color: #cdd6f4;
    padding: 14px;
    border-radius: 8px;
    margin: 12px 0;
    overflow-x: auto;
}}
.block-code pre {{ font-family: 'SF Mono', Monaco, monospace; font-size: 0.85rem; white-space: pre-wrap; }}
.block-text {{ margin: 8px 0; color: var(--muted); font-style: italic; }}

.q-text {{
    font-size: 1.05rem;
    font-weight: 600;
    margin: 12px 0;
    line-height: 1.5;
}}

.options {{ margin: 12px 0; }}
.option {{
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    border: 2px solid var(--border);
    border-radius: 8px;
    margin-bottom: 8px;
    transition: all 0.2s;
}}
.option.correct {{
    border-color: var(--green);
    background: rgba(16,185,129,0.05);
}}
.option-letter {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px; height: 28px;
    background: var(--bg);
    border-radius: 50%;
    font-weight: 700;
    font-size: 0.85rem;
    flex-shrink: 0;
}}
.option.correct .option-letter {{ background: var(--green); color: white; }}
.option-text {{ flex: 1; }}
.option-icon {{ font-size: 1.1rem; }}

.explanation {{
    background: linear-gradient(135deg, rgba(108,99,255,0.05), rgba(167,139,250,0.03));
    border: 1px solid rgba(108,99,255,0.2);
    border-radius: 8px;
    padding: 14px 16px;
    margin-top: 14px;
}}
.explanation-label {{
    font-weight: 700;
    color: var(--accent);
    font-size: 0.85rem;
    margin-bottom: 6px;
}}
.explanation-text {{
    font-size: 0.92rem;
    line-height: 1.6;
    color: var(--text);
}}

.no-answer-note {{
    background: rgba(245,158,11,0.05);
    border: 1px solid rgba(245,158,11,0.2);
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 16px;
    font-size: 0.88rem;
    color: var(--orange);
}}
</style>
</head>
<body>

<h1>🧪 Quiz Review</h1>
<p class="subtitle">{total_q} questions across {len(toc_items)} variants • Demo has full answers + explanations</p>

{toc_html}

{body_content}

</body>
</html>'''

    with open(HTML_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(html_doc)
    print(f'✅ HTML generated: {HTML_OUTPUT}')
    print(f'   Total questions: {total_q}')


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
