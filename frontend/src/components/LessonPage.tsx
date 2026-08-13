import { useState } from "react";
import { ArrowLeft, ArrowRight, ChevronDown, Copy, Lightbulb, MessageSquareQuote } from "lucide-react";
import { lessons } from "../data";
import type { Lesson, PageId } from "../types";
import { ConceptVisual } from "./ConceptVisual";

export function LessonPage({ lesson, onNavigate, completed, onComplete }: { lesson: Lesson; onNavigate: (page: PageId) => void; completed: boolean; onComplete: () => void }) {
  const [technicalOpen, setTechnicalOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const index = lessons.findIndex((item) => item.id === lesson.id);
  const previous = index > 0 ? lessons[index - 1] : null;
  const next = index < lessons.length - 1 ? lessons[index + 1] : null;

  async function copyAnswer() {
    await navigator.clipboard.writeText(lesson.interview);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  return (
    <article className="lesson-page">
      <header className="lesson-header">
        <span className="lesson-kicker">Lesson {lesson.number} of {lessons.length} · {lesson.duration}</span>
        <h1>{lesson.title}</h1>
        <p>{lesson.objective}</p>
      </header>

      <ConceptVisual variant={lesson.visual} caption={lesson.visualCaption} />

      <section className="lesson-section opening-explanation">
        <span className="section-label">In plain language</span>
        <p className="lead-explanation">{lesson.plain}</p>
        <aside className="analogy"><Lightbulb size={20} /><div><strong>Think of it this way</strong><p>{lesson.analogy}</p></div></aside>
      </section>

      <section className="lesson-section">
        <span className="section-label">Step by step</span>
        <h2>What happens here?</h2>
        <div className="lesson-steps">
          {lesson.steps.map((step, stepIndex) => <div key={step.title}><span>{stepIndex + 1}</span><div><h3>{step.title}</h3><p>{step.text}</p></div></div>)}
        </div>
      </section>

      <section className="technical-disclosure">
        <button onClick={() => setTechnicalOpen((value) => !value)} aria-expanded={technicalOpen}>
          <span><small>Optional</small><strong>Show the technical explanation</strong></span><ChevronDown size={19} />
        </button>
        {technicalOpen && <div><p>{lesson.technical}</p><aside><strong>Important trade-off</strong><span>{lesson.tradeoff}</span></aside></div>}
      </section>

      <section className="interview-takeaway">
        <div className="takeaway-heading"><MessageSquareQuote size={22} /><div><span>Interview takeaway</span><h2>Your 30-second answer</h2></div></div>
        <blockquote>{lesson.interview}</blockquote>
        <div className="inline-citations" aria-label="Sources for this answer">{lesson.sources.map((source, sourceIndex) => <a key={source.url} href={source.url} target="_blank" rel="noreferrer" title={source.label}>[{sourceIndex + 1}]</a>)}</div>
        <div className="takeaway-footer"><p><strong>Likely follow-up:</strong> {lesson.followUp}</p><button onClick={copyAnswer}><Copy size={14} />{copied ? "Copied" : "Copy answer"}</button></div>
      </section>

      <aside className="lesson-sources">
        <span className="section-label">Sources and further reading</span>
        <ol>{lesson.sources.map((source) => <li key={source.url}><a href={source.url} target="_blank" rel="noreferrer">{source.label}</a></li>)}</ol>
      </aside>

      <footer className="lesson-navigation">
        {previous ? <button onClick={() => onNavigate(previous.id)}><ArrowLeft size={16} /><span><small>Previous</small>{previous.shortTitle}</span></button> : <button onClick={() => onNavigate("home")}><ArrowLeft size={16} /><span><small>Previous</small>Start here</span></button>}
        <button className={completed ? "complete-action completed" : "complete-action"} onClick={onComplete}>{completed ? "Lesson completed" : "Mark as complete"}</button>
        {next ? <button className="next-lesson" onClick={() => onNavigate(next.id)}><span><small>Next</small>{next.shortTitle}</span><ArrowRight size={16} /></button> : <button className="next-lesson" onClick={() => onNavigate("interview")}><span><small>Next</small>Interview preparation</span><ArrowRight size={16} /></button>}
      </footer>
    </article>
  );
}
