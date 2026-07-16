import type { HTMLAttributes, ReactNode } from "react";

export interface CardProps extends HTMLAttributes<HTMLElement> {
  children: ReactNode;
  eyebrow?: string;
  title?: string;
}

export function Card({
  children,
  className = "",
  eyebrow,
  title,
  ...props
}: CardProps) {
  return (
    <section className={`ui-card ${className}`.trim()} {...props}>
      {eyebrow ? <span className="ui-card__eyebrow">{eyebrow}</span> : null}
      {title ? <h2 className="ui-card__title">{title}</h2> : null}
      {children}
    </section>
  );
}
