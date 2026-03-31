// src/api/concord.api.js
// Routes: GET /api/concords/<lang>, GET /api/noun-classes/<lang>
// Used as FALLBACK when grammar context has not yet loaded.
// Editors derive their data from the loaded grammar object first;
// these routes are only called when grammar === null.
import { get } from "./client";

/** Fetch all concord types for a language (fallback for ConcordEditor) */
export const fetchConcords    = (lang) => get(`/concords/${lang}`);

/** Fetch noun class inventory for a language (fallback for NounClassEditor) */
export const fetchNounClasses = (lang) => get(`/noun-classes/${lang}`);
