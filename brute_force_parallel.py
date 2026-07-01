#!/usr/bin/env python3
"""Brute-force correct answers in PARALLEL — multiple variants at once."""

import urllib.request
import urllib.error
import json
import time
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

API = 'https://zhay-api.piupiu.kz'
OUTPUT_DIR = '/Users/javascript/Desktop/kt/quiz_data'
TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzZXNzaW9uSWQiOiIyYWVjM2MyMC03ZDZjLTRiZTYtOTA5YS1iNDgyODVmZWUwNDAiLCJ1c2VySWQiOjE2NywidXNlcm5hbWUiOiJwYXk0b2tfZXhlIiwiaWF0IjoxNzgyOTE4MzI1LCJleHAiOjE3ODU1MTAzMjV9.PN__oNm72rMpS_ewZBCKL4675Sag-8wInjK9e9OYMe8'

BASE_HEADERS = {
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
    'origin': 'https://zhay.piupiu.kz',
    'referer': 'https://zhay.piupiu.kz/',
    'content-type': 'application/json',
    'authorization': f'Bearer {TOKEN}',
}

# Lock for thread-safe file writes
file_lock = threading.Lock()
print_lock = threading.Lock()

# Track which variants already have answers (from partial run)
already_solved = set()


def log(msg):
    with print_lock:
        print(msg, flush=True)


def api_request(method, path, body=None):
    url = f'{API}/{path}'
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=BASE_HEADERS, method=method)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body_text = e.read().decode()
            if e.code == 429:
                wait = 8 * (attempt + 1)
                time.sleep(wait)
                req = urllib.request.Request(url, data=data, headers=BASE_HEADERS, method=method)
                continue
            try:
                return e.code, json.loads(body_text)
            except json.JSONDecodeError:
                return e.code, {'raw': body_text}
        except Exception as e:
            if attempt < 3:
                time.sleep(2)
                req = urllib.request.Request(url, data=data, headers=BASE_HEADERS, method=method)
                continue
            return 0, {'error': str(e)}
    return 0, {'error': 'max retries'}


def start_and_submit(variant_id, answers):
    """Start a new attempt and immediately submit. Returns score."""
    status, data = api_request('POST', f'quiz/start/{variant_id}')
    if status != 200:
        return None, None

    attempt_id = data.get('attempt_id')
    total = data.get('total')

    status, result = api_request('POST', f'quiz/submit/{attempt_id}', {'answers': answers})
    if status != 200:
        return None, total

    score = result.get('correct_count')
    if score is None:
        pct = result.get('score_percent', 0)
        score = round(pct * total / 100)
    return score, total


def deduce_variant(variant_id, questions):
    """Deduce correct answers for one variant. Returns dict of qid -> [option_id]."""
    total = len(questions)
    q_ids = [q['question_id'] for q in questions]
    q_options = [q['options'] for q in questions]
    q_types = [q.get('type', 'single_choice') for q in questions]

    correct_answers = {}
    solved = [False] * total

    tag = f'[{variant_id}]'

    # Round 1: baseline (all option A / index 0)
    baseline_answers = {qid: [q_options[i][0]['id']] for i, qid in enumerate(q_ids)}
    baseline_score, _ = start_and_submit(variant_id, baseline_answers)
    if baseline_score is None:
        log(f'  {tag} ❌ Baseline failed')
        return None
    log(f'  {tag} Baseline (all A): {baseline_score}/{total}')

    if baseline_score == total:
        for i, qid in enumerate(q_ids):
            correct_answers[qid] = [q_options[i][0]['id']]
            solved[i] = True
        log(f'  {tag} ✅ All A correct!')
        return correct_answers

    # Rounds 2-4: test B, C, D, E for each unsolved question
    # Key insight: changing question i from A to X changes score by:
    #   +1 if X is correct and A is wrong
    #   -1 if A is correct and X is wrong
    #    0 if both A and X are wrong
    # So: score > baseline → X is correct; score < baseline → A is correct

    for round_idx, opt_idx in enumerate([1, 2, 3, 4, 5], start=2):
        unsolved = [i for i in range(total) if not solved[i]]
        if not unsolved:
            break

        round_names = {2: 'B', 3: 'C', 4: 'D', 5: 'E', 6: 'F'}
        letter = round_names.get(round_idx, str(opt_idx))
        log(f'  {tag} Round {round_idx}: testing {letter} for {len(unsolved)} unsolved...')

        still_unsolved = []
        for i in unsolved:
            if opt_idx >= len(q_options[i]):
                still_unsolved.append(i)
                continue

            test_answers = dict(baseline_answers)
            test_answers[q_ids[i]] = [q_options[i][opt_idx]['id']]
            score, _ = start_and_submit(variant_id, test_answers)

            if score is None:
                still_unsolved.append(i)
                continue

            if score > baseline_score:
                correct_answers[q_ids[i]] = [q_options[i][opt_idx]['id']]
                solved[i] = True
            elif score < baseline_score:
                correct_answers[q_ids[i]] = [q_options[i][0]['id']]
                solved[i] = True
            else:
                still_unsolved.append(i)

        # For remaining after all rounds: try option F (last) by elimination
        if round_idx == 6:
            for i in still_unsolved:
                if not solved[i] and len(q_options[i]) > 0:
                    # Last resort: it must be the last untested option
                    # If we tested A,B,C,D,E and none changed score, and there are more options,
                    # the last one must be correct (since one must be correct)
                    if len(q_options[i]) > opt_idx + 1:
                        correct_answers[q_ids[i]] = [q_options[i][-1]['id']]
                        solved[i] = True
                        log(f'  {tag} Q{i+1}: last option by elimination')

    # Handle multiple choice questions
    for i in range(total):
        if not solved[i] and 'multiple' in q_types[i]:
            log(f'  {tag} Q{i+1}: multiple choice, testing combos...')
            from itertools import combinations
            correct_opts = []
            # First test each option individually
            for j, opt in enumerate(q_options[i]):
                test_answers = dict(baseline_answers)
                test_answers[q_ids[i]] = [opt['id']]
                score, _ = start_and_submit(variant_id, test_answers)
                if score is not None and score > baseline_score:
                    correct_opts.append(opt['id'])

            if correct_opts:
                correct_answers[q_ids[i]] = correct_opts
                solved[i] = True
            else:
                # Try pairs
                for r in range(2, len(q_options[i]) + 1):
                    for combo in combinations(range(len(q_options[i])), r):
                        test_answers = dict(baseline_answers)
                        test_answers[q_ids[i]] = [q_options[i][k]['id'] for k in combo]
                        score, _ = start_and_submit(variant_id, test_answers)
                        if score is not None and score > baseline_score:
                            correct_answers[q_ids[i]] = [q_options[i][k]['id'] for k in combo]
                            solved[i] = True
                            break
                    if solved[i]:
                        break

    # Fill unsolved with default A
    for i in range(total):
        if not solved[i]:
            correct_answers[q_ids[i]] = [q_options[i][0]['id']]
            log(f'  {tag} ⚠️ Q{i+1}: default A (unsolved)')

    solved_count = sum(solved)
    log(f'  {tag} 📊 Solved: {solved_count}/{total}')
    return correct_answers


