// src/admin/components/layout/TopBar.jsx
import { useGrammar } from "../../../state/GrammarContext";
import { useUI }      from "../../../state/UIContext";
import Button from "../shared/Button";

export default function TopBar() {
  const { fileName, langName, modified, handleDownload, handleFile } = useGrammar();
  const { language, setLanguage, role, setRole, showToast } = useUI();

  const onDownload = () => {
    const r = handleDownload();
    if (r?.ok === false) showToast(r.error ?? "Export failed", "err");
    else                 showToast("Downloaded!");
  };

  const onFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const r = await handleFile(file);
    if (r?.ok === false) showToast(r.error ?? "Parse error", "err");
    else                 showToast(`Loaded ${file.name}`);
    e.target.value = "";
  };

  return (
    <header className="flex items-center gap-3.5 px-5 h-[50px] bg-ggt-panel border-b border-ggt-border shrink-0 sticky top-0 z-10">
      {/* Brand */}
      <span className="font-sans font-extrabold text-[13px] text-ggt-accent tracking-[0.1em]">GGT ADMIN</span>
      <div className="w-px h-4.5 bg-ggt-border" />
      <span className="font-mono text-xs text-ggt-text">{fileName || "No file loaded"}</span>
      <span className="font-mono text-[11px] text-ggt-muted">[{langName}]</span>
      {modified && <span className="font-sans text-[10px] text-ggt-verify font-bold">● unsaved</span>}

      {/* Role switcher */}
      <div className="flex gap-1 ml-2">
        {["teacher","student"].map(r => (
          <button key={r} onClick={() => setRole(r)}
            className={`px-3 py-1 rounded text-xs font-sans font-bold cursor-pointer border transition-all ${
              role === r
                ? "bg-ggt-accent text-white border-ggt-accent"
                : "bg-transparent text-ggt-muted border-ggt-border hover:border-ggt-borderL"
            }`}
          >
            {r.charAt(0).toUpperCase() + r.slice(1)}
          </button>
        ))}
      </div>

      <div className="flex-1" />

      {/* File controls */}
      <label className="px-3.5 py-1.5 rounded bg-ggt-card border border-ggt-border text-ggt-muted cursor-pointer text-[11px] font-sans font-bold tracking-[0.04em] hover:text-ggt-text transition-colors">
        Load File
        <input type="file" accept=".yaml,.yml" onChange={onFileChange} className="hidden" />
      </label>
      <Button onClick={onDownload} variant="primary">↓ Download YAML</Button>
    </header>
  );
}
