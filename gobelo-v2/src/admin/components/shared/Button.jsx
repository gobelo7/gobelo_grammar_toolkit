// src/admin/components/shared/Button.jsx
// Variants: "primary" | "secondary" | "ghost" | "danger"
export default function Button({
  children,
  onClick,
  variant = "primary",
  disabled = false,
  type = "button",
  className = "",
}) {
  const base = "inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded text-xs font-bold font-sans tracking-wide transition-all duration-100 disabled:opacity-40 disabled:cursor-default";

  const variants = {
    primary:   "bg-ggt-accent text-white hover:opacity-90 shadow-[0_2px_12px_rgba(232,147,74,0.3)]",
    secondary: "bg-ggt-card border border-ggt-border text-ggt-muted hover:text-ggt-text",
    ghost:     "bg-transparent border border-dashed border-ggt-borderL text-ggt-muted hover:text-ggt-text",
    danger:    "bg-transparent border border-ggt-danger text-ggt-danger hover:bg-ggt-danger hover:text-white",
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${base} ${variants[variant] ?? variants.secondary} ${className}`}
    >
      {children}
    </button>
  );
}
