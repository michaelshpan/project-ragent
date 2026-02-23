interface Props {
  message: string;
}

export function LoadingStep({ message }: Props) {
  return (
    <div className="loading-step">
      <div className="spinner" />
      <span className="loading-message">{message}</span>
    </div>
  );
}
