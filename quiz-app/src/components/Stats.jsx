export default function Stats({ bank, db }) {
  const stats = db.allStats();
  const total = Object.keys(stats).length;
  const answered = Object.values(stats).reduce((n, s) => n + s.seen, 0);
  const ok = Object.values(stats).reduce((n, s) => n + s.ok, 0);
  const exams = db.exams().slice(-15).reverse();
  return (
    <main>
      <h2>Статистика</h2>
      <div className="stat-grid">
        <div className="stat"><b>{total}</b><span>вопросов затронуто</span></div>
        <div className="stat"><b>{answered}</b><span>всего ответов</span></div>
        <div className="stat"><b>{answered ? Math.round((ok / answered) * 100) : 0}%</b><span>точность</span></div>
        <div className="stat"><b>{db.exams().length}</b><span>экзаменов пройдено</span></div>
      </div>
      <h3>Последние экзамены</h3>
      {exams.length === 0 && <p className="muted">Ещё не было экзаменов.</p>}
      {exams.map((e, i) => (
        <div className="q-item" key={i}>
          <div className="q-row">
            <span className="q-text">
              {new Date(e.date).toLocaleString('ru-RU')} · {bank.subjects[e.subject]?.name || (e.subject === 'kt-full' ? 'Полный КТ' : e.subject)}
            </span>
            <b className={e.correct / e.total >= 0.7 ? 'good' : 'bad-text'}>
              {e.correct}/{e.total} ({Math.round((e.correct / e.total) * 100)}%)
            </b>
          </div>
        </div>
      ))}
      <button
        onClick={() => { if (confirm('Сбросить весь прогресс?')) { db.reset(); location.reload(); } }}
        className="danger"
      >
        Сбросить прогресс
      </button>
    </main>
  );
}
