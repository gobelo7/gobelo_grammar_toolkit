// src/admin/components/shared/Loader.jsx
export default function Loader({ text = "Loading…" }) {
  return (
    <div className="flex items-center gap-2 text-ggt-muted text-xs font-mono py-8 justify-center">
      <span className="inline-block w-3 h-3 rounded-full border-2 border-ggt-muted border-t-ggt-accent animate-spin" />
      {text}
    </div>
  );
}
