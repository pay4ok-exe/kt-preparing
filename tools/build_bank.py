#!/usr/bin/env python3
"""Build the unified KT-exam question bank from all extracted sources.

Outputs extracted/bank.json:
{ subjects: {id: {name, topics: [..]}},
  questions: [{id, subject, topic, lang, type, text, options: [{text, correct}], source}] }
"""
import fitz, json, os, re, sys, unicodedata, zipfile, hashlib
from xml.etree import ElementTree as ET

ROOT = '/Users/javascript/Desktop/kt'
os.chdir(ROOT)
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

QUESTIONS = []
STATS = []

def norm(s):
    s = unicodedata.normalize('NFKC', s)
    s = re.sub(r'\s+', ' ', s).strip().lower()
    return s

def add_questions(qs, subject, lang, source, min_opts=2):
    """qs: list of dicts {text, options:[(text, correct)], topic?}"""
    kept = 0
    for q in qs:
        text = re.sub(r'\s+', ' ', q['text']).strip()
        opts = [(re.sub(r'\s+', ' ', t).strip(), c) for t, c in q['options'] if t.strip()]
        if len(text) < 8 or len(opts) < min_opts:
            continue
        if len(opts) > 10:
            continue
        ncorrect = sum(1 for _, c in opts if c)
        if ncorrect == 0:
            continue
        item = {
            'subject': subject, 'topic': q.get('topic') or None, 'lang': lang,
            'type': 'multi' if ncorrect > 1 else 'single',
            'text': text,
            'options': [{'text': t, 'correct': c} for t, c in opts],
            'source': source,
        }
        if q.get('media'):
            item['media'] = q['media']
        if q.get('passage'):
            item['passage'] = q['passage'][:1500]
        QUESTIONS.append(item)
        kept += 1
    STATS.append((source, subject, len(qs), kept))
    return kept

# ---------- helpers ----------
QSTART = re.compile(r'^\s*(?:#\s*)?(\d{1,3})\s*[.)…—–-]+\s*(.*)')
OPT_LETTER = re.compile(r'^\s*([A-HА-НЁ])\s*[).]\s*(.*)')

KAZ_FIX = str.maketrans({
    'Ј':'Ә','ј':'ә','Є':'Ғ','є':'ғ','Ќ':'Қ','ќ':'қ','Ѕ':'Ң','ѕ':'ң',
    'Ґ':'Ө','ґ':'ө','Ў':'Ұ','ў':'ұ','Ї':'Ү','ї':'ү',
})

def docx_paras(path):
    """[(text, bold)] for each non-empty paragraph."""
    z = zipfile.ZipFile(path)
    root = ET.fromstring(z.read('word/document.xml'))
    out = []
    for par in root.iter(W + 'p'):
        txt, bold = '', False
        for r in par.findall('.//' + W + 'r'):
            t = ''.join(e.text or '' for e in r.findall(W + 't'))
            rpr = r.find(W + 'rPr')
            b = rpr is not None and rpr.find(W + 'b') is not None and \
                (rpr.find(W + 'b').get(W + 'val') != '0')
            if t.strip() and b:
                bold = True
            txt += t
        if txt.strip():
            out.append((txt.strip(), bold))
    return out

def pdf_lines(path, red_green=False):
    """[(text, marked)] per line; marked = bold (or red/green when red_green)."""
    doc = fitz.open(path)
    out = []
    for page in doc:
        for b in page.get_text('dict')['blocks']:
            for l in b.get('lines', []):
                text, marked = '', False
                for s in l['spans']:
                    if s['text'].strip():
                        if red_green:
                            c = s['color']
                            r, g, bl = c >> 16 & 255, c >> 8 & 255, c & 255
                            if (r > 170 and g < 110 and bl < 110) or (g > 130 and r < 110):
                                marked = True
                        else:
                            if s['flags'] & 16:
                                marked = True
                    text += s['text']
                if text.strip():
                    out.append((text.strip(), marked))
    doc.close()
    return out

def lines_to_questions(lines, opts_by_letter=True, mark_on_question_ok=False):
    """Generic: numbered question lines + lettered/marked option lines.
    lines: [(text, marked)]"""
    qs, cur, opts, in_opts = [], None, [], False
    def flush():
        nonlocal cur, opts
        if cur and opts:
            qs.append({'text': cur, 'options': opts})
        cur, opts = None, []
    for text, marked in lines:
        m = QSTART.match(text)
        lm = OPT_LETTER.match(text)
        if m and (not in_opts or not lm) and len(m.group(2)) > 0 or (m and lm is None):
            # new question line (numbered, not a letter-option)
            flush()
            cur = m.group(2)
            in_opts = False
        elif lm and cur is not None:
            opts.append([lm.group(2), marked])
            in_opts = True
        elif cur is not None:
            if in_opts and opts:
                opts[-1][0] += ' ' + text
                if marked:
                    opts[-1][1] = True
            else:
                cur += ' ' + text
    flush()
    return [{'text': q['text'], 'options': [(t, c) for t, c in q['options']]} for q in qs]

