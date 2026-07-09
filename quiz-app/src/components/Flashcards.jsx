import { useMemo, useState } from 'react';

export default function Flashcards({ bank }) {
  const [subj, setSubj] = useState('');
  const [q, setQ] = useState('');
  const [i, setI] = useState(0);
  const [flip, setFlip] = useState(false);
  const cards = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return bank.flashcards.filter(
      c =>
        (!subj || c.subject === subj) &&
        (!needle || c.question.toLowerCase().includes(needle) || c.answer.toLowerCase().includes(needle))
    );
  }, [bank, subj, q]);
  const card = cards[Math.min(i, cards.length - 1)];
  const subjects = [...new Set(bank.flashcards.map(c => c.subject))];
  return (
    <main>
      <h2>Шпаргалки ({cards.length})</h2>
      <div className="filters">
        <select value={subj} onChange={e => { setSubj(e.target.value); setI(0); }}>
          <option value="">Все предметы</option>
          {subjects.map(s => <option key={s} value={s}>{bank.subjects[s]?.name || s}</option>)}
        </select>
        <input placeholder="Поиск…" value={q} onChange={e => { setQ(e.target.value); setI(0); }} />
      </div>
      {card ? (
        <>
          <div className={'flash' + (flip ? ' flipped' : '')} onClick={() => setFlip(f => !f)}>
            <div className="flash-side">{flip ? card.answer : card.question}</div>
            <div className="muted small">{flip ? 'ответ · клик — вопрос' : 'вопрос · клик — ответ'}</div>
          </div>
          <div className="pager">
            <button disabled={i === 0} onClick={() => { setI(i - 1); setFlip(false); }}>← Назад</button>
            <span>{i + 1} / {cards.length}</span>
            <button disabled={i >= cards.length - 1} onClick={() => { setI(i + 1); setFlip(false); }}>Вперёд →</button>
          </div>
        </>
      ) : (
        <p>Ничего не найдено.</p>
      )}
    </main>
  );
}
