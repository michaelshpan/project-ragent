import { marked } from "marked";

marked.setOptions({ async: false, breaks: true });

export function renderMarkdown(md: string): string {
  return marked.parse(md) as string;
}