# ============================================================
# 1. Existing quiz_data JSON (already-verified platform questions)
# ============================================================
def src_quiz_data():
    data = json.load(open('quiz_data/all_quiz_data.json'))
    subj_map = {
        'Алгоритмы и структуры данных': 'algorithms',
        'Базы данных': 'databases',
        'Английский язык': 'english',
        'ТГО': 'tgo',
    }
    for group in ('algo_db', 'angl_tgo'):
        qs_by_subj = {}
        for variant in data.get(group, []):
            for q in variant['questions']:
                subj = subj_map.get(q.get('subject', ''), None)
                if subj is None:
                    s = (q.get('subject') or '').lower()
                    subj = ('english' if 'англ' in s or 'english' in s
                            else 'tgo' if 'тго' in s or 'готовности' in s
                            else 'algorithms' if 'алгоритм' in s
                            else 'databases' if 'баз' in s or 'дерек' in s else 'other')
                # Prefer the clean first TEXT block over the top-level text,
                # which has "[AUDIO: url]" / "[IMAGE: url]" markers appended.
                text = q['text']
                media = []
                for b in q.get('blocks', []):
                    if b['type'] == 'TEXT' and b['payload'].get('text'):
                        text = b['payload']['text']
                    elif b['type'] in ('AUDIO', 'IMAGE'):
                        fname = os.path.basename(b['payload'].get('url', ''))
                        if fname:
                            media.append({'type': b['type'].lower(), 'file': fname})
                text = re.sub(r'\s*\[(AUDIO|IMAGE|VIDEO):[^\]]*\]', '', text).strip()
                item = {
                    'text': text,
                    'topic': q.get('topic'),
                    'options': [(o['text'], o.get('is_correct', False)) for o in q.get('options', [])],
                    'media': media or None,
                }
                qs_by_subj.setdefault(subj, []).append(item)
        for subj, qs in qs_by_subj.items():
            lang = 'en' if subj == 'english' else 'ru'
            add_questions(qs, subj, lang, f'quiz_data/{group}')

# ============================================================
# 2. All.pdf — color-marked (red/green) English ICT bank with sections
# ============================================================
def src_all_pdf():
    doc = fitz.open('new-data/All.pdf')
    lines = []  # (text, red, green)
    for page in doc:
        for b in page.get_text('dict')['blocks']:
            for l in b.get('lines', []):
                text, red, green = '', False, False
                for s in l['spans']:
                    c = s['color']
                    r, g, bl = c >> 16 & 255, c >> 8 & 255, c & 255
                    st = s['text'].strip()
                    if st and st not in ('o', '•', '·', 'O'):
                        if r > 170 and g < 110:
                            red = True
                        if g > 130 and r < 110 and bl < 110:
                            green = True
                    text += s['text']
                text = text.strip().lstrip('•o ').strip() if text.strip().startswith(('•', 'o ')) else text.strip()
                if text:
                    lines.append((text, red, green))
    qs, cur, opts, topic = [], None, [], None
    def flush():
        nonlocal cur, opts
        if cur and opts:
            # green wins when present; single red = correct; multi-red = ambiguous, drop
            has_green = any(g for _, r, g in opts)
            n_red = sum(1 for _, r, g in opts if r)
            if has_green:
                final = [(t, g) for t, r, g in opts]
            elif n_red == 1:
                final = [(t, r) for t, r, g in opts]
            else:
                final = None
            if final:
                qs.append({'text': cur, 'options': final, 'topic': topic})
        cur, opts = None, []
    for text, red, green in lines:
        t = text
        if t in ('o', '•') or re.fullmatch(r'\d+', t):
            continue
        m = QSTART.match(t)
        if m and len(m.group(2)) > 2:
            flush()
            cur = m.group(2)
        elif cur is None:
            if len(t) < 60 and not m:
                topic = t  # section header like FIS
        else:
            if not opts and (t[0].islower() or cur.endswith((',', '-', '/', 'two', 'the', 'and', 'of'))):
                cur += ' ' + t
            elif opts and (t[0].islower() or opts[-1][0].endswith((',', '-', '/', 'the', 'and', 'of'))):
                opts[-1][0] += ' ' + t
                opts[-1][1] = opts[-1][1] or red
                opts[-1][2] = opts[-1][2] or green
            else:
                opts.append([t, red, green])
    flush()
    add_questions(qs, 'ict', 'en', 'All.pdf')

