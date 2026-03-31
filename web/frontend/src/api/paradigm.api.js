// src/api/paradigm.api.js
// Routes: POST /api/paradigm, GET /api/tam/<lang>, GET /api/extensions/<lang>
// Used as FALLBACK when grammar context has not yet loaded.
import { get, post } from "./client";

/** Generate a verb paradigm */
export const generateParadigm = (params)  => post("/paradigm",         params);

/** Fetch TAM markers for a language (fallback for VerbSystemEditor) */
export const fetchTam         = (lang)    => get(`/tam/${lang}`);

/** Fetch derivational extensions for a language (fallback for VerbSystemEditor) */
export const fetchExtensions  = (lang)    => get(`/extensions/${lang}`);
