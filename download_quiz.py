#!/usr/bin/env python3
"""Download all quiz data + media from zhay-api.piupiu.kz"""

import urllib.request
import urllib.error
import json
import time
import os
import re
import hashlib

API = 'https://zhay-api.piupiu.kz'
BASE_SITE = 'https://zhay.piupiu.kz'
OUTPUT_DIR = '/Users/javascript/Desktop/kt/quiz_data'
MEDIA_DIR = os.path.join(OUTPUT_DIR, 'media')

HEADERS = {
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
    'accept': '*/*',
    'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'origin': 'https://zhay.piupiu.kz',
    'referer': 'https://zhay.piupiu.kz/',
    'content-type': 'application/json',
}

TOKEN = os.environ.get('QUIZ_TOKEN', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzZXNzaW9uSWQiOiIyYWVjM2MyMC03ZDZjLTRiZTYtOTA5YS1iNDgyODVmZWUwNDAiLCJ1c2VySWQiOjE2NywidXNlcm5hbWUiOiJwYXk0b2tfZXhlIiwiaWF0IjoxNzgyOTE4MzI1LCJleHAiOjE3ODU1MTAzMjV9.PN__oNm72rMpS_ewZBCKL4675Sag-8wInjK9e9OYMe8')

# Track downloaded media to avoid duplicates
downloaded_media = set()


def api_request(method, path, body=None):
    url = f'{API}/{path}'
    headers = dict(HEADERS)
    if TOKEN:
        headers['Authorization'] = f'Bearer {TOKEN}'

    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body_text = e.read().decode()
            if e.code == 429:
                print(f'  ⏳ Rate limited, waiting {5*(attempt+1)}s...')
                time.sleep(5 * (attempt + 1))
                req = urllib.request.Request(url, data=data, headers=headers, method=method)
                continue
            try:
                return e.code, json.loads(body_text)
            except json.JSONDecodeError:
                return e.code, {'raw': body_text}
        except Exception as e:
            if attempt < 2:
                time.sleep(3)
                continue
            return 0, {'error': str(e)}
    return 0, {'error': 'max retries'}


def download_file(url, filepath):
    """Download a binary file."""
    if os.path.exists(filepath):
        return True

    req = urllib.request.Request(url, headers={
        'user-agent': HEADERS['user-agent'],
        'referer': 'https://zhay.piupiu.kz/',
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'wb') as f:
                f.write(data)
            return True
    except Exception as e:
        print(f'    ⚠️ Media download failed: {url[:60]}... — {e}')
        return False


def extract_media_urls(question):
    """Extract all media URLs from a question (blocks + inline text)."""
    urls = []
    q_text = question.get('text', '')

    # Inline [IMAGE: url] and [AUDIO: url]
    for m in re.finditer(r'\[IMAGE:\s*([^\]]+)\]', q_text):
        urls.append(('image', m.group(1).strip()))
    for m in re.finditer(r'\[AUDIO:\s*([^\]]+)\]', q_text):
        urls.append(('audio', m.group(1).strip()))

    # Blocks
    for block in question.get('blocks', []):
        btype = block.get('type', '').upper()
        payload = block.get('payload', {})
        content = block.get('content', '')

        if btype in ('IMAGE', 'image'):
            url = content or (payload.get('url') if payload else '')
            if url:
                urls.append(('image', url))
        elif btype in ('AUDIO', 'audio'):
            url = content or (payload.get('url') or payload.get('original_url') if payload else '')
            if url:
                urls.append(('audio', url))
        elif btype in ('CODE', 'code'):
            pass  # code is text, no media

    return urls


def resolve_media_url(url):
    """Resolve a media URL to absolute + local path."""
    if url.startswith('http'):
        abs_url = url
    elif url.startswith('/'):
        abs_url = BASE_SITE + url
    else:
        abs_url = BASE_SITE + '/' + url

    # Generate a filename from the URL path
    path_part = abs_url.split('/')[-1].split('?')[0]
    # If it has a query-less short name, hash to avoid collisions
    if '.' not in path_part:
        path_part = hashlib.md5(abs_url.encode()).hexdigest()[:12]

    return abs_url, path_part


def download_question_media(question):
    """Download all media for a question and update URLs to local paths."""
    media_items = extract_media_urls(question)

    for mtype, raw_url in media_items:
        abs_url, filename = resolve_media_url(raw_url)

        if abs_url in downloaded_media:
            continue

        ext_map = {'image': 'img', 'audio': 'audio'}
        subdir = ext_map.get(mtype, 'other')
        filepath = os.path.join(MEDIA_DIR, subdir, filename)

        print(f'    📎 Downloading {mtype}: {filename}')
        if download_file(abs_url, filepath):
            downloaded_media.add(abs_url)


def download_variant(variant_id, title, total_count):
    """Download all questions for a variant and submit to get answers."""
    print(f'\n{"="*60}')
    print(f'  {title} ({variant_id}) — {total_count} questions')
    print(f'{"="*60}')

    # Step 1: Start the quiz
    status, data = api_request('POST', f'quiz/start/{variant_id}')
    if status != 200:
        print(f'  ❌ Failed to start: {status} — {json.dumps(data, ensure_ascii=False)[:200]}')
        return None

    attempt_id = data.get('attempt_id')
    total = data.get('total', total_count)
    print(f'  ✅ Started. Attempt: {attempt_id[:12]}...  Questions: {total}')

    questions = []

    # First question comes with the start response
    if data.get('question'):
        q = data['question']
        questions.append(q)
        download_question_media(q)
        print(f'  📝 Q 1/{total}: {(q.get("text","") or "")[:50]}...')

    # Step 2: Fetch remaining questions
    for i in range(1, total):
        time.sleep(0.15)
        status, q_data = api_request('GET', f'quiz/question/{attempt_id}/{i}')
        if status != 200:
            print(f'  ❌ Q {i+1} failed: {status} — {json.dumps(q_data, ensure_ascii=False)[:150]}')
            continue

        q = q_data.get('question')
        if q:
            questions.append(q)
            download_question_media(q)
            print(f'  📝 Q {i+1}/{total}: {(q.get("text","") or "")[:50]}...')

    # Step 3: Submit to get correct answers
    # Submit with first option for each question as dummy answers
    answers = {}
    for q in questions:
        if q.get('options'):
            answers[q['question_id']] = [q['options'][0]['id']]

    print(f'  📤 Submitting for correct answers...')
    status, result = api_request('POST', f'quiz/submit/{attempt_id}', {'answers': answers})

    result_data = None
    if status == 200:
        result_data = result
        score = result.get('percentage', result.get('score', '?'))
        print(f'  ✅ Results received! Score: {score}%')
    else:
        print(f'  ⚠️ Submit returned {status}: {json.dumps(result, ensure_ascii=False)[:200]}')
        # Try empty answers
        status2, result2 = api_request('POST', f'quiz/submit/{attempt_id}', {'answers': {}})
        if status2 == 200:
            result_data = result2
            print(f'  ✅ Results (empty submit)!')
        else:
            print(f'  ⚠️ Empty submit failed too: {status2}')

    # Save
    variant_data = {
        'variant_id': variant_id,
        'title': title,
        'total_count': total,
        'attempt_id': attempt_id,
        'questions': questions,
        'results': result_data,
    }

    filename = os.path.join(OUTPUT_DIR, f'{variant_id}.json')
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(variant_data, f, ensure_ascii=False, indent=2)
    print(f'  💾 Saved: {filename}')

    return variant_data


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(MEDIA_DIR, exist_ok=True)
    os.makedirs(os.path.join(MEDIA_DIR, 'img'), exist_ok=True)
    os.makedirs(os.path.join(MEDIA_DIR, 'audio'), exist_ok=True)

    # Get all variants
    print('Fetching variants list...')
    status, variants = api_request('GET', 'quiz/variants')
    if status != 200:
        print(f'Failed to get variants: {status} — {variants}')
        return

    cats = variants.get('variants', {})
    print(f'Categories: {list(cats.keys())}')

    # Build list of all variants
    all_variants = []

    # Demo
    if isinstance(cats.get('demo'), dict):
        all_variants.append(('demo', cats['demo']))

    # angl_tgo
    for v in cats.get('angl_tgo', []):
        all_variants.append(('angl_tgo', v))

    # algo_db
    for v in cats.get('algo_db', []):
        all_variants.append(('algo_db', v))

    print(f'\nTotal variants to download: {len(all_variants)}')

    all_data = {}
    success = 0
    failed = 0

    for cat, vinfo in all_variants:
        vid = vinfo['id']
        title = vinfo['title']
        total = vinfo['total_count']

        # Skip already downloaded
        existing = os.path.join(OUTPUT_DIR, f'{vid}.json')
        if os.path.exists(existing):
            print(f'\n  ⏭️  Already downloaded: {vid}, skipping')
            with open(existing, 'r', encoding='utf-8') as f:
                result = json.load(f)
            if cat == 'demo':
                all_data['demo'] = result
            else:
                all_data.setdefault(cat, []).append(result)
            success += 1
            continue

        result = download_variant(vid, title, total)

        if result:
            if cat == 'demo':
                all_data['demo'] = result
            else:
                all_data.setdefault(cat, []).append(result)
            success += 1
        else:
            failed += 1

        time.sleep(0.3)  # pause between variants

    # Save combined
    combined = os.path.join(OUTPUT_DIR, 'all_quiz_data.json')
    with open(combined, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f'\n{"="*60}')
    print(f'  ✅ DONE!  Success: {success}  Failed: {failed}')
    print(f'  📁 Data: {combined}')
    print(f'  📁 Media: {MEDIA_DIR}  ({len(downloaded_media)} files)')
    print(f'{"="*60}')


if __name__ == '__main__':
    main()
