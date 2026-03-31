#!/usr/bin/env node
// scripts/verify.mjs — GGT Frontend v2 pre-flight checker
// Run: node scripts/verify.mjs
import fs   from "fs";
import path from "path";

const ROOT = path.resolve(process.cwd(), "src");
const P = "\x1b[32m✓\x1b[0m";
const F = "\x1b[31m✗\x1b[0m";
let errors = 0;
const ok   = (m) => console.log(`  ${P} ${m}`);
const fail = (m) => { console.log(`  ${F} ${m}`); errors++; };

function read(rel) {
  const abs = path.join(ROOT, rel);
  return fs.existsSync(abs) ? fs.readFileSync(abs, "utf8") : null;
}
function exists(rel) { return fs.existsSync(path.join(ROOT, rel)); }
function allSrc() {
  const out = [];
  const walk = (d) => {
    if (!fs.existsSync(d)) return;
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const f = path.join(d, e.name);
      if (e.isDirectory()) walk(f);
      else if (/\.(jsx?|mjs)$/.test(e.name)) out.push(f);
    }
  };
  walk(ROOT);
  return out;
}

// ─────────────────────────────────────────────────────────────────────────────
console.log("\n── CHECK 1: Required files (Section 4 tree) ─────────────────────");
const REQUIRED = [
  "main.jsx","App.jsx",
  "styles/global.css","styles/debugger.css","styles/editor.css",
  "api/client.js","api/grammar.api.js","api/parser.api.js",
  "api/concord.api.js","api/paradigm.api.js","api/mockParser.js",
  "state/GrammarContext.jsx","state/UIContext.jsx","state/ParserContext.jsx",
  "hooks/useParser.js","hooks/useStepDebugger.js",
  "hooks/useLiveYaml.js","hooks/useSuggestions.js",
  "admin/GrammarAdmin.jsx",
  "admin/components/layout/TopBar.jsx",
  "admin/components/layout/Sidebar.jsx",
  "admin/components/layout/Workspace.jsx",
  "admin/components/editors/MetadataEditor.jsx",
  "admin/components/editors/NounClassEditor.jsx",
  "admin/components/editors/ConcordEditor.jsx",
  "admin/components/editors/VerbSystemEditor.jsx",
  "admin/components/editors/VerifyManager.jsx",
  "admin/components/debug/SlotDebugger.jsx",
  "admin/components/debug/SlotFlow.jsx",
  "admin/components/debug/SlotCard.jsx",
  "admin/components/debug/MorphBreakdown.jsx",
  "admin/components/debug/TracePanel.jsx",
  "admin/components/debug/StepDebugger.jsx",
  "admin/components/debug/StepControls.jsx",
  "admin/components/debug/StepTimeline.jsx",
  "admin/components/debug/ActiveSlotView.jsx",
  "admin/components/parser/ParserPanel.jsx",
  "admin/components/shared/Button.jsx",
  "admin/components/shared/Card.jsx",
  "admin/components/shared/Loader.jsx",
  "admin/views/DebugView.jsx",
  "admin/views/EditorView.jsx",
  "admin/views/VerifyView.jsx",
  "quiz/QuizPanel.jsx","quiz/QuestionCard.jsx",
  "quiz/ResultPanel.jsx","quiz/quizEngine.js",
  "learning/LearningPanel.jsx","learning/ConceptCard.jsx",
  "learning/ExampleViewer.jsx",
];
for (const f of REQUIRED) {
  if (exists(f)) ok(f);
  else           fail(`MISSING: ${f}`);
}