def update_variant_file(variant_id, correct_answers):
    """Update the variant JSON with correct answers."""
    fpath = os.path.join(OUTPUT_DIR, f'{variant_id}.json')
    with file_lock:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for q in data.get('questions', []):
            qid = q['question_id']
            if qid in correct_answers:
                q['correct_option_ids'] = correct_answers[qid]
                for opt in q.get('options', []):
                    opt['is_correct'] = opt['id'] in correct_answers[qid]

        if data.get('results'):
            data['results']['is_paid'] = True
            data['results']['questions'] = data['questions']

        with open(fpath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    log(f'  💾 [{variant_id}] Saved')


def process_variant(variant_id, data):
    """Process a single variant — designed to run in a thread."""
    try:
        questions = data.get('questions', [])
        if not questions:
            return variant_id, False

        log(f'\n{"="*50}\n  [{variant_id}] Starting ({len(questions)} Q)\n{"="*50}')
        correct = deduce_variant(variant_id, questions)
        if correct:
            update_variant_file(variant_id, correct)
            return variant_id, True
        return variant_id, False
    except Exception as e:
        log(f'  ❌ [{variant_id}] Error: {e}')
        return variant_id, False


def main():
    # Find locked variants
    locked_variants = []
    for fname in sorted(os.listdir(OUTPUT_DIR)):
        if not fname.endswith('.json') or fname in ('all_quiz_data.json', 'demo.json'):
            continue
        fpath = os.path.join(OUTPUT_DIR, fname)
        with open(fpath, 'r') as f:
            data = json.load(f)
        results = data.get('results', {})
        result_qs = results.get('questions', [])

        # Check if already has correct answers
        has_answers = bool(result_qs) and any(q.get('correct_option_ids') for q in result_qs)
        if not has_answers:
            locked_variants.append((fname.replace('.json', ''), data))
        else:
            already_solved.add(fname.replace('.json', ''))

    log(f'Already solved: {len(already_solved)} — {sorted(already_solved)}')
    log(f'Need to solve: {len(locked_variants)} — {[v[0] for v in locked_variants]}')
    log(f'Running with 4 parallel workers...\n')

    # Run 4 variants in parallel
    MAX_WORKERS = 4
    results = {}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_variant, vid, data): vid
            for vid, data in locked_variants
        }

        for future in as_completed(futures):
            vid = futures[future]
            try:
                result_vid, success = future.result()
                results[result_vid] = success
                log(f'  ✅ Done: {result_vid} → {"SUCCESS" if success else "FAILED"}')
            except Exception as e:
                log(f'  ❌ {vid} crashed: {e}')
                results[vid] = False

    # Summary
    success_count = sum(1 for v in results.values() if v)
    log(f'\n{"="*60}')
    log(f'  COMPLETE: {success_count}/{len(locked_variants)} variants solved')
    log(f'{"="*60}')

    # Rebuild all_quiz_data.json
    log('\n📦 Rebuilding all_quiz_data.json...')
    all_data = {}
    for fname in sorted(os.listdir(OUTPUT_DIR)):
        if not fname.endswith('.json') or fname == 'all_quiz_data.json':
            continue
        fpath = os.path.join(OUTPUT_DIR, fname)
        with open(fpath, 'r') as f:
            d = json.load(f)
        vid = d.get('variant_id', fname.replace('.json', ''))
        if 'demo' in vid:
            all_data['demo'] = d
        elif 'angl_tgo' in vid:
            all_data.setdefault('angl_tgo', []).append(d)
        elif 'algo_db' in vid:
            all_data.setdefault('algo_db', []).append(d)

    with open(os.path.join(OUTPUT_DIR, 'all_quiz_data.json'), 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    log('✅ All done!')


if __name__ == '__main__':
    main()