# ============================================================
# 3. $$$ / $$ / $ marker text files (ТСП, ТГО-98%)
# ============================================================
def parse_dollar(txtpath, qprefix='$$$'):
    qs, cur, opts = [], None, []
    def flush():
        nonlocal cur, opts
        if cur and opts:
            qs.append({'text': cur, 'options': opts})
        cur, opts = None, []
    for raw in open(txtpath, encoding='utf-8', errors='replace'):
        line = raw.strip().lstrip('﻿')
        if not line:
            continue
        if line.startswith('$$$'):
            flush()
            cur = re.sub(r'^\$\$\$\s*\d*\s*[.)]?\s*', '', line)
        elif line.startswith('$$'):
            if cur: opts.append((line[2:].strip(), True))
        elif line.startswith('$'):
            if cur: opts.append((line[1:].strip(), False))
        elif cur is not None and not opts:
            cur += ' ' + line
        elif cur is not None and opts:
            t, c = opts[-1]
            opts[-1] = (t + ' ' + line, c)
    flush()
    return qs

def parse_tgo98(txtpath):
    """#N. question ... then $$ correct / $ wrong options."""
    qs, cur, opts = [], None, []
    def flush():
        nonlocal cur, opts
        if cur and opts:
            qs.append({'text': cur, 'options': opts})
        cur, opts = None, []
    for raw in open(txtpath, encoding='utf-8', errors='replace'):
        line = raw.strip()
        if not line:
            continue
        if re.match(r'^#\s*\d+\s*[.)]', line):
            flush()
            cur = re.sub(r'^#\s*\d+\s*[.)]\s*', '', line)
        elif line.startswith('$$'):
            if cur: opts.append((line[2:].strip(), True))
        elif line.startswith('$'):
            if cur: opts.append((line[1:].strip(), False))
        elif cur is not None:
            if opts:
                t, c = opts[-1]
                # short trailing symbols like ◦ merge into option
                opts[-1] = (t + ' ' + line, c)
            else:
                cur += ' ' + line
    flush()
    return qs

# ============================================================
# 4. MyTest export (+1-17 ТСП ВСЕ): $$$NNN / ~%pct%option / E) wrong
# ============================================================
def parse_mytest(txtpath):
    qs, cur, opts = [], None, []
    def flush():
        nonlocal cur, opts
        if cur and opts:
            qs.append({'text': cur, 'options': opts})
        cur, opts = None, []
    started = False
    for raw in open(txtpath, encoding='utf-8', errors='replace'):
        line = raw.strip()
        if not line:
            continue
        if re.match(r'^\$\$\$\d+', line):
            flush()
            cur = ''
            started = True
            continue
        if not started:
            continue
        m = re.match(r'^~%(-?[\d.]+)%\s*(.*)', line)
        lm = OPT_LETTER.match(line)
        if m:
            opts.append((m.group(2), float(m.group(1)) > 0))
        elif lm and opts:
            opts.append((lm.group(2), False))
        elif cur is not None and not opts:
            cur = (cur + ' ' + line).strip()
        elif opts:
            t, c = opts[-1]
            opts[-1] = (t + ' ' + line, c)
    flush()
    return qs

# ============================================================
# 4b. English 300: numbered Q, then $$$correct / -wrong option lines
# ============================================================
JUNK = re.compile(r'(300 ВОПРОСОВ|ДОКУМЕНТ НЕ|@sam1dv|@cl\.durham|Almaty 20|Meldekhanov|НЕ ДЛЯ ПРОДАЖИ|РАСПРОСТРАНЯЕТСЯ)', re.I)
DASH = ('-', '–', '−', '‐', '—')

def parse_eng300(txtpath):
    qs, cur, opts = [], None, []
    def flush():
        nonlocal cur, opts
        if cur:
            # second half of the file lists options inline separated by ' $$ '
            parts = [p.strip() for p in cur.split('$$')]
            cur = parts[0]
            extra = [(p, False) for p in parts[1:] if p]
            expanded = []
            for t, c in opts:
                sub = [p.strip() for p in t.split('$$')]
                expanded.append((sub[0], c))
                expanded += [(p, False) for p in sub[1:] if p]
            opts = expanded + extra
            if opts:
                qs.append({'text': cur, 'options': opts})
        cur, opts = None, []
    for raw in open(txtpath, encoding='utf-8', errors='replace'):
        line = raw.strip()
        if not line or JUNK.search(line) or re.fullmatch(r'\d+', line):
            continue
        m = re.match(r'^(\d{1,3})\s*[.)…]+\s*(.*)', line)
        if m:
            flush(); cur = m.group(2)
        elif line.startswith('$$$'):
            if cur is not None:
                opts.append((line[3:].strip(), True))
        elif line.startswith(DASH) and cur is not None and len(line) > 1:
            opts.append((line[1:].strip(), False))
        elif cur is not None and not opts:
            cur += ' ' + line
        elif cur is not None and opts:
            t, c = opts[-1]
            opts[-1] = (t + ' ' + line, c)
    flush()
    return qs

