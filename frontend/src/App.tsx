import { useMemo, useState } from "react";
import { BookOpen, Check, ChevronRight, Home, Menu, MessageSquareText, X } from "lucide-react";
import { lessonGroups, lessons } from "./data";
import { Glossary } from "./components/Glossary";
import { InterviewPrep } from "./components/InterviewPrep";
import { LearningHome } from "./components/LearningHome";
import { LessonPage } from "./components/LessonPage";
import type { PageId } from "./types";

export function App() {
  const [page, setPage] = useState<PageId>("home");
  const [completed, setCompleted] = useState<Set<PageId>>(new Set());
  const [drawerOpen, setDrawerOpen] = useState(false);
  const lesson = lessons.find((item) => item.id === page);
  const progress = Math.round((completed.size / lessons.length) * 100);

  function navigate(next: PageId) {
    setPage(next);
    setDrawerOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function toggleComplete(id: PageId) {
    setCompleted((current) => {
      const next = new Set(current);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  const content = useMemo(() => {
    if (page === "home") return <LearningHome onNavigate={navigate} />;
    if (page === "interview") return <InterviewPrep />;
    if (page === "glossary") return <Glossary />;
    if (lesson) return <LessonPage lesson={lesson} onNavigate={navigate} completed={completed.has(lesson.id)} onComplete={() => toggleComplete(lesson.id)} />;
    return null;
  }, [page, lesson, completed]);

  return (
    <div className="learning-app">
      <aside className={`learning-sidebar${drawerOpen ? " open" : ""}`}>
        <div className="learning-brand"><button onClick={() => navigate("home")}><span className="brand-symbol">G</span><span><strong>Groundwork</strong><small>Learn RAG clearly</small></span></button><button className="drawer-close" onClick={() => setDrawerOpen(false)} aria-label="Close lessons"><X size={19} /></button></div>
        <div className="progress-block"><div><span>Your progress</span><strong>{completed.size} of {lessons.length} lessons</strong></div><div className="progress-track"><span style={{ width: `${progress}%` }} /></div></div>
        <nav className="lesson-nav" aria-label="RAG lessons">
          <button className={page === "home" ? "active home-link" : "home-link"} onClick={() => navigate("home")}><Home size={17} /><span>Start here</span></button>
          {lessonGroups.map((group) => <div className="nav-group" key={group}><span>{group}</span>{lessons.filter((item) => item.group === group).map((item) => <button className={page === item.id ? "active" : ""} key={item.id} onClick={() => navigate(item.id)}><i className={completed.has(item.id) ? "done" : ""}>{completed.has(item.id) ? <Check size={12} /> : item.number}</i><span>{item.shortTitle}</span>{page === item.id && <ChevronRight size={14} />}</button>)}</div>)}
          <div className="nav-group resources"><span>Interview preparation</span><button className={page === "interview" ? "active" : ""} onClick={() => navigate("interview")}><MessageSquareText size={16} /><span>Mock interview</span></button><button className={page === "glossary" ? "active" : ""} onClick={() => navigate("glossary")}><BookOpen size={16} /><span>RAG glossary</span></button></div>
        </nav>
      </aside>
      {drawerOpen && <button className="drawer-backdrop" onClick={() => setDrawerOpen(false)} aria-label="Close lessons" />}
      <div className="learning-workspace">
        <header className="mobile-header"><button onClick={() => setDrawerOpen(true)} aria-label="Open lessons"><Menu size={20} /></button><span><strong>Groundwork</strong><small>{lesson?.shortTitle ?? (page === "home" ? "Start here" : page === "interview" ? "Interview preparation" : "Glossary")}</small></span><span className="mobile-progress">{progress}%</span></header>
        <main>{content}</main>
      </div>
    </div>
  );
}
