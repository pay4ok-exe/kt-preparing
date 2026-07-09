import { useEffect, useState } from 'react';
import { db } from './store';
import Home from './components/Home';
import Study from './components/Study';
import Quiz from './components/Quiz';
import Mistakes from './components/Mistakes';
import Flashcards from './components/Flashcards';
import Stats from './components/Stats';
import './App.css';

export default function App() {
  const [bank, setBank] = useState(null);
  const [view, setView] = useState({ name: 'home' });
  const [tick, setTick] = useState(0);
  const bump = () => setTick(t => t + 1);

  useEffect(() => {
    fetch(import.meta.env.BASE_URL + 'data/bank.json')
      .then(r => r.json())
      .then(setBank)
      .catch(() => setBank({ error: true }));
  }, []);

  if (!bank) return <div className="loading">Загрузка банка вопросов…</div>;
  if (bank.error) return <div className="loading">Не удалось загрузить data/bank.json</div>;

  const byId = Object.fromEntries(bank.questions.map(q => [q.id, q]));
  const goHome = () => setView({ name: 'home' });

  return (
    <div className="app">
      <header>
        <h1 onClick={goHome}>🎓 KT Экзамен — Тренажёр</h1>
        <nav>
          <button onClick={goHome}>Главная</button>
          <button onClick={() => setView({ name: 'mistakes' })}>Ошибки</button>
          <button onClick={() => setView({ name: 'flash' })}>Шпаргалки</button>
          <button onClick={() => setView({ name: 'stats' })}>Статистика</button>
        </nav>
      </header>
      {view.name === 'home' && <Home bank={bank} db={db} setView={setView} tick={tick} />}
      {view.name === 'study' && <Study bank={bank} db={db} subject={view.subject} bump={bump} />}
      {view.name === 'quiz' && (
        <Quiz key={view.key} bank={bank} db={db} config={view} byId={byId} bump={bump} done={goHome} />
      )}
      {view.name === 'mistakes' && <Mistakes bank={bank} db={db} byId={byId} setView={setView} />}
      {view.name === 'flash' && <Flashcards bank={bank} />}
      {view.name === 'stats' && <Stats bank={bank} db={db} />}
    </div>
  );
}