# ============================================================
# 4c. Variant booklets with answer-key tables (Комбо, 240 №6)
# ============================================================
CYR2LAT = str.maketrans({'А':'A','В':'B','С':'C','Д':'D','Е':'E','Ә':'A'})

def booklet_questions(pdf_path, page_range, letters='A-EАВСДЕЕ'):
    """Extract numbered questions with lettered options + passages (МӘТІН/TEXT)."""
    doc = fitz.open(pdf_path)
    qs, cur, opts, qnum, passage, pbuf = [], None, [], None, None, None
    optre = re.compile(r'^\s*([' + letters + r'])\s*[).]\s*(.*)')
    def flush():
        nonlocal cur, opts
        if cur is not None and opts:
            qs.append({'num': qnum, 'text': cur, 'options': opts, 'passage': passage})
        cur, opts = None, []
    for pno in range(*page_range):
        for line in doc[pno].get_text().split('\n'):
            t = line.strip()
            if not t or JUNK.search(t):
                continue
            if re.match(r'^(МӘТІН|TEXT)\b', t) and len(t) < 30:
                flush()
                pbuf = []
                continue
            m = re.match(r'^(\d{1,2})\s*[.)]\s*(.*)', t)
            om = optre.match(t)
            if m and not om and len(m.group(2)) > 2:
                flush()
                if pbuf is not None:
                    passage = ' '.join(pbuf).strip() or None
                    pbuf = None
                qnum = int(m.group(1)); cur = m.group(2)
            elif om and cur is not None:
                opts.append([om.group(1).translate(CYR2LAT), om.group(2)])
            elif pbuf is not None:
                pbuf.append(t)
            elif cur is not None:
                if opts:
                    opts[-1][1] += ' ' + t
                else:
                    cur += ' ' + t
    flush()
    doc.close()
    return qs

def apply_key(qs, key):
    """key: {num: letter}; qs from booklet_questions."""
    out = []
    for q in qs:
        ans = key.get(q['num'])
        if not ans:
            continue
        opts = [(text, letter == ans) for letter, text in q['options']]
        if not any(c for _, c in opts):
            continue
        item = {'text': q['text'], 'options': opts}
        if q.get('passage'):
            item['passage'] = q['passage'][:1500]
        out.append(item)
    return out

def src_kombo():
    # answer key from Тест жауабы_1 тест.pdf text
    key_eng, key_odat = {}, {}
    cur = None
    nums, lets = [], []
    def drain():
        nonlocal nums, lets
        if cur is not None:
            for n, l in zip(nums, lets):
                cur[n] = l
        nums, lets = [], []
    for line in open('extracted/txt/Тест жауабы_1 тест.txt'):
        t = line.strip()
        if 'Ағылшын' in t:
            drain(); cur = key_eng
        elif 'ОДАТ' in t:
            drain(); cur = key_odat
        elif re.fullmatch(r'\d{1,2}', t):
            nums.append(int(t))
        elif re.fullmatch(r'[A-EА-Е]', t):
            lets.append(t.translate(CYR2LAT))
    drain()
    doc = fitz.open('new-data/Комбо 1 нұсқа.pdf')
    # find page where Сыни ойлау starts (ОДАТ section)
    split = 10
    for p in range(doc.page_count):
        if 'Сыни ойлау' in doc[p].get_text():
            split = p; break
    n = doc.page_count
    doc.close()
    eng = booklet_questions('new-data/Комбо 1 нұсқа.pdf', (0, split))
    odat = booklet_questions('new-data/Комбо 1 нұсқа.pdf', (split, n))
    add_questions(apply_key(eng, key_eng), 'english', 'en', 'Комбо 1 нұсқа (АНГЛ)')
    add_questions(apply_key(odat, key_odat), 'tgo', 'kk', 'Комбо 1 нұсқа (ОДАТ)')

