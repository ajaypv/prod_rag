import type { InterviewQuestion, Lesson, PageId, SourceReference } from "./types";

const ragPaper: SourceReference = { label: "Lewis et al., Retrieval-Augmented Generation (2020)", url: "https://arxiv.org/abs/2005.11401" };
const doclingConcepts: SourceReference = { label: "Docling documentation — concepts", url: "https://docling-project.github.io/docling/concepts/" };
const elasticHybrid: SourceReference = { label: "Elastic documentation — hybrid search", url: "https://www.elastic.co/docs/solutions/search/hybrid-search" };
const qdrantHybrid: SourceReference = { label: "Qdrant documentation — hybrid and multi-stage queries", url: "https://qdrant.tech/documentation/search/hybrid-queries/" };
const ragasMetrics: SourceReference = { label: "Ragas documentation — RAG evaluation metrics", url: "https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/" };
const nistGenAi: SourceReference = { label: "NIST AI 600-1 — Generative AI risk profile", url: "https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence" };
const otelGenAi: SourceReference = { label: "OpenTelemetry — GenAI semantic conventions", url: "https://opentelemetry.io/docs/specs/semconv/gen-ai/" };

export const lessons: Lesson[] = [
  {
    id: "what-is-rag", group: "Getting started", number: 1, title: "What is RAG?", shortTitle: "What is RAG?", duration: "5 min", visual: "pipeline",
    objective: "Understand the single idea that makes RAG useful.",
    visualCaption: "RAG searches trusted knowledge before the AI writes its response.",
    plain: "Retrieval-Augmented Generation, or RAG, gives an AI model relevant information from your own documents before it answers a question.",
    analogy: "Think of an open-book exam. The model is the student, retrieval finds the right pages, and the final answer must come from those pages.",
    steps: [
      { title: "Ask", text: "A person asks a question in everyday language." },
      { title: "Find", text: "The system searches the available knowledge for useful passages." },
      { title: "Answer", text: "The model receives those passages and creates a grounded response with sources." },
    ],
    technical: "RAG separates knowledge retrieval from language generation. The retrieval layer selects evidence at query time, while the generation model turns that evidence into a natural-language response.",
    interview: "RAG is an architecture that retrieves relevant external knowledge and supplies it to a language model as context before generation. It improves grounding and allows knowledge to be updated without retraining the model.",
    followUp: "How is RAG different from fine-tuning?",
    tradeoff: "RAG keeps knowledge current, but its answer quality depends heavily on retrieval quality.",
    sources: [ragPaper],
  },
  {
    id: "why-rag", group: "Getting started", number: 2, title: "Why do we need RAG?", shortTitle: "Why use RAG?", duration: "6 min", visual: "compare",
    objective: "See what RAG solves—and what it does not solve.",
    visualCaption: "Without evidence the model relies on learned memory; with RAG it can use current, private sources.",
    plain: "A model does not automatically know your private documents, and its learned knowledge may be old. RAG connects the model to information you control.",
    analogy: "A knowledgeable employee may still need the latest policy handbook. RAG places the relevant policy on their desk before they reply.",
    steps: [
      { title: "Private knowledge", text: "Use manuals, support articles, policies, and internal documentation." },
      { title: "Current knowledge", text: "Update the index when documents change instead of retraining the model." },
      { title: "Verifiable answers", text: "Return sources so a person can inspect the evidence." },
    ],
    technical: "RAG is appropriate when answers depend on a changing or access-controlled corpus. It is not a guarantee against hallucination; grounding prompts, citations, evaluation, and abstention remain necessary.",
    interview: "I use RAG when a model needs current, private, or domain-specific facts. It is easier to update and audit than embedding all changing knowledge through fine-tuning.",
    followUp: "When would you choose fine-tuning instead?",
    tradeoff: "RAG improves factual access but adds retrieval latency and operational complexity.",
    sources: [ragPaper],
  },
  {
    id: "prepare-documents", group: "How it works", number: 3, title: "Preparing documents for search", shortTitle: "Prepare documents", duration: "8 min", visual: "chunks",
    objective: "Learn why documents are parsed, divided, and labelled before search.",
    visualCaption: "A large document becomes smaller searchable passages while keeping its section context.",
    plain: "Search works better when a large document is divided into meaningful, manageable pieces called chunks.",
    analogy: "A library catalogue points to a chapter or page, not merely to a thousand-page book. Chunking creates those useful locations.",
    steps: [
      { title: "Parse", text: "Extract readable text and structure from PDF, HTML, Markdown, or office documents." },
      { title: "Create parent sections", text: "Keep headings and their surrounding explanation together." },
      { title: "Create child chunks", text: "Make smaller semantic passages for accurate retrieval." },
      { title: "Attach metadata", text: "Store title, section, version, tenant, and source details with every chunk." },
    ],
    technical: "Parent-child retrieval searches small semantic children for precision, then restores the larger parent section for generation. Stable identifiers and checksums make re-ingestion safe and repeatable.",
    interview: "I chunk documents along structural and semantic boundaries. I retrieve small child chunks for precision and expand winning children to parent sections so the model gets complete context.",
    followUp: "How would you choose chunk size and overlap?",
    tradeoff: "Small chunks improve matching but can lose context; large chunks preserve context but can reduce precision.",
    sources: [doclingConcepts],
  },
  {
    id: "find-information", group: "How it works", number: 4, title: "Finding the right information", shortTitle: "Find information", duration: "9 min", visual: "search",
    objective: "Understand meaning search, keyword search, and why both matter.",
    visualCaption: "One search path follows meaning; another follows exact words such as error codes.",
    plain: "RAG can search by meaning and by exact words. These methods solve different problems.",
    analogy: "A librarian understands a topic even when you use different words. A catalogue search is better when you know the exact title or code.",
    steps: [
      { title: "Meaning search", text: "Embeddings represent the meaning of the question and document chunks as vectors." },
      { title: "Keyword search", text: "BM25 rewards exact, important terms such as names, fields, and error codes." },
      { title: "Apply filters", text: "Limit results by tenant, product, version, or document permissions." },
    ],
    technical: "The same embedding model and version must represent both indexed documents and queries. BM25 remains a lexical, local calculation and complements dense vector similarity.",
    interview: "Dense retrieval handles semantic similarity and paraphrases, while BM25 handles exact identifiers and rare terms. A production system often combines both as hybrid retrieval.",
    followUp: "Why can dense retrieval miss an exact error code?",
    tradeoff: "Dense search understands intent but can miss exact tokens; BM25 finds tokens but may miss paraphrases.",
    sources: [elasticHybrid, qdrantHybrid],
  },
  {
    id: "improve-results", group: "How it works", number: 5, title: "Improving retrieved results", shortTitle: "Improve results", duration: "10 min", visual: "rerank",
    objective: "See how rank fusion and reranking turn candidates into strong evidence.",
    visualCaption: "Two ranked lists are fused, then a reranker reads the strongest candidates more carefully.",
    plain: "The first search is designed to find possible answers. A second stage then decides which candidates are truly the most relevant.",
    analogy: "First create a shortlist of job applicants quickly; then review the shortlist carefully before choosing finalists.",
    steps: [
      { title: "Retrieve candidates", text: "Dense and BM25 searches each return their strongest results." },
      { title: "Fuse ranks with RRF", text: "Reciprocal Rank Fusion combines positions without mixing incompatible score scales." },
      { title: "Rerank", text: "A relevance model reads the question together with each candidate and reorders them." },
      { title: "Build context", text: "Keep only the strongest unique parent sections within the evidence budget." },
    ],
    technical: "RRF uses reciprocal rank contributions rather than raw dense and sparse scores. Reranking is a separate model operation from query embedding and answer generation.",
    interview: "I retrieve broadly for recall, fuse dense and BM25 ranks with RRF, then rerank a bounded candidate set for precision before assembling final context.",
    followUp: "Why not rerank every document?",
    tradeoff: "More candidates can improve recall, but reranking too many increases latency and cost.",
    sources: [qdrantHybrid, elasticHybrid],
  },
  {
    id: "generate-answer", group: "How it works", number: 6, title: "Generating a grounded answer", shortTitle: "Generate an answer", duration: "7 min", visual: "answer",
    objective: "Learn what the answer model receives and why citations are checked.",
    visualCaption: "Only the final evidence enters the answer prompt, where each source has a traceable identifier.",
    plain: "The answer model receives the question plus selected evidence. It is instructed to answer only from that evidence and identify its sources.",
    analogy: "A writer receives a small research pack and must add a footnote for every claim instead of relying on memory.",
    steps: [
      { title: "Assemble evidence", text: "Place ranked source sections inside a bounded context window." },
      { title: "Generate", text: "Ask the model to answer only from the supplied sources." },
      { title: "Validate", text: "Confirm the response contains source identifiers that exist in the evidence." },
    ],
    technical: "Context is truncated deterministically to a configured character or token budget. Missing citations, NOT_FOUND, or unusable evidence produce an abstention rather than a normal answer.",
    interview: "The generator receives only selected source blocks with IDs. The prompt requires evidence-only answering and citations, and the application validates those citations before returning the response.",
    followUp: "Does a citation prove the answer is faithful?",
    tradeoff: "Citation presence is necessary but not sufficient; the cited source must actually support the claim.",
    sources: [ragPaper],
  },
  {
    id: "prevent-errors", group: "Quality and production", number: 7, title: "Preventing confident wrong answers", shortTitle: "Prevent wrong answers", duration: "8 min", visual: "shield",
    objective: "Understand confidence gates, abstention, and human review.",
    visualCaption: "Weak, unsafe, or unsupported requests leave the automatic path before an answer is returned.",
    plain: "A reliable RAG system must know when not to answer.",
    analogy: "A careful support agent escalates a ticket when the documentation is missing instead of inventing a policy.",
    steps: [
      { title: "Inspect the request", text: "Route sensitive or uncertain requests before retrieval." },
      { title: "Grade evidence", text: "Use explicit retrieval thresholds to identify weak context." },
      { title: "Validate the response", text: "Reject missing citations or unsupported generation." },
      { title: "Abstain", text: "Explain that evidence is insufficient and route to a person." },
    ],
    technical: "Safety triage, deterministic confidence thresholds, evidence-only prompts, citation validation, and human-review routing form independent safeguards.",
    interview: "I prevent hallucinations with layered controls: safe input routing, strong retrieval, confidence gates, evidence-only generation, citation validation, and an explicit abstention path.",
    followUp: "How would you tune an abstention threshold?",
    tradeoff: "A strict threshold reduces unsupported answers but increases the number of questions sent for human review.",
    sources: [nistGenAi],
  },
  {
    id: "measure-quality", group: "Quality and production", number: 8, title: "Measuring RAG quality", shortTitle: "Measure quality", duration: "10 min", visual: "quality",
    objective: "Separate retrieval quality from answer quality.",
    visualCaption: "Retrieval metrics ask what evidence was found; generation metrics ask how that evidence was used.",
    plain: "A good final answer requires both good evidence and good use of that evidence. These must be measured separately.",
    analogy: "First check whether a researcher found the right books. Then check whether their report accurately used those books.",
    steps: [
      { title: "Recall", text: "Of all expected relevant evidence, how much did retrieval find?" },
      { title: "Precision", text: "Of everything retrieved, how much was actually relevant?" },
      { title: "Faithfulness", text: "Are generated claims supported by the retrieved context?" },
      { title: "Abstention accuracy", text: "Does the system correctly refuse unanswerable questions?" },
    ],
    technical: "Golden evaluations should contain questions, expected document IDs, reference answers, and unanswerable cases. CI thresholds should gate releases rather than merely produce a report.",
    interview: "I evaluate retrieval with recall, precision, hit rate, and MRR; generation with correctness, completeness, faithfulness, and citation correctness; and safety with abstention accuracy.",
    followUp: "Can retrieval have perfect recall and still be poor?",
    tradeoff: "Returning everything can maximize recall while damaging precision, latency, and answer quality.",
    sources: [ragasMetrics],
  },
  {
    id: "production", group: "Quality and production", number: 9, title: "Taking RAG to production", shortTitle: "Production readiness", duration: "9 min", visual: "production",
    objective: "Know what must be operated after the demo works.",
    visualCaption: "Production readiness surrounds the query path with tracing, evaluation, security, and cost controls.",
    plain: "Production RAG is more than a working answer. It must remain measurable, secure, affordable, and recoverable as documents and usage change.",
    analogy: "A prototype is a working car; production readiness adds brakes, instruments, maintenance, traffic rules, and a service history.",
    steps: [
      { title: "Observe", text: "Trace retrieval scores, selected contexts, tokens, model calls, latency, and failures." },
      { title: "Protect", text: "Enforce tenant filters, permissions, upload validation, and secret management." },
      { title: "Control change", text: "Version documents, prompts, models, indexes, and evaluation datasets." },
      { title: "Watch quality and cost", text: "Alert on faithfulness drops, latency regression, and cost spikes." },
    ],
    technical: "Production systems need idempotent ingestion, revision replacement, timeouts, bounded retries, structured traces, quality regression gates, and documented recovery paths.",
    interview: "I treat retrieval quality as an operational signal. Every query is traced end to end, every release runs a golden evaluation, and changes to models, prompts, or indexes are versioned and reversible.",
    followUp: "Which production metrics would you alert on first?",
    tradeoff: "More safeguards and observability increase operational cost, but make quality failures diagnosable.",
    sources: [otelGenAi, nistGenAi, ragasMetrics],
  },
];

export const lessonGroups = ["Getting started", "How it works", "Quality and production"] as const;

const interviewPrompts = [
  "What is RAG, and how does it work?",
  "Why would you use RAG instead of relying on the model alone?",
  "How do you prepare documents for retrieval?",
  "What is hybrid retrieval, and why combine dense search with BM25?",
  "How do RRF and reranking improve retrieval results?",
  "How do you generate an answer that stays grounded in its sources?",
  "How do you reduce hallucinations in a RAG system?",
  "How do you evaluate RAG quality?",
  "What makes a RAG system production-ready?",
] as const;

export const interviewQuestions: InterviewQuestion[] = lessons.map((lesson, index) => ({
  category: lesson.group,
  question: interviewPrompts[index],
  quick: lesson.interview,
  detailed: lesson.technical,
  followUp: lesson.followUp,
  tradeoff: lesson.tradeoff,
  sources: lesson.sources,
}));

export const allPageIds: PageId[] = ["home", ...lessons.map((lesson) => lesson.id), "interview", "glossary"];
