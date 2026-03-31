// src/admin/components/shared/Card.jsx
export default function Card({ children, className = "" }) {
  return (
    <div className={`bg-ggt-card border border-ggt-border rounded-lg p-4 ${className}`}>
      {children}
    </div>
  );
}

export function CardHeader({ label }) {
  return (
    <div className="text-[9px] font-sans font-extrabold tracking-[0.18em] text-ggt-accent uppercase mb-3.5">
      {label}
    </div>
  );
}