def src_240n6():
    path = 'extracted/magistratura/Магистратура/Английский/240 №6.pdf'
    doc = fitz.open(path)
    # answer keys: english p81 (№ + 4 letters), tgo p82 (№ + 3 letters)
    def parse_key(pno, nvars):
        keys = [dict() for _ in range(nvars)]
        toks = doc[pno].get_text().split()
        i = 0
        while i < len(toks):
            m = re.fullmatch(r'(\d{1,2})\.', toks[i])
            if m:
                num = int(m.group(1))
                lets = []
                j = i + 1
                while j < len(toks) and len(lets) < nvars:
                    if re.fullmatch(r'[A-EА-Е]', toks[j]):
                        lets.append(toks[j].translate(CYR2LAT))
                        j += 1
                    else:
                        break
                if len(lets) == nvars:
                    for v in range(nvars):
                        keys[v][num] = lets[v]
                i = j
            else:
                i += 1
        return keys
    key_pages = {}
    for p in range(doc.page_count):
        t = doc[p].get_text()
        if 'АҒЫЛШЫН ЖАУАПТАРЫ' in t: key_pages['eng'] = p
        if 'ТГО ЖАУАПТАРЫ' in t: key_pages['tgo'] = p
    # variant section starts
    eng_starts, tgo_starts = [], []
    for p in range(doc.page_count):
        for line in doc[p].get_text().split('\n'):
            s = line.strip()
            if re.fullmatch(r'[ІI]{1,3}V?\s*нұсқа', s):
                if p < key_pages.get('tgo', 99) and p >= 42:
                    tgo_starts.append(p)
                elif p < 42:
                    eng_starts.append(p)
    eng_keys = parse_key(key_pages['eng'], 4)
    tgo_keys = parse_key(key_pages['tgo'], 3)
    doc.close()
    eng_bounds = eng_starts + [42]
    for v in range(min(4, len(eng_starts))):
        qs = booklet_questions(path, (eng_bounds[v], eng_bounds[v + 1]))
        add_questions(apply_key(qs, eng_keys[v]), 'english', 'en', f'240 №6 АНГЛ в.{v+1}')
    tgo_bounds = tgo_starts + [key_pages['tgo']]
    for v in range(min(3, len(tgo_starts))):
        qs = booklet_questions(path, (tgo_bounds[v], tgo_bounds[v + 1]))
        add_questions(apply_key(qs, tgo_keys[v]), 'tgo', 'kk', f'240 №6 ТГО в.{v+1}')

# ============================================================
# 4d. Flashcard docs (Q?answer / Q:answer in one paragraph)
# ============================================================
def add_flashcards_from_paras(paras, subject, lang, source):
    n = 0
    for text in paras:
        t = re.sub(r'\s+', ' ', text).strip().lstrip('•\t ')
        m = re.match(r'^(.{15,}?[?:])\s*(.{2,})$', t)
        if not m:
            continue
        FLASHCARDS.append({'subject': subject, 'lang': lang,
                           'question': m.group(1).rstrip(':?').strip(),
                           'answer': m.group(2).strip(), 'source': source})
        n += 1
    STATS.append((source + ' [flashcards]', subject, len(paras), n))

# ============================================================
# 5. V-format 0/1 flags (Kazakh 300 algorithm questions) — multi-answer
# ============================================================
def parse_v01(txtpath):
    qs, cur, opts, pending = [], None, [], None
    def flush():
        nonlocal cur, opts
        if cur and opts:
            qs.append({'text': cur, 'options': opts})
        cur, opts = None, []
    for raw in open(txtpath, encoding='utf-8', errors='replace'):
        line = raw.strip()
        if not line:
            continue
        if re.match(r'^V\d+\s*$', line):
            flush(); cur = ''; pending = None
        elif line in ('0', '1'):
            pending = (line == '1')
        elif cur is not None:
            if pending is not None:
                opts.append((line, pending)); pending = None
            elif not opts:
                cur = (cur + ' ' + line).strip()
            else:
                t, c = opts[-1]
                opts[-1] = (t + ' ' + line, c)
    flush()
    return qs

# ============================================================
# 6. ##### / ????? format (correct = first option), broken Kazakh encoding
# ============================================================
def parse_hash(txtpath):
    text = open(txtpath, encoding='utf-8', errors='replace').read().translate(KAZ_FIX)
    qs = []
    blocks = re.split(r'#####', text)
    for block in blocks[1:]:
        block = re.split(r'\?\?\?\?\?\d', block)[0]
        parts = re.split(r'\?\?\?\?\?', block)
        qtext = re.sub(r'\s+', ' ', parts[0]).strip()
        opts = [(re.sub(r'\s+', ' ', p).strip(), i == 0) for i, p in enumerate(parts[1:])]
        opts = [(t, c) for t, c in opts if t]
        if qtext and opts:
            qs.append({'text': qtext, 'options': opts})
    return qs

# ============================================================
# 7. Bold-marked docx (Q numbered, correct option = bold), topic headers
# ============================================================
TOPIC_RE = re.compile(r'(тақырып|сабақ|ТЕМА|Lesson|бөлім)', re.I)

