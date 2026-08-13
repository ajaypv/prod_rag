import { ArrowRight, CheckCircle2 } from "lucide-react";
import { lessons } from "../data";
import type { PageId } from "../types";
import { HeroRagPlayground } from "./HeroRagPlayground";

export function LearningHome({ onNavigate }: { onNavigate: (page: PageId) => void }) {
  return (
    <div className="home-page">
      <HeroRagPlayground onNavigate={onNavigate} />

      <section className="three-ideas" aria-labelledby="three-ideas-title">
        <div className="section-intro"><span>Start with one idea</span><h2 id="three-ideas-title">RAG does three things</h2><p>You do not need to understand vectors or models yet.</p></div>
        <div className="idea-grid">
          <article><span>01</span><h3>Find</h3><p>Search the available knowledge for passages related to the question.</p></article>
          <article><span>02</span><h3>Select</h3><p>Keep the strongest evidence and remove distracting information.</p></article>
          <article><span>03</span><h3>Answer</h3><p>Give that evidence to the model and require a supported response.</p></article>
        </div>
      </section>

      <section className="course-overview" aria-labelledby="course-title">
        <div className="section-intro"><span>Your learning path</span><h2 id="course-title">From first principles to production</h2><p>Each lesson introduces one concept, one visual, and one interview-ready takeaway.</p></div>
        <div className="course-list">
          {lessons.map((lesson) => (
            <button key={lesson.id} onClick={() => onNavigate(lesson.id)}>
              <span className="course-number">{String(lesson.number).padStart(2, "0")}</span>
              <span className="course-copy"><strong>{lesson.title}</strong><small>{lesson.objective}</small></span>
              <span className="course-time">{lesson.duration}</span><ArrowRight size={17} />
            </button>
          ))}
        </div>
      </section>

      <section className="home-interview-callout">
        <div><span>Interview mode</span><h2>Learn the concept. Then practise saying it.</h2><p>Every lesson includes a concise interview answer, a likely follow-up, and the trade-off interviewers expect you to understand.</p></div>
        <ul><li><CheckCircle2 size={16} />30-second answers</li><li><CheckCircle2 size={16} />Technical follow-ups</li><li><CheckCircle2 size={16} />Real trade-offs</li></ul>
        <button onClick={() => onNavigate("interview")}>Open interview preparation <ArrowRight size={16} /></button>
      </section>
    </div>
  );
}
