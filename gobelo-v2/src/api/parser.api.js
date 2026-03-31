// src/api/parser.api.js
// Routes: POST /api/parse, POST /api/analyze, POST /api/annotate
//
// /api/parse response shape (Section 5.3):
//   { word, slots: [{slot, label, value, gloss}], steps: [...], trace: [...] }
//
// /api/analyze response shape (Section 5.4):
//   { token, language, best: { segmented, gloss_line, underlying, rule_trace,
//     morphemes: [{form, slot_id, slot_name, content_type, gloss, nc_id}],
//     warnings }, ud_features, all_hypotheses }
import { post } from "./client";

/** Full slot parser — drives SlotDebugger, SlotFlow, StepTimeline */
export const parseWord   = (word, grammar)   => post("/parse",    { word, grammar });

/** Morphological analysis — drives MorphBreakdown */
export const analyzeWord = (word, language)  => post("/analyze",  { word, language });

/** Corpus annotation */
export const annotateText = (text, language) => post("/annotate", { text, language });
