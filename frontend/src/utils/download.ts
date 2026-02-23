import type { AllReports, SourceEntry } from "../types/analysis";

export function downloadMarkdown(content: string, filename: string): void {
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function buildFullReport(
  ticker: string,
  allReports: AllReports,
  sourceLog: SourceEntry[],
): string {
  const date = new Date().toISOString().slice(0, 10);
  const sourceRows = sourceLog
    .map((e) => `| ${e.source} | ${e.type} | ${e.url} |`)
    .join("\n");

  return `# Investment Committee Report: ${ticker}
**Date:** ${date}

---

## Stage 1: Research Reports

### Quantitative Valuation Research
${allReports.quant}

### Sentiment Research
${allReports.sentiment}

### Technical Signals Research
${allReports.technical}

---

## Stage 2: Portfolio Manager Initial Decision
${allReports.pm_decision}

---

## Stage 3: Devil's Advocate Challenge
${allReports.da_challenge}

---

## Stage 4: Final Investment Decision
${allReports.final_decision}

---

## Source Log
| Source | Type | URL/Endpoint |
|--------|------|-------------|
${sourceRows}
`;
}
