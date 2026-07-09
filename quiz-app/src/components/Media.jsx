const BASE = import.meta.env.BASE_URL;

// Renders audio players / images attached to a question.
export default function Media({ media }) {
  if (!media || media.length === 0) return null;
  return (
    <div className="media">
      {media.map((m, i) =>
        m.type === 'audio' ? (
          <audio key={i} controls preload="none" src={`${BASE}media/${m.file}`} />
        ) : (
          <img key={i} src={`${BASE}media/${m.file}`} alt="иллюстрация к вопросу" loading="lazy" />
        )
      )}
    </div>
  );
}
