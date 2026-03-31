// src/quiz/quizEngine.js
// ─────────────────────────────────────────────────────────────────────────────
// Quiz question generator — derives questions entirely from the loaded grammar.
// No hardcoded keys: noun classes, concord types, TAM markers are all read
// from the grammar object at runtime.
// ─────────────────────────────────────────────────────────────────────────────

/** Generate quiz questions from a grammar object. Returns up to `count` questions. */
export function generateQuestions(grammar, count = 5) {
  if (!grammar) return [];
  const questions = [];

  // ── Noun class prefix questions (derived from runtime keys) ───────────────
  const classes = grammar.noun_class_system?.noun_classes ?? {};
  const ncKeys  = Object.keys(classes);
  for (const key of ncKeys) {
    const nc = classes[key];
    if (!nc?.prefix?.canonical_form) continue;
    questions.push({
      id:       `nc_prefix_${key}`,
      type:     "multiple_choice",
      prompt:   `What is the canonical prefix for noun class ${key}?`,
      answer:   nc.prefix.canonical_form,
      domain:   nc.semantics?.primary_domain ?? "—",
      distractors: ncKeys
        .filter(k => k !== key && classes[k]?.prefix?.canonical_form)
        .slice(0, 3)
        .map(k => classes[k].prefix.canonical_form),
    });
  }

  // ── TAM marker questions ──────────────────────────────────────────────────
  const tam    = grammar.verb_system?.verbal_system_components?.tam ?? {};
  const tamKeys = Object.keys(tam);
  for (const key of tamKeys) {
    const entry = tam[key];
    const forms = Array.isArray(entry.forms) ? entry.forms.join(", ") : String(entry.forms ?? "");
    if (!forms) continue;
    questions.push({
      id:       `tam_${key}`,
      type:     "multiple_choice",
      prompt:   `Which TAM marker encodes "${entry.function ?? key}"?`,
      answer:   forms,
      distractors: tamKeys
        .filter(k => k !== key)
        .slice(0, 3)
        .map(k => {
          const f = tam[k]?.forms;
          return Array.isArray(f) ? f.join(", ") : String(f ?? "");
        })
        .filter(Boolean),
    });
  }

  // Shuffle and limit
  for (let i = questions.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [questions[i], questions[j]] = [questions[j], questions[i]];
  }
  return questions.slice(0, count);
}
