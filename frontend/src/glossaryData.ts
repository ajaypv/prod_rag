export type GlossaryLevel = "Beginner" | "Intermediate" | "Advanced";

export interface GlossarySource {
  title: string;
  publisher: string;
  url: string;
}

export interface CitedCopy {
  text: string;
  citations: string[];
}

export interface GlossaryEntry {
  id: string;
  term: string;
  eyebrow: string;
  category: "Foundations" | "Ingestion & indexing" | "Retrieval" | "Ranking & context" | "Evaluation & trust";
  level: GlossaryLevel;
  readTime: string;
  definition: string;
  overview: CitedCopy[];
  mechanics: Array<{ title: string; copy: CitedCopy }>;
  example: { title: string; text: string };
  comparison?: {
    title: string;
    columns: [string, string, string];
    rows: Array<[string, string, string]>;
  };
  productionNotes: string[];
  interviewAnswer: string;
  related: string[];
  sourceIds: string[];
}

export const glossarySources: Record<string, GlossarySource> = {
  ragPaper: {
    title: "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
    publisher: "Lewis et al., NeurIPS 2020",
    url: "https://arxiv.org/abs/2005.11401",
  },
  docling: {
    title: "Docling concepts and document understanding",
    publisher: "Docling documentation",
    url: "https://docling-project.github.io/docling/concepts/",
  },
  azureChunking: {
    title: "RAG chunking phase and strategy selection",
    publisher: "Microsoft Azure Architecture Center",
    url: "https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/rag/rag-chunking-phase",
  },
  azureChunkDocs: {
    title: "Chunk large documents for RAG and vector search",
    publisher: "Microsoft Learn",
    url: "https://learn.microsoft.com/en-us/azure/search/vector-search-how-to-chunk-documents",
  },
  sbert: {
    title: "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks",
    publisher: "Reimers and Gurevych, EMNLP 2019",
    url: "https://arxiv.org/abs/1908.10084",
  },
  qdrantOverview: {
    title: "Understanding vector search in Qdrant",
    publisher: "Qdrant documentation",
    url: "https://qdrant.tech/documentation/overview/vector-search/",
  },
  qdrantIndexing: {
    title: "Vector indexing and filterable HNSW",
    publisher: "Qdrant documentation",
    url: "https://qdrant.tech/documentation/manage-data/indexing/",
  },
  qdrantFiltering: {
    title: "Filtering and payload indexes",
    publisher: "Qdrant documentation",
    url: "https://qdrant.tech/documentation/search/filtering/",
  },
  hnswPaper: {
    title: "Efficient and robust approximate nearest neighbor search using HNSW graphs",
    publisher: "Malkov and Yashunin",
    url: "https://arxiv.org/abs/1603.09320",
  },
  elasticBm25: {
    title: "Similarity settings: BM25",
    publisher: "Elasticsearch reference",
    url: "https://www.elastic.co/docs/reference/elasticsearch/index-settings/similarity",
  },
  elasticHybrid: {
    title: "Hybrid search",
    publisher: "Elastic documentation",
    url: "https://www.elastic.co/docs/solutions/search/hybrid-search",
  },
  rrfPaper: {
    title: "Reciprocal Rank Fusion outperforms Condorcet and individual rank learning methods",
    publisher: "Cormack, Clarke and Buettcher, SIGIR 2009",
    url: "https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf",
  },
  cohereRerank: {
    title: "An overview of reranking",
    publisher: "Cohere documentation",
    url: "https://docs.cohere.com/docs/rerank-overview",
  },
  cohereRerankPractice: {
    title: "Best practices for using rerank",
    publisher: "Cohere documentation",
    url: "https://docs.cohere.com/docs/reranking-best-practices",
  },
  ragasMetrics: {
    title: "Available RAG evaluation metrics",
    publisher: "Ragas documentation",
    url: "https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/",
  },
  ragasRecall: {
    title: "Context recall",
    publisher: "Ragas documentation",
    url: "https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_recall/",
  },
  ragasPrecision: {
    title: "Context precision",
    publisher: "Ragas documentation",
    url: "https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/",
  },
  ragasFaithfulness: {
    title: "Faithfulness",
    publisher: "Ragas documentation",
    url: "https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/",
  },
  irEvaluation: {
    title: "Evaluation of ranked retrieval results",
    publisher: "Stanford Introduction to Information Retrieval",
    url: "https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-of-ranked-retrieval-results-1.html",
  },
  azureEvaluation: {
    title: "RAG end-to-end evaluation phase",
    publisher: "Microsoft Azure Architecture Center",
    url: "https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/rag/rag-llm-evaluation-phase",
  },
  nistGenAi: {
    title: "Artificial Intelligence Risk Management Framework: Generative AI Profile",
    publisher: "NIST AI 600-1",
    url: "https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence",
  },
};