def parse_docx_bold(path, topic_headers=True):
    paras = docx_paras(path)
    qs, cur, opts, topic, tbuf = [], None, [], None, []
    def flush():
        nonlocal cur, opts
        if cur and opts:
            qs.append({'text': cur, 'options': opts, 'topic': topic})
        cur, opts = None, []
    for text, bold in paras:
        m = QSTART.match(text)
        if m and len(m.group(2)) > 3:
            flush()
            if tbuf:
                topic = tbuf[-1]; tbuf = []
            cur = m.group(2)
        elif cur is None:
            if topic_headers and len(text) < 90:
                if TOPIC_RE.search(text):
                    tbuf = [text]
                elif tbuf:
                    tbuf.append(text)
                    tbuf = [' — '.join(tbuf[-2:])]
        else:
            if topic_headers and TOPIC_RE.search(text) and len(text) < 90:
                flush()
                tbuf = [text]
                continue
            lm = OPT_LETTER.match(text)
            opt_text = lm.group(2) if lm else text
            opt_text = opt_text.lstrip('•\t ').strip()
            if opt_text:
                opts.append((opt_text, bold))
    flush()
    # normalize topics like "5-ші сабақ — Заголовок"
    for q in qs:
        if q.get('topic'):
            q['topic'] = re.sub(r'\s+', ' ', q['topic'])[:80]
    return qs

# ============================================================
# 8. Bold/red-marked PDFs with numbered Q + lettered or plain options
# ============================================================
def parse_pdf_marked(path, red_green=False, letters=True):
    lines = pdf_lines(path, red_green=red_green)
    qs, cur, opts = [], None, []
    def flush():
        nonlocal cur, opts
        if cur and opts:
            qs.append({'text': cur, 'options': opts})
        cur, opts = None, []
    for text, marked in lines:
        m = QSTART.match(text)
        lm = OPT_LETTER.match(text)
        if m and not lm and len(m.group(2)) > 2:
            flush()
            cur = m.group(2)
        elif lm and cur is not None:
            opts.append([lm.group(2), marked])
        elif cur is not None:
            if opts:
                opts[-1][0] += ' ' + text
                opts[-1][1] = opts[-1][1] or marked
            else:
                cur += ' ' + text
    flush()
    return [{'text': q['text'], 'options': [(t, c) for t, c in q['options']]} for q in qs]

# ============================================================
# 9. до 2019 - 259 вопросов: numbered questions + answer-key table at end
# ============================================================
def src_do2019():
    path = 'extracted/magistratura/Магистратура/Английский/Английский основной/до 2019 - 259 вопросов.pdf'
    doc = fitz.open(path)
    full = '\n'.join(p.get_text() for p in doc)
    # questions
    qs = []
    cur, opts = None, []
    qnum = None
    nums = {}
    def flush():
        nonlocal cur, opts
        if cur and opts and qnum is not None:
            nums[qnum] = {'text': cur, 'options': opts}
        cur, opts = None, []
    lines = [l.strip() for l in full.split('\n') if l.strip()]
    i = 0
    merged = []
    while i < len(lines):
        # PDF splits "9." and question text into separate lines; letters too
        if re.fullmatch(r'\d{1,3}\.', lines[i]) and i + 1 < len(lines):
            merged.append(lines[i] + ' ' + lines[i + 1]); i += 2
        elif re.fullmatch(r'[A-E]\)', lines[i]) and i + 1 < len(lines):
            merged.append(lines[i] + ' ' + lines[i + 1]); i += 2
        else:
            merged.append(lines[i]); i += 1
    for line in merged:
        m = re.match(r'^(\d{1,3})\.\s+(.*)', line)
        lm = re.match(r'^([A-E])\)\s*(.*)', line)
        if m and len(m.group(2)) > 3:
            flush()
            qnum = int(m.group(1)); cur = m.group(2)
        elif lm and cur is not None:
            opts.append([lm.group(1), lm.group(2)])
        elif cur is not None and opts:
            opts[-1][1] += ' ' + line
        elif cur is not None:
            cur += ' ' + line
    flush()
    # answer key: last pages contain rows of numbers then letters
    key = {}
    tail = '\n'.join(p.get_text() for p in doc)  # tokens over whole doc tail
    tokens = tail.split()
    seq_nums, seq_lets = [], []
    for tok in tokens[-2000:]:
        if re.fullmatch(r'\d{1,3}', tok):
            seq_nums.append(int(tok))
        elif re.fullmatch(r'[A-E]', tok):
            seq_lets.append(tok)
    # pair in order
    for n, l in zip(seq_nums, seq_lets):
        key[n] = l
    out = []
    for n, q in nums.items():
        ans = key.get(n)
        if not ans:
            continue
        out.append({'text': q['text'],
                    'options': [(t, letter == ans) for letter, t in q['options']]})
    add_questions(out, 'english', 'en', 'до 2019 — 259 вопросов.pdf')

