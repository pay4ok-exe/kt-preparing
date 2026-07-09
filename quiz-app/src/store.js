// Local "database" backed by localStorage.
const KEY = 'kt-progress-v1';

function load() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || {};
  } catch {
    return {};
  }
}

let state = load();
state.stats ||= {};        // qid -> {seen, ok, bad, last}
state.bookmarks ||= [];    // [qid]
state.exams ||= [];        // [{date, subject, total, correct, seconds}]

function save() {
  localStorage.setItem(KEY, JSON.stringify(state));
}

export const db = {
  stat(qid) {
    return state.stats[qid] || { seen: 0, ok: 0, bad: 0 };
  },
  record(qid, correct) {
    const s = state.stats[qid] || { seen: 0, ok: 0, bad: 0 };
    s.seen += 1;
    if (correct) s.ok += 1; else s.bad += 1;
    s.last = Date.now();
    state.stats[qid] = s;
    save();
  },
  isBookmarked(qid) {
    return state.bookmarks.includes(qid);
  },
  toggleBookmark(qid) {
    const i = state.bookmarks.indexOf(qid);
    if (i >= 0) state.bookmarks.splice(i, 1);
    else state.bookmarks.push(qid);
    save();
    return i < 0;
  },
  bookmarks() {
    return [...state.bookmarks];
  },
  addExam(result) {
    state.exams.push(result);
    save();
  },
  exams() {
    return [...state.exams];
  },
  allStats() {
    return state.stats;
  },
  mistakes() {
    return Object.entries(state.stats)
      .filter(([, s]) => s.bad > s.ok)
      .map(([qid]) => qid);
  },
  seenCount(qids) {
    let seen = 0, mastered = 0;
    for (const id of qids) {
      const s = state.stats[id];
      if (s && s.seen > 0) {
        seen += 1;
        if (s.ok > s.bad) mastered += 1;
      }
    }
    return { seen, mastered };
  },
  reset() {
    state = { stats: {}, bookmarks: [], exams: [] };
    save();
  },
};

export function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
