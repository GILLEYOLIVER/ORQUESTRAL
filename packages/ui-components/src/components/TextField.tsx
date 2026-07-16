import { forwardRef, useId } from "react";
import type { InputHTMLAttributes } from "react";

export interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: string;
  hint?: string;
  label: string;
}

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(
  function TextField(
    { className = "", error, hint, id, label, ...props },
    ref,
  ) {
    const generatedId = useId();
    const inputId = id ?? generatedId;
    const descriptionId = error || hint ? `${inputId}-description` : undefined;

    return (
      <div className={`ui-field ${className}`.trim()}>
        <label htmlFor={inputId}>{label}</label>
        <input
          aria-describedby={descriptionId}
          aria-invalid={Boolean(error)}
          id={inputId}
          ref={ref}
          {...props}
        />
        {error ? (
          <span className="ui-field__error" id={descriptionId} role="alert">
            {error}
          </span>
        ) : hint ? (
          <span className="ui-field__hint" id={descriptionId}>
            {hint}
          </span>
        ) : null}
      </div>
    );
  },
);
