// src/admin/components/layout/LoadScreen.jsx
// Shown when grammar === null. No persistence — user must re-upload on refresh.
import { useGrammar } from "../../../state/GrammarContext";
import { useUI }      from "../../../state/UIContext";

export default function LoadScreen() {
  const { handleFile }          = useGrammar();
  const { drag, setDrag, showToast } = useUI();

  const onDrop = async (e) => {
    e.preventDefault();
    setDrag(false);
    const file = e.dataTransfer.files[0];
    if (!file) return;
    if (!file.name.match(/\.ya?ml$/i)) {
      showToast("Only .yaml / .yml files accepted", "err");
      return;
    }
    const r = await handleFile(file);
    if (r?.ok === false) showToast(r.error ?? "Parse error", "err");
  };

  const onFileChange = async (e) => {
    const file = e.target.files[0];
    const r    = await handleFile(file);
    if (r?.ok === false) showToast(r.error ?? "Parse error", "err");
    e.target.value = "";
  };

  return (
    <div
      className="min-h-screen bg-ggt-bg flex items-center justify-center font-sans"
      onDragOver={e => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={onDrop}
    >
      <div className={`text-center px-14 py-12 border-2 rounded-2xl max-w-md transition-all duration-200 ${
        drag
          ? "border-ggt-accent bg-ggt-accentBg"
          : "border-ggt-border bg-transparent"
      }`}>
        <div className="text-5xl mb-5">⌘</div>
        <h1 className="text-ggt-text font-extrabold text-[22px] m-0 mb-1.5 tracking-tight">
          GGT Grammar Admin
        </h1>
        <p className="text-ggt-muted text-xs m-0 mb-2.5 tracking-[0.04em] uppercase">
          Gobelo Grammar Toolkit — v2
        </p>
        <p className="text-ggt-muted text-[13px] mb-8 leading-relaxed">
          Drop a <code className="text-ggt-accent font-mono">.yaml</code> grammar file
          or click to upload.
          <br />
          <span className="text-[11px]">Grammar lives in memory only — re-upload on refresh.</span>
        </p>

        <label className="inline-block px-8 py-3 rounded-lg bg-ggt-accent text-white font-extrabold text-[13px] cursor-pointer tracking-[0.06em] shadow-[0_4px_24px_rgba(232,147,74,0.3)] hover:opacity-90 transition-opacity">
          Upload YAML
          <input type="file" accept=".yaml,.yml" onChange={onFileChange} className="hidden" />
        </label>
      </div>
    </div>
  );
}
