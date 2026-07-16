import type { HTMLAttributes, ReactNode } from "react";
import { AlertCircle, CheckCircle2, Info } from "lucide-react";

type AlertVariant = "info" | "success" | "error";

export interface AlertProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  title?: string;
  variant?: AlertVariant;
}

const icons = {
  info: Info,
  success: CheckCircle2,
  error: AlertCircle,
};

export function Alert({
  children,
  className = "",
  title,
  variant = "info",
  ...props
}: AlertProps) {
  const Icon = icons[variant];
  return (
    <div
      className={`ui-alert ui-alert--${variant} ${className}`.trim()}
      role="status"
      {...props}
    >
      <Icon aria-hidden="true" size={19} />
      <div>
        {title ? <strong>{title}</strong> : null}
        <div>{children}</div>
      </div>
    </div>
  );
}
