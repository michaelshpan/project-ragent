import type { AnalysisState } from "../types/analysis";
import { LoadingStep } from "./LoadingStep";
import { DataSummary } from "./DataSummary";
import { AgentReport } from "./AgentReport";
import { DecisionCard } from "./DecisionCard";
import { FinalView } from "./FinalView";
import { ErrorDisplay } from "./ErrorDisplay";

interface Props {
  state: AnalysisState;
  onNewAnalysis: () => void;
}

export function StepDisplay({ state, onNewAnalysis }: Props) {
  const { stage } = state;

  if (stage === "error") {
    return <ErrorDisplay message={state.error ?? "Unknown error"} onRetry={onNewAnalysis} />;
  }

  if (stage === "complete") {
    return <FinalView state={state} onNewAnalysis={onNewAnalysis} />;
  }

  return (
    <div className="step-display">
      <h2 className="analyzing-ticker">Analyzing {state.ticker}</h2>

      {/* Data fetch phase */}
      {stage === "data_fetch" && !state.dataSummaries && (
        <LoadingStep message={state.message} />
      )}
      {state.dataSummaries && stage === "data_fetch" && (
        <DataSummary summaries={state.dataSummaries} />
      )}

      {/* Research phase */}
      {stage === "research" && Object.keys(state.agentReports).length === 0 && (
        <LoadingStep message={state.message} />
      )}
      {Object.keys(state.agentReports).length > 0 && stage === "research" && (
        <AgentReport reports={state.agentReports} />
      )}

      {/* PM decision phase */}
      {stage === "pm_decision" && !state.pmDecision && (
        <LoadingStep message={state.message} />
      )}
      {state.pmDecision && stage === "pm_decision" && (
        <DecisionCard title="Portfolio Manager Decision" content={state.pmDecision} />
      )}

      {/* DA challenge phase */}
      {stage === "da_challenge" && !state.daChallenge && (
        <LoadingStep message={state.message} />
      )}
      {state.daChallenge && stage === "da_challenge" && (
        <DecisionCard title="Devil's Advocate Challenge" content={state.daChallenge} />
      )}

      {/* Final decision phase */}
      {stage === "final_decision" && !state.finalDecision && (
        <LoadingStep message={state.message} />
      )}
      {state.finalDecision && stage === "final_decision" && (
        <DecisionCard title="Final Decision" content={state.finalDecision} />
      )}

      <button onClick={onNewAnalysis} className="cancel-btn">
        Cancel
      </button>
    </div>
  );
}
