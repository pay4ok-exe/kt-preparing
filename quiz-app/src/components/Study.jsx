import { useMemo, useState } from 'react';
import { LANG_LABEL } from '../constants';

export default function Study({ bank, db, subject, bump }) {
  const [q, setQ] = useState('');
  const [topic, setTopic] = useState('');
  const [lang, setLang] = useState('');
  const [page, setPage] = useState(0);
  const [open, setOpen] = useState({});
  const PER = 20;

  const all = useMemo(() => bank.questions.filter(x => x.subject === subject), [bank, subject]);
  const topics = bank.subjects[subject].topics || [];
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return all.filter(
      x =>
        (!topic || x.topic === topic) &&
        (!lang || x.lang === lang) &&
        (!needle ||
          x.text.toLowerCase().includes(needle) ||
          x.options.some(o => o.text.toLowerCase().includes(needle)))
    );
  }, [all, q, topic, lang]);

  const pages = Math.max(1, Math.ceil(filtered.length / PER));
  const cur = Math.min(page, pages - 1);
  const slice = filtered.slice(cur * PER, cur * PER + PER);

  return (
    <main>
      <h2>{bank.subjects[subject].name} — режим изучения</h2>
      <div className="filters">
        <input placeholder="Поиск по вопросам…" value={q} onChange={e => { setQ(e.target.value); setPage(0); }} />
        {topics.length > 0 && (
          <select value={topic} onChange={e => { setTopic(e.target.value); setPage(0); }}>
            <option value="">Все темы ({topics.length})</option>
            {topics.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        )}
        <select value={lang} onChange={e => { setLang(e.target.value); setPage(0); }}>
          <option value="">Все языки</option>
          <option value="ru">Русский</option>
          <option value="kk">Қазақша</option>
          <option value="en">English</option>
        </select>
        <span className="muted">{filtered.length} вопросов</span>
      </div>
      {slice.map(x => {
        const shown = open[x.id];
        const st = db.stat(x.id);
        return (
          <div className="q-item" key={x.id}>
            <div className="q-row" onClick={() => setOpen(o => ({ ...o, [x.id]: !o[x.id] }))}>
              <span className="lang-tag">{LANG_LABEL[x.lang]}</span>
              <span className="q-text">{x.text}</span>
              <button
                className={'star' + (db.isBookmarked(x.id) ? ' on' : '')}
                onClick={e => { e.stopPropagation(); db.toggleBookmark(x.id); bump(); }}
                title="В закладки"
              >★</button>
            </div>
            {x.topic && <div className="topic-tag">{x.topic}</div>}
            {shown && (
              <ul className="opts">
                {x.passage && <li className="passage">{x.passage}</li>}
                {x.options.map((o, i) => (
                  <li key={i} className={o.correct ? 'correct' : ''}>
                    {o.correct ? '✓ ' : ''}{o.text}
                  </li>
                ))}
                {st.seen > 0 && (
                  <li className="muted small">Ваши ответы: верно {st.ok}, неверно {st.bad}</li>
                )}
              </ul>
            )}
          </div>
        );
      })}
      <div className="pager">
        <button disabled={cur === 0} onClick={() => setPage(cur - 1)}>← Назад</button>
        <span>{cur + 1} / {pages}</span>
        <button disabled={cur >= pages - 1} onClick={() => setPage(cur + 1)}>Вперёд →</button>
      </div>
    </main>
  );
}