# ============================================================
# 10. БД (1).docx — flashcards (Q?answer;answer)
# ============================================================
FLASHCARDS = []
def src_bd1_flashcards():
    paras = docx_paras('extracted/rar/База Данных/База Данных/БД (1).docx')
    n = 0
    for text, bold in paras:
        t = re.sub(r'\s+', ' ', text).strip()
        m = re.match(r'^(.{15,}?[?:])\s*(.+)$', t)
        if not m:
            continue
        q, a = m.group(1).rstrip(':?').strip(), m.group(2).strip()
        if len(a) < 2:
            continue
        FLASHCARDS.append({'subject': 'databases', 'lang': 'kk', 'question': q,
                           'answer': a, 'source': 'БД (1).docx'})
        n += 1
    STATS.append(('БД (1).docx [flashcards]', 'databases', n, n))

# ============================================================
# RUN ALL SOURCES
# ============================================================
src_quiz_data()
src_all_pdf()

# ТСП ($$-format)
for p, name in [
    ('extracted/txt_zip/Магистратура__ТСП__ТСП - основной__ТСП - резервный (архив)__ТСП-325 (для всех - ТСП - КТ).txt', 'ТСП-325'),
    ('extracted/txt_zip/Магистратура__ТСП__ТСП - основной__+тсп 1(первый)__ТСП подготовительные вопросы для КТ.txt', 'ТСП подготовительные'),
    ('extracted/txt_zip/Магистратура__ТСП__ТСП - основной__+тсп 2(второй)__ТСП - 240.txt', 'ТСП-240'),
]:
    add_questions(parse_dollar(p), 'tsp', 'ru', name)
add_questions(parse_mytest('extracted/txt_zip/Магистратура__ТСП__ТСП - основной__+тсп по учебнику (160 воп)__Учебник WORD__+1-17 ТСП ВСЕ.txt'),
              'tsp', 'ru', 'ТСП учебник 1-17')

# English
add_questions(parse_eng300('extracted/txt_zip/Магистратура__Английский__300 ВОПРОСОВ АНГЛ-ГРАММАТИКА (1).txt'),
              'english', 'en', '300 вопросов грамматика')
src_do2019()
add_questions(parse_docx_bold('extracted/magistratura/Магистратура/АНГЛ/listening.docx', topic_headers=False),
              'english', 'en', 'listening.docx')
src_kombo()
src_240n6()

# ТГО
add_questions(parse_tgo98('extracted/txt_zip/Магистратура__Английский__ТГО-98%.txt'), 'tgo', 'kk', 'ТГО-98%')

# Algorithms
add_questions(parse_docx_bold('extracted/rar/Алгоритмы/Алгоритмы/Алгоритм тест.docx'),
              'algorithms', 'kk', 'Алгоритм тест.docx')
add_questions(parse_v01('extracted/txt/Algoritmy_i_struktury_dannykh_kazakhskiy_-_300_voprosov.txt'),
              'algorithms', 'kk', '300 вопросов (0/1)')
add_questions(parse_hash('extracted/txt/Test_Algoritmder_Derekter_Kurylymy_I_Programmalau_Azhx121_131.txt'),
              'algorithms', 'kk', 'Test Algoritmder (#####)')

# Databases
add_questions(parse_docx_bold('extracted/rar/База Данных/База Данных/БД (2).docx'),
              'databases', 'kk', 'БД (2).docx')
src_bd1_flashcards()

# Flashcards from answer-compilation docs
add_flashcards_from_paras([t for t, b in docx_paras('extracted/magistratura/Магистратура/Алгоритмы2/алгоритмсобранное_каз.docx')],
                          'algorithms', 'kk', 'алгоритмсобранное_каз')
add_flashcards_from_paras([t for t, b in docx_paras('extracted/magistratura/Магистратура/Алгоритмы2/алгобщеесобранное.docx')],
                          'algorithms', 'kk', 'алгобщеесобранное')
add_flashcards_from_paras(open('extracted/txt/алгоритм ответы.txt').read().split('\n'),
                          'algorithms', 'kk', 'алгоритм ответы')

# ============================================================
# CLEAN — fix parsing artifacts and drop unsalvageable questions
# ============================================================
# junk that leaked into option/question text from headers/footers
JUNK_SUFFIX = re.compile(
    r'\s*(ДОКУМЕНТ НЕ ДЛЯ ПРОДАЖ.*|АБСОЛЮТНО БЕСПЛАТНО.*|АВТОРЫ СТУДЕНТЫ.*|'
    r'РАСПРОСТРАНЯЕТСЯ БЕСПЛАТНО.*|@\w+.*|Алматы\s*20\d\d.*|Almaty\s*20\d\d.*)$', re.I)
