interface Props {
  demoMode: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}

export function ModeToggle({ demoMode, onChange, disabled }: Props) {
  return (
    <label className={`mode-toggle ${disabled ? "is-disabled" : ""}`}>
      <span className="mode-toggle-label">Demo mode</span>
      <input
        type="checkbox"
        checked={demoMode}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="mode-toggle-track" aria-hidden="true">
        <span className="mode-toggle-thumb" />
      </span>
      <span
        className="mode-toggle-hint"
        title="Show prompts, input data, and reasoning at each stage"
      >
        ?
      </span>
    </label>
  );
}
