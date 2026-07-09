import { useEffect, useMemo, useRef, useState } from 'react';
import { shuffle } from '../store';
import { LANG_LABEL } from '../constants';

function pickQuestions(bank, db, config) {
  if (config.qids) return config.qids;
  if (config.subject === 'kt-full') {
    const parts = [['english', 30], ['tgo', 30], ['algorithms', 20], ['databases', 20]];
    let out = [];
    for (const [subj, n] of parts) {
      const pool = bank.questions.filter(q => q.subject === subj);
      out = out.concat(shuffle(pool).slice(0, n).map(q => q.id));
    }
    return out;
  }
  let pool = bank.questions.filter(q => q.subject === config.subject);
  if (config.mode === 'practice') {
    const score = q => {
      const s = db.stat(q.id);
      if (s.seen === 0) return 0;
      if (s.bad >= s.ok) return 1;
      return 2;
    };
    pool = shuffle(pool).sort((a, b) => score(a) - score(b));
    return pool.slice(0, config.count).map(q => q.id);
  }
  return shuffle(pool).slice(0, config.count).map(q => q.id);
}

export default function Quiz({ bank, db, config, byId, bump, done }) {
  const [qids] = useState(() => pickQuestions(bank, db, config));
  const [idx, setIdx] = useState(0);
  const [picked, setPicked] = useState([]);
  const [checked, setChecked] = useState(false);
  const [answers, setAnswers] = useState({});
  const [finished, setFinished] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(config.minutes ? config.minutes * 60 : null);
  const [started] = useState(Date.now());
  const answersRef = useRef({}); // sync copy: finish() can run before setAnswers flushes

  const optionOrder = useMemo(() => {
    const map = {};
    for (const id of qids) {
      map[id] = shuffle(byId[id].options.map((_, i) => i));
    }
    return map;
  }, [qids, byId]);

  useEffect(() => {
    if (secondsLeft === null || finished) return;
    if (secondsLeft <= 0) { finish(); return; }
    const t = setTimeout(() => setSecondsLeft(s => s - 1), 1000);
    return () => clearTimeout(t);
  });

  if (qids.length === 0)
    return <main><p>Нет вопросов для этого режима.</p><button onClick={done}>← Назад</button></main>;

  const q = byId[qids[idx]];
  const order = optionOrder[q.id];
  const isMulti = q.type === 'multi';
  const isExam = config.mode === 'exam';

  function evaluate(pickedIdxs) {
    const correctIdxs = q.options.map((o, i) => (o.correct ? i : -1)).filter(i => i >= 0);
    return (
      pickedIdxs.length === correctIdxs.length &&
      pickedIdxs.every(i => q.options[i].correct)
    );
  }

  function submitCurrent(pickedIdxs) {
    const ok = evaluate(pickedIdxs);
    answersRef.current[q.id] = { picked: pickedIdxs, correct: ok };
    setAnswers(a => ({ ...a, [q.id]: { picked: pickedIdxs, correct: ok } }));
    db.record(q.id, ok);
    return ok;
  }

  function choose(origIdx) {
    if (checked) return;
    if (isMulti) {
      setPicked(p => (p.includes(origIdx) ? p.filter(x => x !== origIdx) : [...p, origIdx]));
      return;
    }
    if (isExam) {
      submitCurrent([origIdx]);
      next([origIdx]);
    } else {
      submitCurrent([origIdx]);
      setPicked([origIdx]);
      setChecked(true);
    }
  }

  function checkMulti() {
    if (picked.length === 0) return;
    submitCurrent(picked);
    if (isExam) next(picked);
    else setChecked(true);
  }

  function next() {
    setPicked([]);
    setChecked(false);
    if (idx + 1 >= qids.length) finish();
    else setIdx(idx + 1);
  }

  function finish() {
    if (finished) return;
    setFinished(true);
    setAnswers({ ...answersRef.current });
    const correct = Object.values(answersRef.current).filter(a => a.correct).length;
    if (isExam) {
      db.addExam({
        date: Date.now(),
        subject: config.subject,
        total: qids.length,
        correct,
        seconds: Math.round((Date.now() - started) / 1000),
      });
    }
    bump();
  }

  if (finished) {
    const results = qids.map(id => ({ q: byId[id], a: answers[id] }));
    const correct = results.filter(r => r.a?.correct).length;
    const pct = Math.round((correct / qids.length) * 100);
    return (
      <main>
        <h2>Результат: {correct} / {qids.length} ({pct}%)</h2>
        <p className={pct >= 70 ? 'good' : 'bad-text'}>
          {pct >= 70 ? '🎉 Отлично, проходной уровень!' : '📚 Стоит повторить — смотрите разбор ниже.'}
        </p>
        <button className="big" onClick={done}>← На главную</button>
        {results.map(({ q, a }, i) => (
          <div className={'q-item ' + (a?.correct ? 'ok-border' : 'bad-border')} key={q.id}>
            <div className="q-row"><b>{i + 1}.</b>&nbsp;<span className="q-text">{q.text}</span></div>
            <ul className="opts">
              {q.options.map((o, j) => {
                const was = a?.picked?.includes(j);
                return (
                  <li key={j} className={(o.correct ? 'correct' : '') + (was && !o.correct ? ' wrong' : '')}>
                    {o.correct ? '✓ ' : was ? '✗ ' : ''}{o.text}
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </main>
    );
  }

  const answered = Object.keys(answers).length;
  return (
    <main>
      <div className="quiz-top">
        <span>Вопрос {idx + 1} / {qids.length}</span>
        {secondsLeft !== null && (
          <span className={secondsLeft < 300 ? 'bad-text' : ''}>
            ⏱ {Math.floor(secondsLeft / 60)}:{String(secondsLeft % 60).padStart(2, '0')}
          </span>
        )}
        <span className="muted">{answered} отвечено</span>
      </div>
      <div className="bar slim"><div className="fill" style={{ width: `${(idx / qids.length) * 100}%` }} /></div>
      {q.passage && <div className="passage">{q.passage}</div>}
      <h3 className="quiz-q">
        <span className="lang-tag">{LANG_LABEL[q.lang]}</span> {q.text}
        {isMulti && <span className="multi-tag"> (несколько ответов)</span>}
      </h3>
      <div className="quiz-opts">
        {order.map(origIdx => {
          const o = q.options[origIdx];
          const sel = picked.includes(origIdx);
          let cls = 'opt';
          if (sel) cls += ' sel';
          if (checked && o.correct) cls += ' right';
          if (checked && sel && !o.correct) cls += ' wrong';
          return (
            <button key={origIdx} className={cls} onClick={() => choose(origIdx)}>
              {o.text}
            </button>
          );
        })}
      </div>
      <div className="quiz-actions">
        {isMulti && !checked && <button className="big" onClick={checkMulti}>Проверить</button>}
        {checked && <button className="big" onClick={() => next()}>Дальше →</button>}
        {isExam && <button onClick={() => next()}>Пропустить</button>}
        <button onClick={finish}>Завершить</button>
      </div>
    </main>
  );
}
