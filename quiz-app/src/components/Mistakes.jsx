import { shuffle } from '../store';

export default function Mistakes({ bank, db, byId, setView }) {
  const ids = db.mistakes().filter(id => byId[id]);
  const marked = db.bookmarks().filter(id => byId[id]);
  return (
    <main>
      <h2>Работа над ошибками</h2>
      <p className="muted">{ids.length} вопросов, где ошибок больше, чем верных ответов · {marked.length} в закладках</p>
      <div className="actions">
        {ids.length > 0 && (
          <button className="big" onClick={() => setView({ name: 'quiz', key: Date.now(), mode: 'practice', qids: shuffle(ids).slice(0, 30) })}>
            ⚡ Тренировать ошибки
          </button>
        )}
        {marked.length > 0 && (
          <button className="big" onClick={() => setView({ name: 'quiz', key: Date.now(), mode: 'practice', qids: shuffle(marked).slice(0, 30) })}>
            ★ Тренировать закладки
          </button>
        )}
      </div>
      {ids.slice(0, 50).map(id => {
        const q = byId[id];
        const s = db.stat(id);
        return (
          <div className="q-item bad-border" key={id}>
            <div className="q-row"><span className="q-text">{q.text}</span></div>
            <ul className="opts">
              {q.options.filter(o => o.correct).map((o, i) => <li key={i} className="correct">✓ {o.text}</li>)}
              <li className="muted small">ошибок {s.bad} · верно {s.ok}</li>
            </ul>
          </div>
        );
      })}
      {ids.length === 0 && <p>Пока нет ошибок — пройдите тренировку! 💪</p>}
    </main>
  );
}