// ─────────────────────────────────────────────────────────────────────────────
console.log("\n── CHECK 2: Absolute prohibitions (Section 1 + Section 8) ──────");
const files = allSrc();
const all   = files.map(f => fs.readFileSync(f, "utf8")).join("\n");
const noComments = (s) => s.replace(/\/\/[^\n]*/g, "").replace(/\/\*[\s\S]*?\*\//g, "");

// localStorage / sessionStorage — Section 1 explicit prohibition
const lsHits = files.filter(f => /localStorage|sessionStorage/.test(noComments(fs.readFileSync(f,"utf8"))));
if (lsHits.length === 0) ok("No localStorage / sessionStorage");
else lsHits.forEach(f => fail(`localStorage/sessionStorage in ${path.relative(ROOT,f)}`));

// Hardcoded inventory arrays — Section 8 canonical antipatterns
const INV = ["NC_KEYS","CONCORD_TYPES","TAM_KEYS","EXT_KEYS","FV_KEYS","EXTENSION_KEYS"];
for (const name of INV) {
  const hits = files.filter(f => {
    const clean = noComments(fs.readFileSync(f,"utf8"));
    return new RegExp(`(const|let|var)\\s+${name}\\s*=`).test(clean);
  });
  if (hits.length === 0) ok(`No hardcoded ${name}`);
  else hits.forEach(h => fail(`Hardcoded ${name} in ${path.relative(ROOT,h)} — use Object.keys() at runtime`));
}

// inline onclick= handlers
const onclickHits = files.filter(f => /onclick\s*=/.test(fs.readFileSync(f,"utf8")));
if (onclickHits.length === 0) ok("No inline onclick= handlers");
else onclickHits.forEach(f => fail(`inline onclick in ${path.relative(ROOT,f)}`));

// lodash (not lodash-es)
const lodashHits = files.filter(f => {
  const clean = noComments(fs.readFileSync(f,"utf8"));
  return /from ['"]lodash['"]/.test(clean);
});
if (lodashHits.length === 0) ok("No bare 'lodash' imports (lodash-es only)");
else lodashHits.forEach(f => fail(`bare lodash import in ${path.relative(ROOT,f)} — use lodash-es`));

// js-yaml — not in spec dependencies (should be absent from non-context files)
// (GrammarContext and useLiveYaml legitimately use it)
const allowedYaml = ["state/GrammarContext.jsx", "hooks/useLiveYaml.js"];
const yamlHits = files.filter(f => {
  // Normalise to forward slashes so this works on both Windows and Unix
  const rel = path.relative(ROOT, f).replace(/\\/g, "/");
  if (allowedYaml.some(a => rel.endsWith(a))) return false;
  return /from ['"]js-yaml['"]/.test(noComments(fs.readFileSync(f, "utf8")));
});
if (yamlHits.length === 0) ok("js-yaml usage confined to GrammarContext + useLiveYaml");
else yamlHits.forEach(f => fail(`js-yaml imported outside allowed files in ${path.relative(ROOT, f)}`));

// ─────────────────────────────────────────────────────────────────────────────
console.log("\n── CHECK 3: UIContext contract (Section 5.1) ────────────────────");
const uiCtx = read("state/UIContext.jsx") ?? "";
["language","setLanguage","role","setRole","activeView","setView"].forEach(field => {
  if (uiCtx.includes(field)) ok(`UIContext exposes: ${field}`);
  else                        fail(`UIContext missing: ${field}`);
});

// ─────────────────────────────────────────────────────────────────────────────
console.log("\n── CHECK 4: GrammarContext — no localStorage (Section 1) ────────");
const gramCtx = read("state/GrammarContext.jsx") ?? "";
if (/localStorage|sessionStorage/.test(noComments(gramCtx))) {
  fail("GrammarContext uses localStorage — prohibited by Section 1");
} else {
  ok("GrammarContext has no localStorage");
}
if (gramCtx.includes("updateGrammar")) ok("GrammarContext exports updateGrammar");
else                                   fail("GrammarContext missing updateGrammar");

// ─────────────────────────────────────────────────────────────────────────────
console.log("\n── CHECK 5: Editors use Object.keys() not hardcoded arrays ──────");
const EDITORS = [
  ["NounClassEditor",  "admin/components/editors/NounClassEditor.jsx",  "noun_class_system"],
  ["ConcordEditor",    "admin/components/editors/ConcordEditor.jsx",     "concord_system"],
  ["VerbSystemEditor", "admin/components/editors/VerbSystemEditor.jsx",  "verb_system"],
];
for (const [name, rel, path_] of EDITORS) {
  const raw     = read(rel) ?? "";
  const clean   = noComments(raw);   // strip comments before checking
  const hasObjKeys    = clean.includes("Object.keys(") || clean.includes("Object.entries(");
  const hasHardcoded  = INV.some(k => new RegExp(`(const|let|var)\\s+${k}\\s*=`).test(clean));
  if (hasObjKeys && !hasHardcoded) ok(`${name}: uses Object.keys() / Object.entries()`);
  else if (hasHardcoded)           fail(`${name}: hardcoded inventory constant found`);
  else                             fail(`${name}: no Object.keys() call found`);
}

// ─────────────────────────────────────────────────────────────────────────────
console.log("\n── CHECK 6: MorphBreakdown v2 contract (Section 5.4/6.9) ────────");
const mb = read("admin/components/debug/MorphBreakdown.jsx") ?? "";
["best","segmented","underlying","rule_trace","gloss_line","morphemes"].forEach(field => {
  if (mb.includes(field)) ok(`MorphBreakdown references: ${field}`);
  else                    fail(`MorphBreakdown missing v2 field: ${field}`);
});
// underlying must only show when it differs from surface
if (mb.includes("hasPhon") || mb.includes("replace(/-/g")) ok("MorphBreakdown: conditional underlying display");
else                                                         fail("MorphBreakdown: underlying shown unconditionally (spec requires conditional)");
// rule_trace must be teacher-mode only
if (mb.includes("role") || mb.includes("teacher")) ok("MorphBreakdown: rule_trace is role-gated");
else                                                fail("MorphBreakdown: rule_trace not gated by teacher role");

// ─────────────────────────────────────────────────────────────────────────────
console.log("\n── CHECK 7: Tailwind usage — no pervasive inline styles ─────────");
const STYLE_INTENSIVE = [
  "admin/components/editors/NounClassEditor.jsx",
  "admin/components/editors/ConcordEditor.jsx",
  "admin/components/editors/VerbSystemEditor.jsx",
  "admin/components/layout/Sidebar.jsx",
  "admin/components/layout/TopBar.jsx",
];
for (const rel of STYLE_INTENSIVE) {
  const content = read(rel) ?? "";
  const classNames = (content.match(/className=/g) ?? []).length;
  const inlineStyles = (content.match(/style=\{\{/g) ?? []).length;
  // Allow minimal inline styles for dynamic values (e.g. border color from parser)
  if (classNames > 0 && inlineStyles <= 3) ok(`${rel.split("/").pop()}: Tailwind (${classNames} className, ${inlineStyles} inline)`);
  else if (inlineStyles > 10)              fail(`${rel.split("/").pop()}: excessive inline styles (${inlineStyles}) — use Tailwind`);
  else                                     ok(`${rel.split("/").pop()}: ${classNames} className, ${inlineStyles} inline`);
}

// ─────────────────────────────────────────────────────────────────────────────
console.log("\n── CHECK 8: Provider order (Section 7) ─────────────────────────");
const ga = read("admin/GrammarAdmin.jsx") ?? "";
const uiPos   = ga.indexOf("UIProvider");
const gramPos = ga.indexOf("GrammarProvider");
if (uiPos > -1 && gramPos > -1 && uiPos < gramPos) ok("UIProvider wraps GrammarProvider (correct order)");
else                                                  fail("Provider order wrong — UIProvider must be outer (Section 7)");

// ─────────────────────────────────────────────────────────────────────────────
console.log("\n── CHECK 9: Rules of Hooks ──────────────────────────────────────");
let hooksOk = true;
const hookPat = /\buse[A-Z]\w+\s*\(/;
const fnPat   = /^export\s+(?:default\s+)?function\s+(\w+)/;
for (const filePath of files) {
  const content = fs.readFileSync(filePath,"utf8");
  const lines   = content.split("\n");
  let inFn = false, fnStart = 0, depth = 0, condRet = -1;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (fnPat.test(line.trim())) { inFn = true; depth = 0; fnStart = 0; condRet = -1; }
    if (!inFn) continue;
    for (const ch of line) {
      if (ch==="{") { depth++; if (!fnStart) fnStart = depth; }
      if (ch==="}") depth--;
    }
    if (fnStart > 0 && depth < fnStart) { inFn = false; condRet = -1; continue; }
    if (/^\s*\/\//.test(line)) continue;
    if (condRet < 0 && depth === fnStart && /^\s*if\s*\(/.test(line) && /\breturn\b/.test(line)) {
      condRet = i;
    }
    if (condRet >= 0 && i > condRet && hookPat.test(line) && !/^\s*\/\//.test(line)) {
      const rel = path.relative(ROOT, filePath);
      fail(`Rules of Hooks: hook after guard return at line ${i+1} in ${rel}`);
      hooksOk = false;
      break;
    }
  }
}
if (hooksOk) ok("No Rules of Hooks violations");

// ─────────────────────────────────────────────────────────────────────────────
console.log("\n── CHECK 10: package.json (Section 11) ──────────────────────────");
const pkgPath = path.resolve(process.cwd(),"package.json");
if (fs.existsSync(pkgPath)) {
  const pkg  = JSON.parse(fs.readFileSync(pkgPath,"utf8"));
  const deps = { ...pkg.dependencies, ...pkg.devDependencies };
  // [["lodash-es","dep"],["react","dep"],["react-dom","dep"],
  [["lodash-es","dep"],["react","dep"],["react-dom","dep"],["js-yaml","dep"],
   ["@vitejs/plugin-react","dev"],["vite","dev"]].forEach(([d]) => {
    if (deps[d]) ok(`${d} present`);
    else         fail(`${d} missing`);
  });
  // if (!pkg.dependencies?.["js-yaml"]) ok("js-yaml not in package.json (correct — loaded internally)");
  if (pkg.dependencies?.["lodash"] || pkg.devDependencies?.["lodash"]) fail("bare 'lodash' found — use lodash-es");
  else ok("No bare 'lodash' dependency");
}

// ─────────────────────────────────────────────────────────────────────────────
console.log("\n── SUMMARY ──────────────────────────────────────────────────────");
console.log(`  Files checked: ${files.length}`);
if (errors === 0) {
  console.log(`  \x1b[32m✓ All checks passed — safe to run: npm run dev\x1b[0m`);
} else {
  console.log(`  \x1b[31m${errors} error(s) — fix before running dev server\x1b[0m`);
  process.exit(1);
}
console.log();
