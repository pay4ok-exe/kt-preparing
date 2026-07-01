#!/usr/bin/env python3
"""Brute-force correct answers by submitting multiple times and comparing scores."""

import urllib.request
import urllib.error
import json
import time
import os
import sys

API = 'https://zhay-api.piupiu.kz'
OUTPUT_DIR = '/Users/javascript/Desktop/kt/quiz_data'
TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzZXNzaW9uSWQiOiIyYWVjM2MyMC03ZDZjLTRiZTYtOTA5YS1iNDgyODVmZWUwNDAiLCJ1c2VySWQiOjE2NywidXNlcm5hbWUiOiJwYXk0b2tfZXhlIiwiaWF0IjoxNzgyOTE4MzI1LCJleHAiOjE3ODU1MTAzMjV9.PN__oNm72rMpS_ewZBCKL4675Sag-8wInjK9e9OYMe8'

HEADERS = {
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
    'origin': 'https://zhay.piupiu.kz',
    'referer': 'https://zhay.piupiu.kz/',
    'content-type': 'application/json',
    'authorization': f'Bearer {TOKEN}',
}


def api_request(method, path, body=None):
    url = f'{API}/{path}'
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body_text = e.read().decode()
            if e.code == 429:
                wait = 10 * (attempt + 1)
                print(f'  ⏳ Rate limited, waiting {wait}s...', flush=True)
                time.sleep(wait)
                req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
                continue
            try:
                return e.code, json.loads(body_text)
            except json.JSONDecodeError:
                return e.code, {'raw': body_text}
        except Exception as e:
            if attempt < 2:
                time.sleep(3)
                req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
                continue
            return 0, {'error': str(e)}
    return 0, {'error': 'max retries'}


def start_and_submit(variant_id, answers):
    """Start a new attempt and immediately submit with given answers. Returns score (as percentage*total/100)."""
    # Start
    status, data = api_request('POST', f'quiz/start/{variant_id}')
    if status != 200:
        return None, None

    attempt_id = data.get('attempt_id')
    total = data.get('total')

    # Submit
    status, result = api_request('POST', f'quiz/submit/{attempt_id}', {'answers': answers})
    if status != 200:
        return None, total

    # correct_count may be None for unpaid, but score_percent is always available
    score = result.get('correct_count')
    if score is None:
        pct = result.get('score_percent', 0)
        score = round(pct * total / 100)
    return score, total


