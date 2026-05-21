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
    primary:   "bg-ggtk-accent text-white hover:opacity-90 shadow-[0_2px_12px_rgba(232,147,74,0.3)]",
    secondary: "bg-ggtk-card border border-ggtk-border text-ggtk-muted hover:text-ggtk-text",
    ghost:     "bg-transparent border border-dashed border-ggtk-borderL text-ggtk-muted hover:text-ggtk-text",
    danger:    "bg-transparent border border-ggtk-danger text-ggtk-danger hover:bg-ggtk-danger hover:text-white",
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
