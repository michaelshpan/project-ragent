import type { AnalysisState } from "../types/analysis";
import { LoadingStep } from "./LoadingStep";
import { DataSummary } from "./DataSummary";
import { AgentReport } from "./AgentReport";
import { DecisionCard } from "./DecisionCard";
import { DebugPanel } from "./DebugPanel";
import { FinalView } from "./FinalView";
import { ErrorDisplay } from "./ErrorDisplay";

interface Props {
  state: AnalysisState;
  onNewAnalysis: () => void;
}

export function StepDisplay({ state, onNewAnalysis }: Props) {
  const { stage, demoMode, debug } = state;

  if (stage === "error") {
    return <ErrorDisplay message={state.error ?? "Unknown error"} onRetry={onNewAnalysis} />;
  }

  if (stage === "complete") {
    return <FinalView state={state} onNewAnalysis={onNewAnalysis} />;
  }

  const researchHasReports = Object.keys(state.agentReports).length > 0;

  return (
    <div className="step-display">
      <h2 className="analyzing-ticker">Analyzing {state.ticker}</h2>
      {state.currentPrice != null && (
        <p className="current-price">Current Price: ${state.currentPrice.toFixed(2)}</p>
      )}
      {demoMode && <div className="demo-mode-badge">Demo mode</div>}

      {/* Data fetch phase */}
      {stage === "data_fetch" && !state.dataSummaries && (
        <LoadingStep message={state.message} />
      )}
      {state.dataSummaries && stage === "data_fetch" && (
        <DataSummary summaries={state.dataSummaries} />
      )}

      {/* Research phase — demo mode always renders all 3 slots so prompts show pre-call */}
      {stage === "research" && demoMode && (
        <AgentReport reports={state.agentReports} demoMode debug={debug} />
      )}
      {stage === "research" && !demoMode && !researchHasReports && (
        <LoadingStep message={state.message} />
      )}
      {stage === "research" && !demoMode && researchHasReports && (
        <AgentReport reports={state.agentReports} />
      )}

      {/* PM decision phase */}
      {stage === "pm_decision" && state.pmDecision && (
        <DecisionCard
          title="Portfolio Manager Decision"
          content={state.pmDecision}
          demoMode={demoMode}
          debug={debug.pm_decision}
        />
      )}
      {stage === "pm_decision" && !state.pmDecision && (
        <>
          {demoMode && <DebugPanel debug={debug.pm_decision} done={false} />}
          <LoadingStep message={state.message} />
        </>
      )}

      {/* DA challenge phase */}
      {stage === "da_challenge" && state.daChallenge && (
        <DecisionCard
          title="Devil's Advocate Challenge"
          content={state.daChallenge}
          demoMode={demoMode}
          debug={debug.da_challenge}
        />
      )}
      {stage === "da_challenge" && !state.daChallenge && (
        <>
          {demoMode && <DebugPanel debug={debug.da_challenge} done={false} />}
          <LoadingStep message={state.message} />
        </>
      )}

      {/* Final decision phase */}
      {stage === "final_decision" && state.finalDecision && (
        <DecisionCard
          title="Final Decision"
          content={state.finalDecision}
          demoMode={demoMode}
          debug={debug.final_decision}
        />
      )}
      {stage === "final_decision" && !state.finalDecision && (
        <>
          {demoMode && <DebugPanel debug={debug.final_decision} done={false} />}
          <LoadingStep message={state.message} />
        </>
      )}

      <button onClick={onNewAnalysis} className="cancel-btn">
        Cancel
      </button>
    </div>
  );
}
