// src/admin/components/editors/MetadataEditor.jsx
import { useGrammar } from "../../../state/GrammarContext";
import Card, { CardHeader } from "../shared/Card";

// Reusable labelled input — Tailwind throughout
function Field({ label, path, grammar, updateGrammar, mono = false }) {
  // Resolve value from dot-path at runtime
  const value = path.split(".").reduce((o, k) => o?.[k], grammar) ?? "";
  return (
    <div className="mb-3.5">
      <label className="block text-[10px] font-sans tracking-[0.09em] uppercase text-ggt-muted mb-1.5">
        {label}
      </label>
      <input
        value={value}
        onChange={e => updateGrammar(path, e.target.value)}
        className={`w-full bg-ggt-input border border-ggt-border rounded text-ggt-text px-2.5 py-1.5 text-xs outline-none focus:border-ggt-accent ${mono ? "font-mono" : "font-sans"}`}
      />
    </div>
  );
}

export default function MetadataEditor() {
  const { grammar, updateGrammar } = useGrammar();

  if (!grammar) {
    return <div className="text-ggt-muted text-xs p-10 text-center">Grammar not loaded</div>;
  }

  const lang = grammar.metadata?.language;
  const b    = "metadata.language";

  return (
    <div>
      {/* Section header */}
      <div className="mb-6 pb-3.5 border-b border-ggt-border flex items-start justify-between">
        <div>
          <h2 className="m-0 text-ggt-text font-sans font-extrabold text-lg">Language Metadata</h2>
          <p className="mt-1 text-ggt-muted text-[11px] font-sans">Core language identification and bibliographic data</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-5">
        {/* Identification card */}
        <Card>
          <CardHeader label="Identification" />
          <Field label="Language Name"    path={`${b}.name`}                   grammar={grammar} updateGrammar={updateGrammar} mono />
          <Field label="ISO 639-3"        path={`${b}.iso_code`}               grammar={grammar} updateGrammar={updateGrammar} mono />
          <Field label="Guthrie Code"     path={`${b}.guthrie`}                grammar={grammar} updateGrammar={updateGrammar} mono />
          <Field label="Primary Region"   path={`${b}.primary_region`}         grammar={grammar} updateGrammar={updateGrammar} />
          <Field label="Approx. Speakers" path={`${b}.approximate_speakers`}   grammar={grammar} updateGrammar={updateGrammar} mono />
          <Field label="Family"           path={`${b}.family`}                 grammar={grammar} updateGrammar={updateGrammar} />
        </Card>

        <div className="flex flex-col gap-4">
          {/* Dialects */}
          <Card>
            <CardHeader label="Dialects" />
            <div className="flex flex-wrap gap-1.5 mb-2">
              {(lang?.dialects ?? []).map((d, i) => (
                <span key={i} className="inline-flex items-center gap-1 bg-ggt-accentBg text-ggt-accent font-mono text-xs px-2 py-0.5 rounded border border-ggt-accent/20">
                  {d}
                  <button
                    onClick={() => updateGrammar(`${b}.dialects`, (lang.dialects ?? []).filter((_, j) => j !== i))}
                    className="text-ggt-accent hover:opacity-70 leading-none bg-transparent border-none cursor-pointer"
                  >×</button>
                </span>
              ))}
            </div>
            <input
              placeholder="+ dialect (Enter to add)"
              onKeyDown={e => {
                if (e.key === "Enter" && e.target.value.trim()) {
                  updateGrammar(`${b}.dialects`, [...(lang?.dialects ?? []), e.target.value.trim()]);
                  e.target.value = "";
                }
              }}
              className="w-full bg-ggt-input border border-dashed border-ggt-borderL rounded text-ggt-muted font-mono text-xs px-2.5 py-1.5 outline-none"
            />
          </Card>

          {/* Reference */}
          <Card>
            <CardHeader label="Reference" />
            <Field label="Reference Grammar" path="metadata.reference_grammar" grammar={grammar} updateGrammar={updateGrammar} />
            <Field label="Version"           path="metadata.version"           grammar={grammar} updateGrammar={updateGrammar} mono />
          </Card>
        </div>

        {/* Description — full width */}
        <Card className="col-span-2">
          <CardHeader label="Description" />
          <textarea
            value={lang?.description ?? ""}
            onChange={e => updateGrammar(`${b}.description`, e.target.value)}
            rows={4}
            className="w-full bg-ggt-input border border-ggt-border rounded text-ggt-text font-sans text-xs px-2.5 py-1.5 outline-none focus:border-ggt-accent resize-y"
          />
        </Card>
      </div>
    </div>
  );
}