def deduce_answers(variant_id, questions):
    """Deduce correct answers by submitting multiple times."""
    total = len(questions)
    print(f'\n{"="*60}', flush=True)
    print(f'  Deduce: {variant_id} ({total} questions)', flush=True)
    print(f'{"="*60}', flush=True)

    # Build answer dicts
    # Option indices: 0=A, 1=B, 2=C, 3=D, 4=E, 5=F
    q_ids = [q['question_id'] for q in questions]
    q_options = [q['options'] for q in questions]
    q_types = [q.get('type', 'single_choice') for q in questions]

    correct_answers = {}  # question_id -> [option_id]
    solved = [False] * total

    # ── Round 1: Submit all option-0 (A) as baseline ──
    print(f'  Round 1: baseline (all A)...', flush=True)
    baseline_answers = {qid: [q_options[i][0]['id']] for i, qid in enumerate(q_ids)}
    baseline_score, _ = start_and_submit(variant_id, baseline_answers)
    print(f'  Baseline score: {baseline_score}/{total}', flush=True)
    time.sleep(0.2)

    if baseline_score is None:
        print(f'  ❌ Failed to get baseline score', flush=True)
        return None

    # If baseline is perfect, all A's are correct
    if baseline_score == total:
        for i, qid in enumerate(q_ids):
            correct_answers[qid] = [q_options[i][0]['id']]
            solved[i] = True
        print(f'  ✅ All A answers correct!', flush=True)
        return correct_answers

    # ── Round 2: For each question, try option-1 (B) ──
    print(f'  Round 2: trying B for each question...', flush=True)
    unsolved_after_b = []

    for i in range(total):
        if solved[i]:
            continue
        # Change only question i to option B (index 1)
        test_answers = dict(baseline_answers)
        if len(q_options[i]) > 1:
            test_answers[q_ids[i]] = [q_options[i][1]['id']]
            score, _ = start_and_submit(variant_id, test_answers)

            if score is None:
                print(f'  ⚠️ Q{i+1}: submit failed, skipping', flush=True)
                unsolved_after_b.append(i)
                continue

            if score > baseline_score:
                # B is correct
                correct_answers[q_ids[i]] = [q_options[i][1]['id']]
                solved[i] = True
                print(f'  ✅ Q{i+1}: B is correct (score {score})', flush=True)
            elif score < baseline_score:
                # A was correct
                correct_answers[q_ids[i]] = [q_options[i][0]['id']]
                solved[i] = True
                print(f'  ✅ Q{i+1}: A is correct (score {score})', flush=True)
            else:
                # Neither A nor B
                unsolved_after_b.append(i)
                print(f'  ❓ Q{i+1}: neither A nor B (score {score})', flush=True)

            time.sleep(0.15)

    # ── Round 3: For remaining, try option-2 (C) ──
    if unsolved_after_b:
        print(f'  Round 3: trying C for {len(unsolved_after_b)} remaining...', flush=True)
        unsolved_after_c = []

        for i in unsolved_after_b:
            if solved[i]:
                continue
            test_answers = dict(baseline_answers)
            if len(q_options[i]) > 2:
                test_answers[q_ids[i]] = [q_options[i][2]['id']]
                score, _ = start_and_submit(variant_id, test_answers)

                if score is None:
                    unsolved_after_c.append(i)
                    continue

                if score > baseline_score:
                    correct_answers[q_ids[i]] = [q_options[i][2]['id']]
                    solved[i] = True
                    print(f'  ✅ Q{i+1}: C is correct (score {score})', flush=True)
                elif score < baseline_score:
                    # A was correct (shouldn't happen since we already tested this in round 2)
                    correct_answers[q_ids[i]] = [q_options[i][0]['id']]
                    solved[i] = True
                else:
                    # Neither A, B, nor C → D (or E) is correct
                    unsolved_after_c.append(i)
                    print(f'  ❓ Q{i+1}: not A,B,C (score {score})', flush=True)

                time.sleep(0.15)

        # ── Round 4: For remaining, try option-3 (D) ──
        if unsolved_after_c:
            print(f'  Round 4: trying D for {len(unsolved_after_c)} remaining...', flush=True)
            for i in unsolved_after_c:
                if solved[i]:
                    continue
                test_answers = dict(baseline_answers)
                if len(q_options[i]) > 3:
                    test_answers[q_ids[i]] = [q_options[i][3]['id']]
                    score, _ = start_and_submit(variant_id, test_answers)

                    if score is not None and score > baseline_score:
                        correct_answers[q_ids[i]] = [q_options[i][3]['id']]
                        solved[i] = True
                        print(f'  ✅ Q{i+1}: D is correct (score {score})', flush=True)
                    else:
                        # Must be E or F
                        if len(q_options[i]) > 4:
                            # Try E
                            test_answers[q_ids[i]] = [q_options[i][4]['id']]
                            score2, _ = start_and_submit(variant_id, test_answers)
                            if score2 is not None and score2 > baseline_score:
                                correct_answers[q_ids[i]] = [q_options[i][4]['id']]
                                solved[i] = True
                                print(f'  ✅ Q{i+1}: E is correct', flush=True)
                            elif len(q_options[i]) > 5:
                                # Must be F
                                correct_answers[q_ids[i]] = [q_options[i][5]['id']]
                                solved[i] = True
                                print(f'  ✅ Q{i+1}: F is correct (deduced)', flush=True)
                            else:
                                print(f'  ❌ Q{i+1}: could not determine', flush=True)
                        else:
                            print(f'  ❌ Q{i+1}: could not determine (score {score})', flush=True)

                    time.sleep(0.15)

    # Handle multiple choice questions separately (try all combinations)
    for i in range(total):
        if not solved[i] and 'multiple' in q_types[i]:
            print(f'  🔧 Q{i+1}: multiple choice, trying combos...', flush=True)
            # Try all single options to find which are correct
            correct_opts = []
            for j, opt in enumerate(q_options[i]):
                test_answers = dict(baseline_answers)
                test_answers[q_ids[i]] = [opt['id']]
                score, _ = start_and_submit(variant_id, test_answers)
                if score is not None and score > baseline_score:
                    correct_opts.append(opt['id'])
                    print(f'    Option {j+1} ({chr(65+j)}) is correct', flush=True)
                time.sleep(0.15)

            if correct_opts:
                correct_answers[q_ids[i]] = correct_opts
                solved[i] = True
            else:
                # Maybe need multiple selected
                print(f'    Trying all combinations...', flush=True)
                from itertools import combinations
                for r in range(2, len(q_options[i]) + 1):
                    for combo in combinations(range(len(q_options[i])), r):
                        test_answers = dict(baseline_answers)
                        test_answers[q_ids[i]] = [q_options[i][k]['id'] for k in combo]
                        score, _ = start_and_submit(variant_id, test_answers)
                        if score is not None and score > baseline_score:
                            correct_answers[q_ids[i]] = [q_options[i][k]['id'] for k in combo]
                            solved[i] = True
                            print(f'    Found combo: {[chr(65+k) for k in combo]}', flush=True)
                            break
                    if solved[i]:
                        break
                    time.sleep(0.15)

    solved_count = sum(solved)
    print(f'\n  📊 Solved: {solved_count}/{total}', flush=True)

    # Fill in unsolved with best guess (option A)
    for i in range(total):
        if not solved[i]:
            correct_answers[q_ids[i]] = [q_options[i][0]['id']]
            print(f'  ⚠️ Q{i+1}: using default (A) - could not determine', flush=True)

    return correct_answers


