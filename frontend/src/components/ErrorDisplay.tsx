interface Props {
  message: string;
  onRetry: () => void;
}

export function ErrorDisplay({ message, onRetry }: Props) {
  return (
    <div className="error-display">
      <h2>Analysis Failed</h2>
      <p className="error-message">{message}</p>
      <button onClick={onRetry} className="retry-btn">
        Try Again
      </button>
    </div>
  );
}
