// src/api/grammar.api.js
// Routes: GET /api/metadata/<lang>, GET /api/languages,
//         POST /api/validate, GET /api/verify-flags/<lang>, GET /api/compare
import { get, post } from "./client";

export const fetchLanguages    = ()     => get("/languages");
export const fetchMetadata     = (lang) => get(`/metadata/${lang}`);
export const validateGrammar   = (g)    => post("/validate", { grammar: g });
export const fetchVerifyFlags  = (lang) => get(`/verify-flags/${lang}`);
export const compareLanguages  = (l1, l2) => get(`/compare?l1=${l1}&l2=${l2}`);