def update_variant_file(variant_id, correct_answers):
    """Update the variant JSON file with correct answers."""
    fpath = os.path.join(OUTPUT_DIR, f'{variant_id}.json')
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Add correct_option_ids to each question
    for q in data.get('questions', []):
        qid = q['question_id']
        if qid in correct_answers:
            q['correct_option_ids'] = correct_answers[qid]
            # Also mark options
            for opt in q.get('options', []):
                opt['is_correct'] = opt['id'] in correct_answers[qid]

    # Update results to mark as having answers
    if data.get('results'):
        data['results']['is_paid'] = True
        data['results']['questions'] = data['questions']

    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'  💾 Updated {fpath}', flush=True)


def main():
    # Find all locked variants (no answers)
    locked_variants = []
    for fname in sorted(os.listdir(OUTPUT_DIR)):
        if not fname.endswith('.json') or fname in ('all_quiz_data.json', 'demo.json'):
            continue
        fpath = os.path.join(OUTPUT_DIR, fname)
        with open(fpath, 'r') as f:
            data = json.load(f)
        results = data.get('results', {})
        if not results.get('questions'):
            locked_variants.append((fname.replace('.json', ''), data))

    print(f'Found {len(locked_variants)} locked variants to deduce answers for', flush=True)

    for vid, data in locked_variants:
        questions = data.get('questions', [])
        if not questions:
            continue

        correct = deduce_answers(vid, questions)
        if correct:
            update_variant_file(vid, correct)

        time.sleep(1)

    # Rebuild all_quiz_data.json
    print('\n📦 Rebuilding all_quiz_data.json...', flush=True)
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
    print('✅ Done!', flush=True)


if __name__ == '__main__':
    main()
