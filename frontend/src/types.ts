export type PageId =
  | "home"
  | "what-is-rag"
  | "why-rag"
  | "prepare-documents"
  | "find-information"
  | "improve-results"
  | "generate-answer"
  | "prevent-errors"
  | "measure-quality"
  | "production"
  | "interview"
  | "glossary";

export type LessonVisual = "pipeline" | "compare" | "chunks" | "search" | "rerank" | "answer" | "shield" | "quality" | "production";

export interface SourceReference {
  label: string;
  url: string;
}

export interface Lesson {
  id: PageId;
  group: "Getting started" | "How it works" | "Quality and production";
  number: number;
  title: string;
  shortTitle: string;
  objective: string;
  duration: string;
  visual: LessonVisual;
  visualCaption: string;
  plain: string;
  analogy: string;
  steps: Array<{ title: string; text: string }>;
  technical: string;
  interview: string;
  followUp: string;
  tradeoff: string;
  sources: SourceReference[];
}

export interface InterviewQuestion {
  category: string;
  question: string;
  quick: string;
  detailed: string;
  followUp: string;
  tradeoff: string;
  sources: SourceReference[];
}
