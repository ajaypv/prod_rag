import { useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BookMarked,
  CheckCircle2,
  Clock3,
  ExternalLink,
  GraduationCap,
} from "lucide-react";
import {
  glossaryEntries,
  glossarySources,
  type CitedCopy,
  type GlossaryEntry,
} from "../glossaryData";

function initialEntryId() {
  const hash = window.location.hash.replace("#glossary-", "");
  return glossaryEntries.some((entry) => entry.id === hash) ? hash : null;
}

function Citations({ entry, ids }: { entry: GlossaryEntry; ids: string[] }) {
  if (!ids.length) return null;

  return (
    <sup className="chapter-citations" aria-label="Citations">
      {ids.map((id) => {
        const sourceNumber = entry.sourceIds.indexOf(id) + 1;
        if (sourceNumber === 0) return null;
        return (
          <a key={id} href={`#glossary-source-${id}`} aria-label={`Go to source ${sourceNumber}`}>
            {sourceNumber}
          </a>
        );
      })}
    </sup>
  );
}

function CitedParagraph({ entry, copy }: { entry: GlossaryEntry; copy: CitedCopy }) {
  return (
    <p>
      {copy.text}
      <Citations entry={entry} ids={copy.citations} />
    </p>
  );
}

export function Glossary() {
  const [selectedId, setSelectedId] = useState(initialEntryId);
  const articleRef = useRef<HTMLElement>(null);

  const selectedEntry = glossaryEntries.find((entry) => entry.id === selectedId);
  const selectedIndex = selectedEntry ? glossaryEntries.findIndex((entry) => entry.id === selectedEntry.id) : -1;

  function selectEntry(id: string) {
    setSelectedId(id);
    window.history.replaceState(null, "", `#glossary-${id}`);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function closeEntry() {
    setSelectedId(null);
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function moveChapter(direction: -1 | 1) {
    if (!selectedEntry) return;
    const nextIndex = (selectedIndex + direction + glossaryEntries.length) % glossaryEntries.length;
    selectEntry(glossaryEntries[nextIndex].id);
  }

  if (!selectedEntry) {
    return (
      <div className="resource-page glossary-overview-page">
        <header className="resource-header">
          <span className="lesson-kicker">Quick reference</span>
          <h1>RAG glossary</h1>
          <p>Plain-language definitions for the terms used throughout the lessons. Select a term when you want the complete, source-backed chapter.</p>
        </header>

        <nav className="glossary-list" aria-label="RAG glossary terms">
          {glossaryEntries.map((entry, index) => (
            <button key={entry.id} type="button" onClick={() => selectEntry(entry.id)}>
              <span className="glossary-card-number">{String(index + 1).padStart(2, "0")}</span>
              <span className="glossary-card-copy">
                <strong>{entry.term}</strong>
                <span>{entry.definition}</span>
              </span>
              <ArrowRight size={16} aria-hidden="true" />
            </button>
          ))}
        </nav>
      </div>
    );
  }

  return (
    <div className="resource-page glossary-library glossary-detail-view">
      <div className="glossary-detail-toolbar">
        <button type="button" onClick={closeEntry}><ArrowLeft size={15} />Back to glossary</button>
        <span>{selectedEntry.category} · {selectedEntry.level}</span>
      </div>

      <article className="glossary-chapter" ref={articleRef} key={selectedEntry.id}>
          <div className="glossary-chapter-progress" aria-label={`Chapter ${selectedIndex + 1} of ${glossaryEntries.length}`}>
            <span style={{ width: `${((selectedIndex + 1) / glossaryEntries.length) * 100}%` }} />
          </div>

          <header className="chapter-title-page">
            <div className="chapter-running-head">
              <span>{selectedEntry.category}</span>
              <span>Chapter {String(selectedIndex + 1).padStart(2, "0")}</span>
            </div>
            <span className="chapter-eyebrow">{selectedEntry.eyebrow}</span>
            <h2>{selectedEntry.term}</h2>
            <p className="chapter-definition">{selectedEntry.definition}</p>
            <div className="chapter-meta">
              <span className={`level-${selectedEntry.level.toLocaleLowerCase()}`}><GraduationCap size={14} />{selectedEntry.level}</span>
              <span><Clock3 size={13} />{selectedEntry.readTime} read</span>
              <span><BookMarked size={13} />{selectedEntry.sourceIds.length} sources</span>
            </div>
          </header>

          <section className="chapter-section chapter-overview">
            <div className="chapter-section-label"><span>01</span><strong>What it means</strong></div>
            <div className="chapter-prose">
              {selectedEntry.overview.map((copy, index) => <CitedParagraph key={index} entry={selectedEntry} copy={copy} />)}
            </div>
          </section>

          <section className="chapter-section">
            <div className="chapter-section-label"><span>02</span><strong>How it works</strong></div>
            <ol className="chapter-mechanics">
              {selectedEntry.mechanics.map((step, index) => (
                <li key={step.title}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <div>
                    <h3>{step.title}</h3>
                    <CitedParagraph entry={selectedEntry} copy={step.copy} />
                  </div>
                </li>
              ))}
            </ol>
          </section>

          <aside className="chapter-example">
            <span>Worked example</span>
            <h3>{selectedEntry.example.title}</h3>
            <p>{selectedEntry.example.text}</p>
          </aside>

          {selectedEntry.comparison && (
            <section className="chapter-section chapter-comparison">
              <div className="chapter-section-label"><span>03</span><strong>{selectedEntry.comparison.title}</strong></div>
              <div className="chapter-table-scroll">
                <table>
                  <thead><tr>{selectedEntry.comparison.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
                  <tbody>
                    {selectedEntry.comparison.rows.map((row) => (
                      <tr key={row[0]}>{row.map((cell, index) => <td key={`${row[0]}-${index}`}>{cell}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <section className="chapter-section chapter-production">
            <div className="chapter-section-label"><span>04</span><strong>Production notebook</strong></div>
            <ul>
              {selectedEntry.productionNotes.map((note) => <li key={note}><CheckCircle2 size={16} /><span>{note}</span></li>)}
            </ul>
          </section>

          <aside className="chapter-interview-answer">
            <span>Say this in an interview</span>
            <blockquote>{selectedEntry.interviewAnswer}</blockquote>
          </aside>

          <section className="chapter-related">
            <div>
              <span>Continue reading</span>
              <h3>Related chapters</h3>
            </div>
            <div className="chapter-related-links">
              {selectedEntry.related.map((id) => {
                const relatedEntry = glossaryEntries.find((entry) => entry.id === id);
                if (!relatedEntry) return null;
                return (
                  <button key={id} type="button" onClick={() => selectEntry(id)}>
                    <span>{relatedEntry.category}</span>
                    <strong>{relatedEntry.term}</strong>
                    <ArrowRight size={14} />
                  </button>
                );
              })}
            </div>
          </section>

          <section className="chapter-sources" aria-labelledby="chapter-source-title">
            <div>
              <span>References</span>
              <h3 id="chapter-source-title">Sources for this chapter</h3>
              <p>Open the original research or documentation behind the explanation.</p>
            </div>
            <ol>
              {selectedEntry.sourceIds.map((sourceId) => {
                const source = glossarySources[sourceId];
                return (
                  <li key={sourceId} id={`glossary-source-${sourceId}`}>
                    <a href={source.url} target="_blank" rel="noreferrer">
                      <span><strong>{source.title}</strong><small>{source.publisher}</small></span>
                      <ExternalLink size={14} aria-hidden="true" />
                    </a>
                  </li>
                );
              })}
            </ol>
          </section>

          <nav className="chapter-pagination" aria-label="Glossary chapter navigation">
            <button type="button" onClick={() => moveChapter(-1)}>
              <ArrowLeft size={15} />
              <span><small>Previous</small><strong>{glossaryEntries[(selectedIndex - 1 + glossaryEntries.length) % glossaryEntries.length].term}</strong></span>
            </button>
            <button type="button" onClick={() => moveChapter(1)}>
              <span><small>Next</small><strong>{glossaryEntries[(selectedIndex + 1) % glossaryEntries.length].term}</strong></span>
              <ArrowRight size={15} />
            </button>
          </nav>
      </article>
    </div>
  );
}
