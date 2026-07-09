import { SUBJECT_META } from '../constants';

export default function Home({ bank, db, setView, tick }) {
  const subjects = Object.entries(bank.subjects).filter(([, s]) => s.count > 0);
  return (
    <main>
      <p className="intro">
        В банке <b>{bank.questions.length}</b> вопросов и <b>{bank.flashcards.length}</b> шпаргалок,
        собранных из всех ваших материалов. Прогресс сохраняется локально в браузере.
      </p>
      <div className="cards" data-tick={tick}>
        {subjects.map(([id, s]) => {
          const qids = bank.questions.filter(q => q.subject === id).map(q => q.id);
          const { seen, mastered } = db.seenCount(qids);
          const meta = SUBJECT_META[id] || { icon: '📚', color: '#64748b' };
          return (
            <div className="card" key={id} style={{ '--accent': meta.color }}>
              <div className="card-head">
                <span className="icon">{meta.icon}</span>
                <h2>{s.name}</h2>
              </div>
              <div className="counts">
                {s.count} вопросов · изучено {seen} · освоено {mastered}
              </div>
              <div className="bar">
                <div className="fill" style={{ width: `${(mastered / s.count) * 100}%` }} />
                <div className="fill seen" style={{ width: `${(seen / s.count) * 100}%` }} />
              </div>
              <div className="actions">
                <button onClick={() => setView({ name: 'study', subject: id })}>📖 Учить</button>
                <button onClick={() => setView({ name: 'quiz', key: Date.now(), mode: 'practice', subject: id, count: 20 })}>
                  ⚡ Тренировка
                </button>
                <button onClick={() => setView({ name: 'quiz', key: Date.now(), mode: 'exam', subject: id, count: 30, minutes: 45 })}>
                  ⏱️ Экзамен
                </button>
              </div>
            </div>
          );
        })}
      </div>
      <div className="full-exam">
        <button
          className="big"
          onClick={() =>
            setView({ name: 'quiz', key: Date.now(), mode: 'exam', subject: 'kt-full', count: 100, minutes: 150 })
          }
        >
          🏆 Полный КТ: Англ (30) + ТГО (30) + Алгоритмы (20) + БД (20), 150 минут
        </button>
      </div>
    </main>
  );
}
