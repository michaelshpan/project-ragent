import { useAnalysis } from "./hooks/useAnalysis";
import { TickerInput } from "./components/TickerInput";
import { StepDisplay } from "./components/StepDisplay";
import { Footer } from "./components/Footer";

export function App() {
  const { state, start, reset } = useAnalysis();

  return (
    <>
      <div className="app">
        {state.stage === "idle" ? (
          <TickerInput onSubmit={start} disabled={false} />
        ) : (
          <StepDisplay state={state} onNewAnalysis={reset} />
        )}
      </div>
      <Footer />
    </>
  );
}