export const glossaryEntries: GlossaryEntry[] = [
  {
    id: "rag",
    term: "Retrieval-Augmented Generation",
    eyebrow: "RAG",
    category: "Foundations",
    level: "Beginner",
    readTime: "5 min",
    definition: "An architecture that retrieves external evidence and gives it to a language model before the model writes an answer.",
    overview: [
      {
        text: "RAG joins two systems: a retriever that finds relevant knowledge and a generator that turns that knowledge into a useful response. The source collection is external to the language model, so teams can update documents without retraining the generator.",
        citations: ["ragPaper"],
      },
      {
        text: "The important production idea is grounding, not merely search. Retrieved passages must be relevant, fit inside the context budget, support the final claims, and remain traceable through citations.",
        citations: ["ragPaper", "azureEvaluation"],
      },
    ],
    mechanics: [
      { title: "Retrieve", copy: { text: "Turn the question into a search request and collect candidate passages from an approved corpus.", citations: ["ragPaper"] } },
      { title: "Assemble context", copy: { text: "Rank, deduplicate, and pack the strongest evidence into a bounded prompt.", citations: ["azureEvaluation"] } },
      { title: "Generate and verify", copy: { text: "Ask the model to answer from that evidence, then validate citations and abstain when support is insufficient.", citations: ["nistGenAi"] } },
    ],
    example: {
      title: "A policy assistant",
      text: "A user asks, “Can I cancel after 20 days?” Retrieval finds the current cancellation-policy section, and the model answers from that section with its document and page reference.",
    },
    comparison: {
      title: "RAG compared with fine-tuning",
      columns: ["Question", "RAG", "Fine-tuning"],
      rows: [
        ["Where knowledge lives", "External searchable corpus", "Model parameters"],
        ["How knowledge changes", "Re-index documents", "Train another model version"],
        ["Best fit", "Current, private, attributable facts", "Behavior, style, or task adaptation"],
      ],
    },
    productionNotes: [
      "Version the corpus, embedding model, ranking configuration, and prompt together.",
      "Treat retrieval failure and unsupported generation as separate failure modes.",
      "Store source identifiers through every stage so citations can be validated.",
    ],
    interviewAnswer: "RAG retrieves relevant external knowledge at query time and supplies it as context to a language model. It is useful for current or private facts, but production quality still depends on retrieval evaluation, grounding, citations, and abstention.",
    related: ["document-parsing", "hybrid-retrieval", "faithfulness", "golden-evaluation"],
    sourceIds: ["ragPaper", "azureEvaluation", "nistGenAi"],
  },
  {
    id: "document-parsing",
    term: "Document parsing",
    eyebrow: "Before chunking",
    category: "Ingestion & indexing",
    level: "Beginner",
    readTime: "6 min",
    definition: "Converting PDFs, HTML, Markdown, office files, and images into structured content that the retrieval pipeline can understand.",
    overview: [
      {
        text: "Parsing is not the same as copying visible text. A useful parser preserves headings, lists, tables, reading order, page numbers, and document relationships so later chunks retain meaning and provenance.",
        citations: ["docling", "azureChunking"],
      },
      {
        text: "Bad parsing becomes bad retrieval: a split table, repeated header, or incorrect reading order can produce embeddings that accurately represent the wrong text. Parsing quality should therefore be evaluated before ranking quality.",
        citations: ["docling"],
      },
    ],
    mechanics: [
      { title: "Recognize structure", copy: { text: "Identify titles, headings, paragraphs, tables, captions, lists, and page boundaries.", citations: ["docling"] } },
      { title: "Normalize", copy: { text: "Remove repeated furniture and repair reading order while retaining meaningful formatting.", citations: ["azureChunking"] } },
      { title: "Emit traceable content", copy: { text: "Produce structured text plus metadata such as source file, page, section path, and content type.", citations: ["docling"] } },
    ],
    example: {
      title: "A PDF pricing table",
      text: "Plain extraction may interleave columns and detach prices from product names. A structure-aware parser emits the table as rows with the page and heading, allowing one coherent chunk to be retrieved.",
    },
    comparison: {
      title: "Parsing choices",
      columns: ["Approach", "Strength", "Risk"],
      rows: [
        ["Plain text", "Fast for simple files", "Loses layout and tables"],
        ["Layout-aware", "Preserves structure", "Higher processing cost"],
        ["OCR", "Handles scanned pages", "Recognition errors need review"],
      ],
    },
    productionNotes: [
      "Keep the original file and a parser-version field for reproducibility.",
      "Sample table-heavy and multi-column pages during ingestion QA.",
      "Do not silently index empty or nearly empty extraction results.",
    ],
    interviewAnswer: "Document parsing converts source files into structured, traceable content before chunking. I preserve headings, tables, reading order, page numbers, and metadata because parsing errors propagate directly into retrieval and citations.",
    related: ["chunking", "parent-child-chunking", "golden-evaluation"],
    sourceIds: ["docling", "azureChunking"],
  },
  {
    id: "chunking",
    term: "Chunking",
    eyebrow: "Segmentation strategies",
    category: "Ingestion & indexing",
    level: "Beginner",
    readTime: "8 min",
    definition: "Dividing a document into searchable units that are small enough to match precisely but large enough to carry complete meaning.",
    overview: [
      {
        text: "Chunk size controls a central RAG trade-off. Very small chunks match narrow phrases but can lose qualifiers and surrounding logic. Very large chunks preserve context but introduce unrelated text, consume more tokens, and can lower retrieval precision.",
        citations: ["azureChunking", "azureChunkDocs"],
      },
      {
        text: "There is no universal best size. Fixed-size, sentence, structure-aware, semantic, and parent-child strategies should be compared on representative documents and golden questions.",
        citations: ["azureChunking"],
      },
    ],
    mechanics: [
      { title: "Choose boundaries", copy: { text: "Split by tokens, sentences, headings, layout elements, or semantic change points.", citations: ["azureChunkDocs"] } },
      { title: "Preserve continuity", copy: { text: "Use overlap or inherited heading metadata when an idea crosses a boundary.", citations: ["azureChunkDocs"] } },
      { title: "Evaluate the result", copy: { text: "Measure retrieval on the actual corpus; visual inspection alone cannot prove that a strategy works.", citations: ["azureChunking", "azureEvaluation"] } },
    ],
    example: {
      title: "A troubleshooting manual",
      text: "A heading-aware splitter keeps “ERR_AUTH_17” with its cause and repair steps. A blind 450-token cut might place the code in one chunk and the repair in another.",
    },
    comparison: {
      title: "Common chunking strategies",
      columns: ["Strategy", "Use it when", "Main trade-off"],
      rows: [
        ["Fixed size + overlap", "Documents are inconsistent or unstructured", "Simple, but can cut ideas"],
        ["Sentence / paragraph", "Prose has reliable boundaries", "Natural units can vary greatly"],
        ["Structure-aware", "Headings and layout carry meaning", "Depends on parsing quality"],
        ["Semantic", "Topics shift inside long sections", "More compute and tuning"],
        ["Parent-child", "Search needs precision and answers need context", "More storage and linking logic"],
      ],
    },
    productionNotes: [
      "Record chunker name, version, target size, overlap, and document checksum.",
      "Test several document types; one strategy may not fit manuals, tables, and FAQs equally.",
      "Re-run retrieval evaluation whenever chunking changes because every indexed unit changes.",
    ],
    interviewAnswer: "Chunking creates the retrieval units. I choose boundaries based on document structure, then tune size and overlap against golden queries. Smaller chunks favor precise matching; larger chunks preserve context, so parent-child retrieval is often a useful compromise.",
    related: ["document-parsing", "parent-child-chunking", "recall", "precision"],
    sourceIds: ["azureChunking", "azureChunkDocs", "azureEvaluation"],
  },
  {
    id: "parent-child-chunking",
    term: "Parent-child chunking",
    eyebrow: "Small-to-big retrieval",
    category: "Ingestion & indexing",
    level: "Intermediate",
    readTime: "6 min",
    definition: "Searching small child passages for precision, then returning their larger parent sections to the answer model for context.",
    overview: [
      {
        text: "A child chunk is optimized for matching; its parent is optimized for reading. The index stores a stable parent identifier on every child so winning children can be expanded after retrieval.",
        citations: ["azureChunking", "azureChunkDocs"],
      },
      {
        text: "Expansion must be bounded and deduplicated. Several winning children can point to the same parent, and blindly returning every parent can erase the context-budget advantage.",
        citations: ["azureEvaluation"],
      },
    ],
    mechanics: [
      { title: "Create parents", copy: { text: "Build coherent sections around headings or larger semantic units.", citations: ["azureChunking"] } },
      { title: "Index children", copy: { text: "Split each parent into smaller passages and store their parent IDs and metadata.", citations: ["azureChunkDocs"] } },
      { title: "Expand winners", copy: { text: "Search and rerank children, then replace top children with unique parents for generation.", citations: ["azureEvaluation"] } },
    ],
    example: {
      title: "One match, complete procedure",
      text: "The sentence “rotate the key after 24 hours” matches the query. The system returns its full “Credential rotation” section so prerequisites and rollback steps are not lost.",
    },
    comparison: {
      title: "Child versus parent",
      columns: ["Unit", "Optimized for", "Typical failure if used alone"],
      rows: [
        ["Child", "Precise retrieval", "Answer lacks surrounding conditions"],
        ["Parent", "Complete answer context", "Search score is diluted by extra text"],
        ["Combined", "Precision plus context", "Requires stable linking and deduplication"],
      ],
    },
    productionNotes: [
      "Keep parent IDs stable across retries of the same ingestion revision.",
      "Deduplicate parents before enforcing the final context limit.",
      "Evaluate child-level retrieval and parent-level answer support separately.",
    ],
    interviewAnswer: "Parent-child retrieval searches small child chunks for accurate matching and expands the winners to larger parent sections for generation. It combines retrieval precision with enough context to answer completely.",
    related: ["chunking", "reranking", "precision", "faithfulness"],
    sourceIds: ["azureChunking", "azureChunkDocs", "azureEvaluation"],
  },
  {
    id: "embedding",
    term: "Embedding",
    eyebrow: "Meaning as numbers",
    category: "Ingestion & indexing",
    level: "Beginner",
    readTime: "6 min",
    definition: "A fixed-length numeric representation in which texts with related meaning are intended to be near one another.",
    overview: [
      {
        text: "An embedding model maps a query or passage to a vector. A similarity function such as cosine similarity compares vectors, allowing retrieval to find paraphrases even when they do not share the same words.",
        citations: ["sbert", "qdrantOverview"],
      },
      {
        text: "Query and document vectors must be compatible. Changing model, version, dimensions, or task mode on only one side makes similarity scores meaningless and normally requires re-embedding the corpus.",
        citations: ["sbert", "qdrantOverview"],
      },
    ],
    mechanics: [
      { title: "Encode documents", copy: { text: "Run each searchable chunk through the selected embedding model during ingestion.", citations: ["sbert"] } },
      { title: "Encode the query", copy: { text: "Use the compatible query mode or model version when a user asks a question.", citations: ["qdrantOverview"] } },
      { title: "Compare", copy: { text: "Use the distance metric configured for the collection to rank nearby vectors.", citations: ["qdrantOverview"] } },
    ],
    example: {
      title: "Paraphrase matching",
      text: "“How do I end my subscription?” can be close to “cancellation procedure” even though the exact words differ. BM25 may need shared terms; dense retrieval can use their semantic relationship.",
    },
    comparison: {
      title: "Embedding decisions",
      columns: ["Decision", "What it affects", "What to verify"],
      rows: [
        ["Model", "Domain and language quality", "Golden-query recall"],
        ["Dimension", "Storage and index shape", "Database collection schema"],
        ["Similarity", "How closeness is scored", "Model recommendation"],
      ],
    },
    productionNotes: [
      "Persist embedding provider, model ID, version, dimensions, and normalization settings.",
      "Treat an embedding migration as an index migration, not a prompt-only change.",
      "Benchmark domain terms, abbreviations, and multilingual questions before rollout.",
    ],
    interviewAnswer: "An embedding converts text into a vector so semantic similarity can be computed. Documents and queries must use compatible model settings, and changing the embedding model generally requires re-indexing and retrieval regression testing.",
    related: ["dense-retrieval", "vector-database", "hnsw", "hybrid-retrieval"],
    sourceIds: ["sbert", "qdrantOverview"],
  },
  {
    id: "vector-database",
    term: "Vector database",
    eyebrow: "Local semantic index",
    category: "Ingestion & indexing",
    level: "Beginner",
    readTime: "6 min",
    definition: "A data system that stores vectors with identifiers and metadata and supports efficient similarity search.",
    overview: [
      {
        text: "A vector database stores more than an array of numbers. A useful RAG record combines a vector, the searchable text or reference to it, payload metadata, source identity, and indexes for similarity and filtering.",
        citations: ["qdrantOverview", "qdrantFiltering"],
      },
      {
        text: "It can run locally; locality and database type are separate choices. A local database simplifies data placement for a demonstration, but backups, capacity, permissions, and corruption recovery still matter.",
        citations: ["qdrantOverview"],
      },
    ],
    mechanics: [
      { title: "Store points", copy: { text: "Write each chunk vector with a stable ID and payload such as tenant, document, page, and parent ID.", citations: ["qdrantOverview"] } },
      { title: "Build indexes", copy: { text: "Create vector and payload indexes appropriate to the expected search and filter patterns.", citations: ["qdrantIndexing"] } },
      { title: "Query and filter", copy: { text: "Find nearest vectors while enforcing metadata and access constraints.", citations: ["qdrantFiltering"] } },
    ],
    example: {
      title: "A local support corpus",
      text: "Each support-manual chunk is stored as a vector plus product, version, page, and parent-section metadata. A query searches meaning but filters to the user’s product version.",
    },
    comparison: {
      title: "Vector index versus vector database",
      columns: ["Capability", "Index library", "Database"],
      rows: [
        ["Nearest-neighbor search", "Yes", "Yes"],
        ["Persistence and updates", "Application-managed", "Built in"],
        ["Metadata filtering", "Often custom", "Usually integrated"],
        ["Operational controls", "Application-managed", "Database-specific"],
      ],
    },
    productionNotes: [
      "Create payload indexes for fields used in filters.",
      "Back up both vectors and the metadata needed to rebuild them.",
      "Measure resident memory, index-build time, query latency, and ANN recall at expected scale.",
    ],
    interviewAnswer: "A vector database persists embeddings and payload metadata and provides approximate nearest-neighbor search plus filtering. In RAG, it maps a query vector to candidate chunks while preserving source and access metadata.",
    related: ["embedding", "hnsw", "metadata-filtering", "dense-retrieval"],
    sourceIds: ["qdrantOverview", "qdrantIndexing", "qdrantFiltering"],
  },
  {
    id: "hnsw",
    term: "HNSW",
    eyebrow: "Approximate nearest neighbors",
    category: "Ingestion & indexing",
    level: "Advanced",
    readTime: "8 min",
    definition: "Hierarchical Navigable Small World: a graph index that speeds vector search by navigating layers of linked neighbors instead of scanning every vector.",
    overview: [
      {
        text: "HNSW builds multiple graph layers. Search begins in a sparse upper layer, moves toward promising regions, and descends into denser layers until it finds near neighbors. This makes search fast but approximate: the true nearest item is not guaranteed every time.",
        citations: ["hnswPaper", "qdrantIndexing"],
      },
      {
        text: "The key production trade-off is speed, memory, and recall. Broader construction and search parameters usually improve ANN recall but consume more build time, memory, or query latency.",
        citations: ["hnswPaper", "qdrantIndexing"],
      },
    ],
    mechanics: [
      { title: "Build the graph", copy: { text: "Insert vectors and connect each one to nearby neighbors across hierarchical layers.", citations: ["hnswPaper"] } },
      { title: "Navigate", copy: { text: "Start high, greedily approach the query region, then descend for a finer search.", citations: ["qdrantIndexing"] } },
      { title: "Tune breadth", copy: { text: "Use construction and search breadth settings to balance latency, memory, and missed neighbors.", citations: ["qdrantIndexing"] } },
    ],
    example: {
      title: "Why enable an index",
      text: "With a few hundred chunks, an exact scan may be acceptable. With millions, HNSW avoids comparing the query with every vector, reducing latency while accepting a measurable approximation risk.",
    },
    comparison: {
      title: "Exact versus HNSW search",
      columns: ["Property", "Exact scan", "HNSW"],
      rows: [
        ["Result", "True nearest neighbors", "Approximate neighbors"],
        ["Query cost", "Grows with all vectors", "Navigates a graph subset"],
        ["Extra index memory", "Low", "Graph edges require memory"],
        ["Primary quality test", "Retrieval relevance", "ANN recall plus retrieval relevance"],
      ],
    },
    productionNotes: [
      "Measure ANN recall against exact search on a representative sample.",
      "Tune with production filters; strict filtering can change graph behavior.",
      "Account for index-build time and memory during ingestion and restart.",
    ],
    interviewAnswer: "HNSW is a layered graph index for approximate nearest-neighbor search. It avoids scanning every vector, so it is fast at scale, but I tune and measure it against exact search because latency, memory, and ANN recall trade off.",
    related: ["vector-database", "dense-retrieval", "recall", "metadata-filtering"],
    sourceIds: ["hnswPaper", "qdrantIndexing"],
  },
  {
    id: "dense-retrieval",
    term: "Dense retrieval",
    eyebrow: "Semantic search",
    category: "Retrieval",
    level: "Beginner",
    readTime: "6 min",
    definition: "Retrieving passages by comparing dense query and document embeddings rather than relying on exact words alone.",
    overview: [
      {
        text: "Dense retrieval is strong when users paraphrase, use synonyms, or describe a concept without copying document wording. It ranks chunks whose vectors are near the query vector.",
        citations: ["sbert", "qdrantOverview"],
      },
      {
        text: "Semantic similarity does not replace exact matching. Dense retrieval can miss rare identifiers, versions, names, or error codes, which is why it is commonly paired with lexical retrieval.",
        citations: ["elasticHybrid"],
      },
    ],
    mechanics: [
      { title: "Embed the query", copy: { text: "Encode the user question with settings compatible with the indexed documents.", citations: ["sbert"] } },
      { title: "Search neighbors", copy: { text: "Use exact or approximate vector search to collect the top semantic candidates.", citations: ["qdrantOverview"] } },
      { title: "Apply constraints", copy: { text: "Filter candidates by tenant, version, permissions, and other non-semantic requirements.", citations: ["qdrantFiltering"] } },
    ],
    example: {
      title: "Meaning without matching words",
      text: "The query “stop paying for the service” can retrieve a section titled “Subscription cancellation,” even if “stop paying” never occurs in the document.",
    },
    comparison: {
      title: "Dense versus lexical retrieval",
      columns: ["Question type", "Dense", "BM25"],
      rows: [
        ["Paraphrase", "Usually strong", "May miss"],
        ["Exact error code", "May miss", "Usually strong"],
        ["New domain acronym", "Model-dependent", "Strong if exact"],
      ],
    },
    productionNotes: [
      "Keep document and query embedding configurations compatible.",
      "Evaluate rare identifiers separately from natural-language questions.",
      "Log top scores and selected document IDs, but do not treat one global score as calibrated confidence.",
    ],
    interviewAnswer: "Dense retrieval embeds the question and chunks into vectors and searches by semantic closeness. It handles paraphrases well, but exact codes and rare terms often need BM25, so I normally evaluate a hybrid design.",
    related: ["embedding", "bm25", "hybrid-retrieval", "hnsw"],
    sourceIds: ["sbert", "qdrantOverview", "elasticHybrid", "qdrantFiltering"],
  },
  {
    id: "bm25",
    term: "BM25",
    eyebrow: "Lexical retrieval",
    category: "Retrieval",
    level: "Intermediate",
    readTime: "7 min",
    definition: "A lexical ranking function that rewards important query-term matches while normalizing for document length and repeated-term saturation.",
    overview: [
      {
        text: "BM25 works with tokens rather than embeddings. A match receives more weight when the term is rare across the corpus, while repeated occurrences eventually add less value and document length is normalized.",
        citations: ["elasticBm25"],
      },
      {
        text: "Its main RAG advantage is exactness. Product names, field names, SKUs, error codes, and uncommon acronyms may be easier to retrieve lexically than semantically.",
        citations: ["elasticHybrid"],
      },
    ],
    mechanics: [
      { title: "Tokenize", copy: { text: "Analyze documents and the query into comparable terms.", citations: ["elasticBm25"] } },
      { title: "Weight terms", copy: { text: "Give rarer corpus terms more information value and saturate repeated term frequency.", citations: ["elasticBm25"] } },
      { title: "Normalize length", copy: { text: "Reduce the unfair advantage that long documents would receive merely by containing more words.", citations: ["elasticBm25"] } },
    ],
    example: {
      title: "An exact identifier",
      text: "For “ERR_AUTH_17,” an exact token match is highly informative. A dense model might group it with generic authentication errors, while BM25 can place the exact code first.",
    },
    comparison: {
      title: "What changes the BM25 score",
      columns: ["Signal", "Effect", "Reason"],
      rows: [
        ["Rare matched term", "Higher", "More discriminative in the corpus"],
        ["Repeated term", "Rises, then saturates", "Avoids keyword stuffing dominance"],
        ["Long document", "Normalized", "Controls length bias"],
      ],
    },
    productionNotes: [
      "Inspect tokenizer behavior for punctuation-heavy codes and domain identifiers.",
      "Tune analyzers before blindly tuning BM25 constants.",
      "Do not directly average BM25 and vector scores unless their scales are calibrated.",
    ],
    interviewAnswer: "BM25 is a lexical ranking function based on term importance, frequency saturation, and length normalization. It complements dense retrieval because it is strong for exact names, error codes, and rare domain terms.",
    related: ["dense-retrieval", "hybrid-retrieval", "rrf", "precision"],
    sourceIds: ["elasticBm25", "elasticHybrid"],
  },
  {
    id: "hybrid-retrieval",
    term: "Hybrid retrieval",
    eyebrow: "Dense + lexical",
    category: "Retrieval",
    level: "Intermediate",
    readTime: "7 min",
    definition: "Running semantic and lexical retrieval together, then combining their candidates into one ranked list.",
    overview: [
      {
        text: "Hybrid retrieval covers two different relevance signals. Dense search understands meaning and paraphrase; lexical search preserves exact-term strength. Combining them reduces dependence on either model behavior or token overlap alone.",
        citations: ["elasticHybrid"],
      },
      {
        text: "The lists still need fusion. Because dense similarity and BM25 scores have different scales, rank-based methods such as RRF are often safer than adding raw scores.",
        citations: ["elasticHybrid", "rrfPaper"],
      },
    ],
    mechanics: [
      { title: "Search semantic", copy: { text: "Retrieve top candidates using the query embedding.", citations: ["elasticHybrid"] } },
      { title: "Search lexical", copy: { text: "Retrieve a separate list using analyzed query terms and BM25.", citations: ["elasticHybrid"] } },
      { title: "Fuse and rerank", copy: { text: "Merge ranks, deduplicate chunks, and optionally apply a stronger reranker.", citations: ["rrfPaper", "cohereRerank"] } },
    ],
    example: {
      title: "One query, two strengths",
      text: "“Why did ERR_AUTH_17 log me out?” lets BM25 lock onto the code while dense retrieval finds explanations about expired sessions. Fusion retains candidates from both routes.",
    },
    comparison: {
      title: "Retrieval modes",
      columns: ["Mode", "Strength", "Weakness"],
      rows: [
        ["Dense only", "Meaning and paraphrase", "Exact identifiers"],
        ["BM25 only", "Exact terms", "Vocabulary mismatch"],
        ["Hybrid", "Broader coverage", "More tuning and compute"],
      ],
    },
    productionNotes: [
      "Log dense, lexical, fused, and final ranks separately for diagnosis.",
      "Evaluate hybrid against each individual retriever; complexity needs evidence of improvement.",
      "Apply the same access filters to both retrieval paths.",
    ],
    interviewAnswer: "Hybrid retrieval runs dense and BM25 search together. Dense search finds semantic matches, BM25 finds exact terms, and a fusion method such as RRF combines their rankings before optional reranking.",
    related: ["dense-retrieval", "bm25", "rrf", "reranking"],
    sourceIds: ["elasticHybrid", "rrfPaper", "cohereRerank"],
  },
  {
    id: "metadata-filtering",
    term: "Metadata filtering",
    eyebrow: "Retrieval constraints",
    category: "Retrieval",
    level: "Intermediate",
    readTime: "6 min",
    definition: "Restricting search by structured attributes such as tenant, product, version, language, date, or permission before results are accepted.",
    overview: [
      {
        text: "Similarity answers “what looks relevant?” Filtering answers “what is allowed and applicable?” An excellent semantic match from the wrong tenant or obsolete product version is still an invalid result.",
        citations: ["qdrantFiltering"],
      },
      {
        text: "Filter fields should be designed and indexed deliberately. Strict or complex filters can affect approximate-search behavior and latency, so filter-aware retrieval needs its own tests.",
        citations: ["qdrantIndexing", "qdrantFiltering"],
      },
    ],
    mechanics: [
      { title: "Attach payload", copy: { text: "Store normalized metadata on every chunk during ingestion.", citations: ["qdrantFiltering"] } },
      { title: "Build payload indexes", copy: { text: "Index fields used repeatedly in filters rather than scanning them at query time.", citations: ["qdrantIndexing"] } },
      { title: "Enforce consistently", copy: { text: "Apply authorization and applicability conditions to every dense, sparse, and fallback route.", citations: ["qdrantFiltering"] } },
    ],
    example: {
      title: "Correct answer, wrong customer",
      text: "Two tenants have different refund policies. Without a tenant filter, retrieval may return the semantically closest policy from the wrong tenant and generate a confidently incorrect answer.",
    },
    comparison: {
      title: "Common filter purposes",
      columns: ["Field", "Purpose", "Failure prevented"],
      rows: [
        ["tenant_id", "Isolation", "Cross-customer leakage"],
        ["product_version", "Applicability", "Obsolete instructions"],
        ["access_group", "Authorization", "Unauthorized disclosure"],
      ],
    },
    productionNotes: [
      "Treat authorization filters as security controls, not ranking preferences.",
      "Reject records missing mandatory isolation metadata.",
      "Include filtered and zero-result queries in regression and latency tests.",
    ],
    interviewAnswer: "Metadata filtering constrains semantic or lexical results using structured fields such as tenant, version, and permissions. It prevents irrelevant or unauthorized evidence from entering the answer path and must be applied consistently to every retriever.",
    related: ["vector-database", "hnsw", "hybrid-retrieval", "abstention"],
    sourceIds: ["qdrantFiltering", "qdrantIndexing"],
  },
  {
    id: "rrf",
    term: "Reciprocal Rank Fusion",
    eyebrow: "RRF",
    category: "Ranking & context",
    level: "Intermediate",
    readTime: "7 min",
    definition: "A method that combines ranked lists using reciprocal rank positions instead of mixing their raw scores.",
    overview: [
      {
        text: "RRF gives each document a contribution based on where it appears in each list, commonly expressed as 1 / (k + rank). A result appearing near the top of several lists accumulates more support.",
        citations: ["rrfPaper"],
      },
      {
        text: "Its practical advantage is scale independence. BM25 and cosine similarity do not need to be normalized into a common numeric meaning before fusion.",
        citations: ["rrfPaper", "elasticHybrid"],
      },
    ],
    mechanics: [
      { title: "Collect ranks", copy: { text: "Keep the ordered dense and lexical candidate lists.", citations: ["elasticHybrid"] } },
      { title: "Add reciprocal contributions", copy: { text: "For each result, add a rank-based contribution from every list where it appears.", citations: ["rrfPaper"] } },
      { title: "Sort the total", copy: { text: "Order candidates by fused score, then deduplicate or pass them to a reranker.", citations: ["rrfPaper"] } },
    ],
    example: {
      title: "A simple fusion",
      text: "If passage A ranks 1st in BM25 and 4th in dense search, it receives contributions from both. Passage B ranked 1st in only one list can still lose when A has consistent cross-retriever evidence.",
    },
    comparison: {
      title: "Fusion choices",
      columns: ["Method", "Input", "Caution"],
      rows: [
        ["Raw score sum", "Retriever scores", "Scales may be incompatible"],
        ["Weighted normalized sum", "Calibrated scores", "Needs tuning and stable distributions"],
        ["RRF", "Rank positions", "Discards score-margin information"],
      ],
    },
    productionNotes: [
      "Tune list depths and the RRF constant using golden queries.",
      "Retain per-retriever ranks in traces so fused results remain explainable.",
      "Remember that fusion improves ordering; it does not deeply read the candidate text.",
    ],
    interviewAnswer: "RRF combines multiple result lists using reciprocal rank contributions. It is useful for hybrid retrieval because it avoids directly mixing incomparable BM25 and dense similarity scores, although a later reranker can still improve final relevance.",
    related: ["hybrid-retrieval", "bm25", "reranking", "ranking-metrics"],
    sourceIds: ["rrfPaper", "elasticHybrid"],
  },
  {
    id: "reranking",
    term: "Reranking",
    eyebrow: "Second-stage relevance",
    category: "Ranking & context",
    level: "Intermediate",
    readTime: "8 min",
    definition: "A second-stage model pass that scores a bounded candidate set against the complete query and reorders it by relevance.",
    overview: [
      {
        text: "Initial retrieval is optimized to search a large corpus cheaply and preserve recall. A reranker spends more computation on a much smaller list, reading the query together with each candidate to make a finer relevance judgment.",
        citations: ["cohereRerank"],
      },
      {
        text: "Reranking is distinct from RRF. RRF combines existing rank positions; a semantic reranker produces a new query-document relevance order. It is also a separate model call from query embedding and answer generation when a hosted model is used.",
        citations: ["cohereRerank", "rrfPaper"],
      },
    ],
    mechanics: [
      { title: "Retrieve broadly", copy: { text: "Send only the top bounded candidates from dense, lexical, or fused retrieval.", citations: ["cohereRerankPractice"] } },
      { title: "Score query with candidate", copy: { text: "The reranker evaluates each candidate in the context of the query and emits a new relevance order.", citations: ["cohereRerank"] } },
      { title: "Cut final context", copy: { text: "Keep the strongest unique evidence within the context budget and calibrated acceptance policy.", citations: ["cohereRerankPractice"] } },
    ],
    example: {
      title: "From shortlist to evidence",
      text: "Hybrid search returns 20 plausible passages. The reranker notices that only three directly answer the cancellation-window question, moves them to the top, and the context builder keeps their two unique parent sections.",
    },
    comparison: {
      title: "RRF versus reranking",
      columns: ["Property", "RRF", "Semantic reranker"],
      rows: [
        ["Reads text deeply", "No", "Yes"],
        ["Input", "Ranked lists", "Query + candidates"],
        ["Cost", "Very low", "Higher model compute"],
        ["Role", "Fuse retrievers", "Improve final precision"],
      ],
    },
    productionNotes: [
      "Bound candidate count and text length to control latency and cost.",
      "Tune relevance thresholds on representative borderline examples; scores are query-dependent.",
      "Evaluate the no-rerank baseline so the added model call earns its place.",
    ],
    interviewAnswer: "Reranking is a more expensive second-stage relevance pass over a small candidate set. Retrieval finds broadly for recall, RRF can fuse lists, and the reranker then reads query-document pairs more carefully to improve final precision.",
    related: ["rrf", "hybrid-retrieval", "precision", "parent-child-chunking"],
    sourceIds: ["cohereRerank", "cohereRerankPractice", "rrfPaper"],
  },
  {
    id: "recall",
    term: "Recall",
    eyebrow: "Retrieval coverage",
    category: "Evaluation & trust",
    level: "Beginner",
    readTime: "7 min",
    definition: "The fraction of all expected relevant evidence that the retriever successfully returned.",
    overview: [
      {
        text: "Recall asks whether retrieval missed anything important. For ID-labelled evaluation, recall is relevant IDs retrieved divided by all reference relevant IDs. It therefore requires a reference set, not just model confidence.",
        citations: ["ragasRecall", "irEvaluation"],
      },
      {
        text: "Recall depends on the cutoff. Recall@5 and Recall@20 answer different questions. Returning more candidates often raises recall but can reduce precision and increase reranking or generation cost.",
        citations: ["irEvaluation", "azureEvaluation"],
      },
    ],
    mechanics: [
      { title: "Label expected evidence", copy: { text: "For each golden question, record the document or chunk IDs that can support the answer.", citations: ["ragasRecall"] } },
      { title: "Run retrieval at a cutoff", copy: { text: "Collect the top-k candidate IDs before answer generation.", citations: ["irEvaluation"] } },
      { title: "Count coverage", copy: { text: "Divide the number of expected relevant IDs found by the total expected relevant IDs.", citations: ["ragasRecall"] } },
    ],
    example: {
      title: "Recall@5",
      text: "The golden set expects four relevant passages. The top five results contain three of them. Recall@5 = 3 / 4 = 0.75.",
    },
    comparison: {
      title: "Recall and precision use the same counts differently",
      columns: ["Metric", "Question", "Formula"],
      rows: [
        ["Recall", "How much relevant evidence did we find?", "TP / (TP + FN)"],
        ["Precision", "How much retrieved evidence was useful?", "TP / (TP + FP)"],
        ["Hit rate", "Did we find at least one relevant item?", "Queries with a hit / all queries"],
      ],
    },
    productionNotes: [
      "Always report the cutoff, such as Recall@5.",
      "Measure answerable and unanswerable questions separately.",
      "Do not celebrate perfect recall obtained by returning most of the corpus.",
    ],
    interviewAnswer: "Recall measures coverage: of all evidence labelled relevant, how much did retrieval find? I report it at a cutoff and pair it with precision because increasing top-k can improve recall while adding noise.",
    related: ["precision", "ranking-metrics", "golden-evaluation", "chunking"],
    sourceIds: ["ragasRecall", "irEvaluation", "azureEvaluation"],
  },
  {
    id: "precision",
    term: "Precision",
    eyebrow: "Retrieval focus",
    category: "Evaluation & trust",
    level: "Beginner",
    readTime: "7 min",
    definition: "The fraction of retrieved items that are actually relevant to the question.",
    overview: [
      {
        text: "Precision measures noise in the returned set. For binary relevance labels, it is relevant retrieved items divided by all retrieved items. Ranked context-precision variants also reward placing relevant contexts earlier.",
        citations: ["ragasPrecision", "irEvaluation"],
      },
      {
        text: "Low precision means the generator receives distracting evidence even when recall is perfect. This can increase tokens, latency, conflicting claims, and the chance that the answer cites the wrong passage.",
        citations: ["ragasPrecision", "azureEvaluation"],
      },
    ],
    mechanics: [
      { title: "Define relevance", copy: { text: "Use document IDs or human relevance labels tied to each golden question.", citations: ["irEvaluation"] } },
      { title: "Inspect retrieved items", copy: { text: "Judge which top-k results can actually help answer the question.", citations: ["ragasPrecision"] } },
      { title: "Measure noise", copy: { text: "Divide relevant retrieved items by all returned items, or use a rank-aware precision metric.", citations: ["ragasPrecision"] } },
    ],
    example: {
      title: "Precision@5",
      text: "Five passages are returned, but only two are relevant. Precision@5 = 2 / 5 = 0.40, even if those two cover every required fact and recall is 1.0.",
    },
    comparison: {
      title: "A useful diagnostic matrix",
      columns: ["Result", "Interpretation", "Likely next check"],
      rows: [
        ["High recall, low precision", "Evidence found with too much noise", "Reranking, filters, top-k"],
        ["Low recall, high precision", "Few results, mostly good", "Chunking, retriever coverage"],
        ["Both low", "Retrieval is broadly failing", "Parsing, corpus, embeddings, labels"],
      ],
    },
    productionNotes: [
      "Calculate precision at the same stage the generator consumes.",
      "Deduplicate repeated children or parents before scoring final context precision.",
      "Review label quality before tuning against surprising metric changes.",
    ],
    interviewAnswer: "Precision measures how much of the retrieved set is relevant. It exposes noisy context that recall alone hides, so I use recall and precision together and inspect them at the candidate, reranked, and final-context stages.",
    related: ["recall", "reranking", "ranking-metrics", "golden-evaluation"],
    sourceIds: ["ragasPrecision", "irEvaluation", "azureEvaluation"],
  },
  {
    id: "ranking-metrics",
    term: "Hit rate and MRR",
    eyebrow: "Rank-aware evaluation",
    category: "Evaluation & trust",
    level: "Intermediate",
    readTime: "8 min",
    definition: "Metrics that ask whether a relevant result appeared and how early the first relevant result was ranked.",
    overview: [
      {
        text: "Hit rate is binary per question: at least one relevant item appears within top-k or it does not. Mean Reciprocal Rank gives each question 1 / rank of its first relevant result, then averages across questions.",
        citations: ["irEvaluation"],
      },
      {
        text: "Neither metric measures complete evidence coverage. A query can have Hit@5 = 1 and a strong MRR while still missing other passages required for a complete answer, so recall remains necessary.",
        citations: ["irEvaluation", "ragasRecall"],
      },
    ],
    mechanics: [
      { title: "Label relevance", copy: { text: "Record which result IDs count as relevant for every question.", citations: ["irEvaluation"] } },
      { title: "Find the first hit", copy: { text: "Locate the rank of the earliest relevant item inside the chosen cutoff.", citations: ["irEvaluation"] } },
      { title: "Aggregate", copy: { text: "Average binary hits for hit rate and reciprocal first-hit ranks for MRR.", citations: ["irEvaluation"] } },
    ],
    example: {
      title: "Three queries",
      text: "First relevant ranks are 1, 2, and no hit. Hit@5 = 2/3. MRR@5 = (1 + 1/2 + 0) / 3 = 0.50.",
    },
    comparison: {
      title: "Which metric answers which question?",
      columns: ["Metric", "Rewards", "Does not prove"],
      rows: [
        ["Hit rate", "At least one useful result", "Good ordering or full coverage"],
        ["MRR", "First useful result near the top", "All required evidence found"],
        ["Recall", "Coverage of expected evidence", "Low noise"],
      ],
    },
    productionNotes: [
      "Define behavior for no-hit queries explicitly as reciprocal rank zero.",
      "Include the cutoff in metric names and reports.",
      "Use MRR for first-answer workflows; use broader ranked metrics when multiple results matter.",
    ],
    interviewAnswer: "Hit rate measures whether top-k contains any relevant result. MRR additionally rewards placing the first relevant result early. They are useful ranking signals, but neither replaces recall when an answer needs several evidence pieces.",
    related: ["recall", "precision", "rrf", "golden-evaluation"],
    sourceIds: ["irEvaluation", "ragasRecall"],
  },
  {
    id: "faithfulness",
    term: "Faithfulness",
    eyebrow: "Answer grounding",
    category: "Evaluation & trust",
    level: "Intermediate",
    readTime: "7 min",
    definition: "The degree to which claims in the generated answer are supported by the retrieved context.",
    overview: [
      {
        text: "Faithfulness evaluates the generator, given the evidence it received. A common method extracts claims from the answer and checks whether each claim can be inferred from the retrieved context.",
        citations: ["ragasFaithfulness", "ragasMetrics"],
      },
      {
        text: "Faithfulness is not the same as correctness. An answer can faithfully repeat an outdated source and still be wrong in the real world, or be factually correct from model memory but unsupported by the supplied evidence.",
        citations: ["ragasMetrics", "azureEvaluation"],
      },
    ],
    mechanics: [
      { title: "Extract claims", copy: { text: "Break the generated answer into factual statements that can be checked.", citations: ["ragasFaithfulness"] } },
      { title: "Check support", copy: { text: "Determine whether each claim follows from the contexts provided to the model.", citations: ["ragasFaithfulness"] } },
      { title: "Score and inspect", copy: { text: "Calculate the supported-claim fraction and preserve reasons for human error analysis.", citations: ["ragasMetrics"] } },
    ],
    example: {
      title: "A citation is not enough",
      text: "The answer says cancellation is allowed for 60 days and cites a policy that says 30 days. The citation exists, but the claim is unfaithful because the source does not support it.",
    },
    comparison: {
      title: "Answer-quality dimensions",
      columns: ["Metric", "Compared with", "Question"],
      rows: [
        ["Faithfulness", "Retrieved context", "Are claims supported?"],
        ["Correctness", "Reference answer or facts", "Is the answer right?"],
        ["Relevance", "User question", "Does it address the request?"],
      ],
    },
    productionNotes: [
      "Validate cited source IDs deterministically before using an LLM-based faithfulness judge.",
      "Review evaluator disagreements; judge models are not ground truth.",
      "Track faithfulness separately for answerable and deliberately unanswerable cases.",
    ],
    interviewAnswer: "Faithfulness measures whether answer claims are supported by the retrieved context. It differs from correctness and relevance, so I evaluate all three and also validate that every citation points to evidence actually supplied to the model.",
    related: ["golden-evaluation", "abstention", "recall", "precision"],
    sourceIds: ["ragasFaithfulness", "ragasMetrics", "azureEvaluation"],
  },
  {
    id: "abstention",
    term: "Abstention",
    eyebrow: "Knowing when not to answer",
    category: "Evaluation & trust",
    level: "Intermediate",
    readTime: "7 min",
    definition: "Deliberately refusing or escalating a question when evidence is absent, weak, conflicting, unauthorized, or unsafe.",
    overview: [
      {
        text: "A grounded system needs a valid no-answer outcome. If retrieval returns no admissible evidence, the model should not fill the gap from memory and present it as document-backed knowledge.",
        citations: ["nistGenAi", "azureEvaluation"],
      },
      {
        text: "Abstention is a classification decision with two error types: answering when it should refuse and refusing when it could answer. Thresholds therefore need answerable and unanswerable golden questions.",
        citations: ["azureEvaluation", "nistGenAi"],
      },
    ],
    mechanics: [
      { title: "Detect weak evidence", copy: { text: "Use deterministic conditions and calibrated retrieval or rerank signals rather than prompt wording alone.", citations: ["azureEvaluation"] } },
      { title: "Return a clear outcome", copy: { text: "State that the available sources do not support an answer and avoid invented citations.", citations: ["nistGenAi"] } },
      { title: "Offer recovery", copy: { text: "Request clarification, suggest an approved source, or route the case for human review.", citations: ["nistGenAi"] } },
    ],
    example: {
      title: "Out-of-corpus question",
      text: "The corpus contains product manuals but no pricing policy. When asked for next year’s price, the system says the indexed sources do not contain that information and directs the user to sales.",
    },
    comparison: {
      title: "Abstention outcomes",
      columns: ["Evidence state", "Desired behavior", "Failure if wrong"],
      rows: [
        ["Strong and supported", "Answer with citations", "False refusal"],
        ["Missing or weak", "Abstain", "Unsupported answer"],
        ["Conflicting", "Explain or escalate", "Arbitrary source choice"],
      ],
    },
    productionNotes: [
      "Do not use one uncalibrated similarity score as universal confidence.",
      "Measure abstention accuracy and the two error directions separately.",
      "Log the reason code: no results, low relevance, conflict, permission, or safety.",
    ],
    interviewAnswer: "Abstention is the explicit no-answer path when evidence is missing, weak, conflicting, or unsafe. I calibrate it with both answerable and unanswerable golden cases and return a clear reason plus a recovery path.",
    related: ["faithfulness", "golden-evaluation", "metadata-filtering", "reranking"],
    sourceIds: ["nistGenAi", "azureEvaluation"],
  },
  {
    id: "golden-evaluation",
    term: "Golden evaluation set",
    eyebrow: "Regression quality gate",
    category: "Evaluation & trust",
    level: "Intermediate",
    readTime: "9 min",
    definition: "A reviewed collection of representative questions, expected evidence, reference answers, and expected refusal behavior used to detect regressions.",
    overview: [
      {
        text: "A golden set turns “the answers look good” into a repeatable test. Each case should identify the question, whether it is answerable, expected source IDs, a reference answer or required claims, and relevant categories such as product or difficulty.",
        citations: ["azureEvaluation", "ragasMetrics"],
      },
      {
        text: "The set must represent real traffic and hard boundaries: paraphrases, exact identifiers, multi-hop questions, conflicting documents, missing answers, permissions, and changed versions. One aggregate score can otherwise hide a serious slice failure.",
        citations: ["azureEvaluation", "nistGenAi"],
      },
    ],
    mechanics: [
      { title: "Author cases", copy: { text: "Start with reviewed real questions and deliberately add difficult and unanswerable variants.", citations: ["azureEvaluation"] } },
      { title: "Score components", copy: { text: "Evaluate retrieval, ranking, answer grounding, correctness, citations, and abstention separately.", citations: ["ragasMetrics"] } },
      { title: "Gate changes", copy: { text: "Run the fixed set for changes to parsing, chunking, embeddings, indexes, ranking, prompts, and models.", citations: ["azureEvaluation"] } },
    ],
    example: {
      title: "One useful JSONL case",
      text: "A case records the question, answerable=true, expected_document_ids=[policy-v3], a reference answer, required citation IDs, tags=[policy, paraphrase], and the approved corpus revision.",
    },
    comparison: {
      title: "Evaluation layers",
      columns: ["Layer", "Example metrics", "Typical failure found"],
      rows: [
        ["Retrieval", "Recall, precision, hit rate, MRR", "Missing or noisy evidence"],
        ["Generation", "Faithfulness, correctness, relevance", "Unsupported or incomplete answer"],
        ["Safety", "Abstention, citation validity, leakage tests", "Answering when it should not"],
        ["Operations", "P95 latency, tokens, cost, failure rate", "Quality works but service does not"],
      ],
    },
    productionNotes: [
      "Version the dataset and record the corpus revision used for every run.",
      "Keep a human-reviewed core set; synthetic cases can extend it but should not silently replace it.",
      "Use hard failure gates for tenant leakage, fabricated citations, and critical unanswerable cases.",
    ],
    interviewAnswer: "A golden evaluation set contains representative questions, expected source IDs, reference answers, and unanswerable cases. I run it on every retrieval, model, prompt, or ingestion change and gate releases on component metrics plus critical safety failures.",
    related: ["recall", "precision", "ranking-metrics", "faithfulness", "abstention"],
    sourceIds: ["azureEvaluation", "ragasMetrics", "nistGenAi"],
  },
];

export const glossaryCategories = [
  "All topics",
  "Foundations",
  "Ingestion & indexing",
  "Retrieval",
  "Ranking & context",
  "Evaluation & trust",
] as const;
