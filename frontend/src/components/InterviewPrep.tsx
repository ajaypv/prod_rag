import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useInView, useReducedMotion } from "motion/react";
import { Copy, Eye, EyeOff, MessageSquareText, RotateCcw, Sparkles } from "lucide-react";
import { interviewQuestions } from "../data";
import type { InterviewQuestion } from "../types";

type AnswerDepth = "quick" | "detailed";
type InterviewMode = "watch" | "practice";

interface ConversationExchangeProps {
  item: InterviewQuestion;
  index: number;
  detail: AnswerDepth;
  mode: InterviewMode;
  revealed: boolean;
  copied: boolean;
  onActive: (index: number) => void;
  onReveal: (index: number) => void;
  onCopy: (index: number, answer: string) => void;
}

function ConversationExchange({ item, index, detail, mode, revealed, copied, onActive, onReveal, onCopy }: ConversationExchangeProps) {
  const exchangeRef = useRef<HTMLElement>(null);
  const inView = useInView(exchangeRef, { amount: 0.42, margin: "-8% 0px -24% 0px" });
  const reducedMotion = useReducedMotion();
  const answer = detail === "quick" ? item.quick : item.detailed;
  const showCandidate = mode === "watch" || revealed;
  const enter = reducedMotion ? { duration: 0 } : { type: "spring" as const, stiffness: 105, damping: 18 };

  useEffect(() => {
    if (inView) onActive(index);
  }, [inView, index, onActive]);

  return (
    <article ref={exchangeRef} className={inView ? "conversation-exchange active" : "conversation-exchange"}>
      <motion.div className="conversation-number" initial={false} animate={{ opacity: inView ? 1 : 0.38 }}>
        <span>Conversation {String(index + 1).padStart(2, "0")}</span><span>{item.category}</span>
      </motion.div>

      <motion.div
        className="speaker interviewer"
        initial={reducedMotion ? false : { opacity: 0, x: -46, y: 12 }}
        animate={inView ? { opacity: 1, x: 0, y: 0 } : { opacity: 0.18, x: reducedMotion ? 0 : -28, y: 8 }}
        transition={enter}
      >
        <div className="speaker-identity"><span>I</span><div><strong>Interviewer</strong><small>Core question</small></div></div>
        <blockquote>{item.question}</blockquote>
      </motion.div>

      <motion.div
        className="speaker candidate"
        initial={reducedMotion ? false : { opacity: 0, x: 50, y: 18 }}
        animate={inView ? { opacity: 1, x: 0, y: 0 } : { opacity: 0.12, x: reducedMotion ? 0 : 30, y: 10 }}
        transition={{ ...enter, delay: reducedMotion ? 0 : 0.24 }}
      >
        <div className="speaker-identity"><span>C</span><div><strong>Candidate</strong><small>{detail === "quick" ? "30-second response" : "Technical response"}</small></div></div>

        <AnimatePresence mode="wait" initial={false}>
          {!showCandidate ? (
            <motion.div key="practice" className="practice-prompt" initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.97 }}>
              <span><EyeOff size={16} />Your turn</span>
              <strong>Answer aloud before you look.</strong>
              <p>Define it, explain the flow, and mention one trade-off.</p>
              <button onClick={() => onReveal(index)}><Eye size={15} />Reveal candidate response</button>
            </motion.div>
          ) : (
            <motion.div key="answer" className="candidate-response-wrap" initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: reducedMotion ? 0 : 0.36 }}>
              {inView && !reducedMotion && <motion.div className="candidate-typing" initial={{ opacity: 0 }} animate={{ opacity: [0, 1, 1, 0] }} transition={{ duration: 0.8, times: [0, 0.12, 0.72, 1] }} aria-hidden="true"><i /><i /><i /></motion.div>}
              <motion.div className="candidate-response" initial={reducedMotion ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: reducedMotion ? 0 : 0.62, duration: 0.3 }}>
                <p>{answer}</p>
                <div className="response-actions">
                  <div className="inline-citations" aria-label="Sources">{item.sources.map((source, sourceIndex) => <a key={source.url} href={source.url} target="_blank" rel="noreferrer" title={source.label}>[{sourceIndex + 1}]</a>)}</div>
                  <button onClick={() => onCopy(index, answer)}><Copy size={14} />{copied ? "Copied" : "Copy"}</button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      <AnimatePresence initial={false}>
        {detail === "detailed" && showCandidate && <>
          <motion.div className="speaker interviewer follow-up-turn" initial={{ opacity: 0, x: reducedMotion ? 0 : -30 }} animate={{ opacity: inView ? 1 : 0.18, x: 0 }} exit={{ opacity: 0 }} transition={{ ...enter, delay: reducedMotion ? 0 : 0.85 }}>
            <div className="speaker-identity"><span>I</span><div><strong>Interviewer</strong><small>Follow-up</small></div></div>
            <blockquote>{item.followUp}</blockquote>
          </motion.div>
          <motion.div className="speaker candidate follow-up-turn" initial={{ opacity: 0, x: reducedMotion ? 0 : 30 }} animate={{ opacity: inView ? 1 : 0.12, x: 0 }} exit={{ opacity: 0 }} transition={{ ...enter, delay: reducedMotion ? 0 : 1.05 }}>
            <div className="speaker-identity"><span>C</span><div><strong>Candidate</strong><small>Trade-off to mention</small></div></div>
            <div className="candidate-response"><p>{item.tradeoff}</p></div>
          </motion.div>
        </>}
      </AnimatePresence>
    </article>
  );
}