# section markers that got parsed as options (reading/listening block labels)
SECTION_OPT = re.compile(r'^\s*(\d+\s*)?(чтение|слушание|reading|listening|тыңдалым|оқылым)\s*\??\s*$', re.I)
# a bare section label as a whole question
SECTION_Q = re.compile(r'^\s*(\d+\s*)?(чтение|слушание|reading|listening|тыңдалым|оқылым|text)\s*\d*\s*$', re.I)
LEAK_PREFIX = re.compile(r'^\s*(?:[Oo]\s+)?[A-HА-Е]\)\s*')   # "D) ", "O D) "
CODE_JUNK = re.compile(r'[{}]|^\}|miss rate|hit rate')       # merged code fragments
# references to a drawn figure lost during OCR (locative "shown in the graph/picture");
# unanswerable without the image, and no media file is recoverable for these sources.
ORPHAN_FIG = re.compile(
    r'(суретте|суреттегі|графикте|графиктегі|диаграммада|диаграммадағы|'
    r'кестеде көрсетілген|сызбада|сызбанұсқа|дөңгелек диаграмма|'
    r'на рисунке|на графике|на диаграмме|по графику|по диаграмме|на чертеже|см\. рис)', re.I)

def clean_option_text(t):
    t = LEAK_PREFIX.sub('', t)
    t = JUNK_SUFFIX.sub('', t)
    return re.sub(r'\s+', ' ', t).strip()

CLEANED = []
DROPPED = 0
for q in QUESTIONS:
    text = JUNK_SUFFIX.sub('', q['text']).strip()
    if SECTION_Q.match(text) or len(text) < 8:
        DROPPED += 1
        continue
    # drop questions that reference a lost figure and have no attached media
    if not q.get('media') and ORPHAN_FIG.search(text):
        DROPPED += 1
        continue
    # clean + dedupe options (preserve order, keep first correct instance)
    seen_opt, opts = set(), []
    for o in q['options']:
        ot = clean_option_text(o['text'])
        if not ot or SECTION_OPT.match(ot):
            continue
        low = ot.lower()
        if low in seen_opt:
            # same text seen: if this one is correct, promote existing to correct
            if o['correct']:
                for eo in opts:
                    if eo['text'].lower() == low:
                        eo['correct'] = True
            continue
        seen_opt.add(low)
        opts.append({'text': ot, 'correct': o['correct']})
    # drop questions with merged code fragments or an over-long option (Q+opts merged)
    if any(CODE_JUNK.search(o['text']) for o in opts) or any(len(o['text']) > 400 for o in opts):
        DROPPED += 1
        continue
    ncorrect = sum(1 for o in opts if o['correct'])
    if len(opts) < 2 or ncorrect == 0 or ncorrect == len(opts):
        DROPPED += 1
        continue
    q['text'] = re.sub(r'\s+', ' ', text).strip()
    q['options'] = opts
    q['type'] = 'multi' if ncorrect > 1 else 'single'
    CLEANED.append(q)

QUESTIONS = CLEANED

# ============================================================
# DEDUPE + OUTPUT
# ============================================================
seen = {}
unique = []
for q in QUESTIONS:
    key = (q['subject'], norm(q['text']),
           tuple(sorted(norm(o['text']) for o in q['options'])))
    if key in seen:
        continue
    seen[key] = True
    q['id'] = hashlib.md5(str(key).encode()).hexdigest()[:12]
    unique.append(q)

subjects = {
    'algorithms': {'name': 'Алгоритмы и структуры данных'},
    'databases': {'name': 'Базы данных'},
    'english': {'name': 'Английский язык'},
    'tgo': {'name': 'ТГО — тест готовности к обучению'},
    'ict': {'name': 'ИКТ (English bank)'},
    'tsp': {'name': 'ТСП'},
}
for sid in subjects:
    topics = sorted({q['topic'] for q in unique if q['subject'] == sid and q['topic']})
    subjects[sid]['topics'] = topics
    subjects[sid]['count'] = sum(1 for q in unique if q['subject'] == sid)

bank = {'subjects': subjects, 'questions': unique, 'flashcards': FLASHCARDS}
os.makedirs('extracted', exist_ok=True)
json.dump(bank, open('extracted/bank.json', 'w'), ensure_ascii=False)

print(f"{'SOURCE':50} {'SUBJ':12} {'raw':>5} {'kept':>5}")
for s, subj, raw, kept in STATS:
    print(f"{s[:50]:50} {subj:12} {raw:5} {kept:5}")
print(f"\nDropped by cleaning pass: {DROPPED}")
print(f"TOTAL unique questions: {len(unique)}  (after clean, before dedupe: {len(QUESTIONS)})")
print(f"Flashcards: {len(FLASHCARDS)}")
for sid, s in subjects.items():
    print(f"  {sid:12} {s['count']:5}  topics={len(s['topics'])}")
