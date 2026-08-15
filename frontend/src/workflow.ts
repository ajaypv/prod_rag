import type { LucideIcon } from "lucide-react";
import {
  Binary,
  BookOpenCheck,
  Braces,
  CheckCheck,
  ClipboardCheck,
  Database,
  FileCheck2,
  FileSearch,
  Gauge,
  GitMerge,
  Layers3,
  ListChecks,
  MessageSquareText,
  Network,
  PackageCheck,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Split,
  UploadCloud,
} from "lucide-react";
import type { WorkflowId } from "./types";

export interface WorkflowStage {
  id: string;
  title: string;
  description: string;
  artifact: string;
  icon: LucideIcon;
}

export const workflowStages: Record<WorkflowId, WorkflowStage[]> = {
  ingestion: [
    { id: "upload", title: "Upload", description: "Validate the file, size, tenant, and security scan.", artifact: "approved file", icon: UploadCloud },
    { id: "queued", title: "Queue", description: "Persist the job and hand work to the ingestion worker.", artifact: "job ID", icon: ListChecks },
    { id: "checksum", title: "Fingerprint", description: "Calculate a stable checksum for revision-safe indexing.", artifact: "checksum", icon: FileCheck2 },
    { id: "parse", title: "Parse", description: "Docling extracts readable structure from the source.", artifact: "structured Markdown", icon: FileSearch },
    { id: "section", title: "Parent sections", description: "Keep headings and surrounding explanation together.", artifact: "parent context", icon: Layers3 },
    { id: "chunk_embed", title: "Chunk + embed", description: "Create semantic child chunks and dense vectors.", artifact: "searchable children", icon: Binary },
    { id: "index", title: "Hybrid index", description: "Write vectors, BM25 text, metadata, and the ready revision.", artifact: "local Qdrant", icon: Database },
    { id: "complete", title: "Ready", description: "The document is available to tenant-filtered retrieval.", artifact: "indexed corpus", icon: PackageCheck },
  ],
  query: [
    { id: "triage", title: "Triage", description: "Classify intent, confidence, sensitive data, and routing.", artifact: "safe request", icon: ShieldCheck },
    { id: "hybrid_retrieval", title: "Hybrid retrieval", description: "Dense vectors and BM25 search are fused with RRF.", artifact: "broad candidates", icon: GitMerge },
    { id: "rerank", title: "Rerank", description: "The relevance model sharpens the fused candidate order.", artifact: "ranked evidence", icon: ScanSearch },
    { id: "context", title: "Parent context", description: "Winning child hits expand into unique parent sections.", artifact: "evidence pack", icon: BookOpenCheck },
    { id: "evidence_gate", title: "Evidence gate", description: "Confidence and context budget decide whether to answer.", artifact: "answer decision", icon: Gauge },
    { id: "generate", title: "Generate", description: "The model answers only from numbered source blocks.", artifact: "draft answer", icon: Sparkles },
    { id: "citations", title: "Validate", description: "Every cited source ID is checked before returning output.", artifact: "grounded response", icon: CheckCheck },
  ],
  evaluation: [
    { id: "queued", title: "Queue", description: "Store the uploaded golden dataset for an evaluation worker.", artifact: "evaluation job", icon: ClipboardCheck },
    { id: "load_dataset", title: "Validate labels", description: "Load JSONL questions, expected sources, and answers.", artifact: "golden cases", icon: Braces },
    { id: "retrieval", title: "Retrieval metrics", description: "Measure recall, precision, hit rate, MRR, and latency.", artifact: "retrieval report", icon: Split },
    { id: "answer_quality", title: "Answer quality", description: "Run real queries and score citations and abstention.", artifact: "end-to-end report", icon: MessageSquareText },
    { id: "deepeval", title: "DeepEval", description: "Judge contextual quality, faithfulness, and answer relevance.", artifact: "semantic scores", icon: Network },
    { id: "report", title: "Release report", description: "Combine deterministic and model-judged measurements.", artifact: "quality decision", icon: CheckCheck },
  ],
};

export const workflowCopy: Record<WorkflowId, { eyebrow: string; title: string; summary: string }> = {
  ingestion: {
    eyebrow: "Knowledge preparation",
    title: "Watch a document become searchable knowledge.",
    summary: "Upload a real source and follow the worker through parsing, semantic chunking, embedding, and local hybrid indexing.",
  },
  query: {
    eyebrow: "Grounded answering",
    title: "See every decision behind one answer.",
    summary: "Stream the actual triage, hybrid retrieval, reranking, context assembly, generation, and citation-validation stages.",
  },
  evaluation: {
    eyebrow: "Quality assurance",
    title: "Measure retrieval and answer quality together.",
    summary: "Run a golden JSONL dataset through deterministic metrics, end-to-end checks, and optional DeepEval judge metrics.",
  },
};
