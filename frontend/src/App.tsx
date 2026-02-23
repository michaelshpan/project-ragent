import { useAnalysis } from "./hooks/useAnalysis";
import { TickerInput } from "./components/TickerInput";
import { StepDisplay } from "./components/StepDisplay";

export function App() {
  const { state, start, reset } = useAnalysis();

  if (state.stage === "idle") {
    return (
      <div className="app">
        <TickerInput onSubmit={start} disabled={false} />
      </div>
    );
  }

  return (
    <div className="app">
      <StepDisplay state={state} onNewAnalysis={reset} />
    </div>
  );
}