export function InterviewPrep() {
  const [detail, setDetail] = useState<AnswerDepth>("quick");
  const [mode, setMode] = useState<InterviewMode>("watch");
  const [copied, setCopied] = useState<number | null>(null);
  const [active, setActive] = useState(0);
  const [revealed, setRevealed] = useState<Set<number>>(() => new Set());

  async function copyAnswer(index: number, answer: string) {
    await navigator.clipboard.writeText(answer);
    setCopied(index);
    window.setTimeout(() => setCopied(null), 1500);
  }

  function changeMode(nextMode: InterviewMode) {
    setMode(nextMode);
    if (nextMode === "practice") setRevealed(new Set());
  }

  function reveal(index: number) {
    setRevealed((current) => new Set(current).add(index));
  }

  const progress = ((active + 1) / interviewQuestions.length) * 100;

  return (
    <div className="resource-page interview-page">
      <header className="resource-header">
        <span className="lesson-kicker">Interview preparation</span>
        <h1>Step into a real RAG interview.</h1>
        <p>Scroll through the interview and watch each message enter the conversation. Use practice mode when you are ready to answer before seeing the candidate’s response.</p>
      </header>

      <div className="interview-toolbar">
        <div>
          <span>Answer depth</span>
          <div className="answer-level" aria-label="Answer depth">
            <button className={detail === "quick" ? "active" : ""} onClick={() => setDetail("quick")}>Concise</button>
            <button className={detail === "detailed" ? "active" : ""} onClick={() => setDetail("detailed")}>Deep dive</button>
          </div>
        </div>
        <div>
          <span>Experience</span>
          <div className="answer-level" aria-label="Interview experience">
            <button className={mode === "watch" ? "active" : ""} onClick={() => changeMode("watch")}><Sparkles size={13} />Watch responses</button>
            <button className={mode === "practice" ? "active" : ""} onClick={() => changeMode("practice")}><EyeOff size={13} />Practice first</button>
          </div>
        </div>
      </div>

      <aside className="interview-session-bar" aria-live="polite">
        <div className="session-status"><span>Live interview</span><strong>Question {active + 1} of {interviewQuestions.length}</strong></div>
        <p>{interviewQuestions[active].question}</p>
        <div className="session-progress" aria-hidden="true"><motion.span animate={{ width: `${progress}%` }} transition={{ type: "spring", stiffness: 90, damping: 20 }} /></div>
        {mode === "practice" && <button onClick={() => setRevealed(new Set())}><RotateCcw size={13} />Reset answers</button>}
      </aside>

      <section className="interview-conversation" aria-label="RAG interview conversation">
        {interviewQuestions.map((item, index) => <ConversationExchange
          key={item.question}
          item={item}
          index={index}
          detail={detail}
          mode={mode}
          revealed={revealed.has(index)}
          copied={copied === index}
          onActive={setActive}
          onReveal={reveal}
          onCopy={copyAnswer}
        />)}
      </section>

      <aside className="interview-advice"><MessageSquareText size={21} /><div><strong>A useful speaking pattern</strong><p>Define the concept first. Explain the flow in simple words. Add one implementation detail, then finish with a trade-off. That structure sounds experienced without becoming difficult to follow.</p></div></aside>
    </div>
  );
}
