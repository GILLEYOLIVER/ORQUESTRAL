export interface SpinnerProps {
  label?: string;
  size?: "small" | "medium";
}

export function Spinner({
  label = "Carregando",
  size = "medium",
}: SpinnerProps) {
  return (
    <span className="ui-spinner-wrap" role="status">
      <span aria-hidden="true" className={`ui-spinner ui-spinner--${size}`} />
      <span className="ui-visually-hidden">{label}</span>
    </span>
  );
}
