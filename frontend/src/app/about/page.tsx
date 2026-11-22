import { Info, ShieldCheck, Bot, AlertTriangle, Sparkles, FlaskConical } from "lucide-react";

export const metadata = { title: "About · Feynlist" };

const card: React.CSSProperties = { padding: "20px", display: "flex", flexDirection: "column", gap: "8px" };
const head: React.CSSProperties = { display: "flex", gap: "10px", alignItems: "center", fontSize: "14px", fontWeight: 600 };
const body: React.CSSProperties = { fontSize: "13px", lineHeight: 1.6, color: "var(--text-muted)" };

export default function AboutPage() {
  return (
    <div style={{ padding: "32px 16px", maxWidth: "680px", margin: "0 auto" }}>
      <div style={{ marginBottom: "24px" }}>
        <div style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "4px", textTransform: "uppercase", letterSpacing: "0.1em" }}>
          Feynlist
        </div>
        <h1 style={{ fontSize: "28px", fontWeight: 700 }} className="gradient-text">About</h1>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        <div className="glass" style={card}>
          <div style={head}><Info size={16} style={{ color: "var(--accent)" }} /> What this is</div>
          <p style={body}>
            Feynlist is an accountability-first planner. You plan your day in time blocks and mark each one:
            <strong> Start &amp; Sit</strong> (50% of its points), <strong>Complete</strong> (30%) and
            <strong> Be Attentive</strong> (20%, scaled by your focus rating). Discipline, Alertness, Aura and
            your consistency streak come from those marks. Five AI coaches, called The Council, comment on what
            actually happened.
          </p>
        </div>

        <div className="glass" style={card}>
          <div style={head}><Bot size={16} style={{ color: "#5eead4" }} /> How the Council uses your data</div>
          <p style={body}>
            When a coach replies, the server sends Google&apos;s Gemini API a short context: today&apos;s tasks and
            their status, today&apos;s metrics, the time of day, a few saved notes from earlier chats, and your
            message. The API key stays on the server. Live replies use a free Gemini tier, and Google may use
            free-tier content to improve its products, so please don&apos;t enter personal information.
          </p>
        </div>

        <div className="glass" style={card}>
          <div style={head}><Sparkles size={16} style={{ color: "#fbbf24" }} /> Live AI in this demo</div>
          <p style={body}>
            The Council is designed to run live: all five coaches, plus nudges when you miss or finish a task,
            at the end of the day and at check-ins. To stay on a free Gemini key, the public demo limits this:
          </p>
          <ul style={{ ...body, paddingLeft: "18px" }}>
            <li>Each browser session gets <strong>2 live replies</strong> (chat and demo controls count together).</li>
            <li>There is a daily cap for everyone, and a short pause if too many requests arrive in a minute.</li>
            <li>&quot;Council&quot; (all five at once) and automatic nudges always use <strong>sample replies</strong>,
              because all five at once would use five requests.</li>
            <li>No scheduled AI calls run in the demo.</li>
          </ul>
          <p style={body}>
            Everything else is shown as <strong>pre-written sample replies</strong>, always labelled
            &quot;Sample reply (pre-written, not live)&quot;. They are written in each coach&apos;s style and only
            mention your plan&apos;s real numbers. If the AI is unavailable, you get a sample with a short reason, never an error.
          </p>
        </div>

        <div className="glass" style={card}>
          <div style={head}><FlaskConical size={16} style={{ color: "var(--accent-2)" }} /> Sample data and your session</div>
          <p style={body}>
            In demo mode each browser gets its own private copy of the app, filled with sample data: about two weeks
            of made-up history. Nobody else sees what you do. It&apos;s stored in temporary storage on a free server, so it
            may reset when the server restarts. &quot;Reset demo&quot; on the dashboard starts you over at any time.
          </p>
        </div>

        <div className="glass" style={card}>
          <div style={head}><ShieldCheck size={16} style={{ color: "#34d399" }} /> What the numbers are (and aren&apos;t)</div>
          <p style={body}>
            The workload (&quot;burnout&quot;) signal is a simple rule-based heuristic over your recent metrics. It is
            not a medical or psychological assessment. Scores are self-reported by design: they reflect what you
            mark, not anything measured.
          </p>
        </div>

        <div className="glass" style={card}>
          <div style={head}><AlertTriangle size={16} style={{ color: "#fbbf24" }} /> Known limits</div>
          <p style={body}>
            The coaches only know what is in your plan and metrics. The persona replies have not yet been evaluated
            against a live model in a structured way (see the project&apos;s evals). The planner and stats work with or
            without live AI.
          </p>
        </div>
      </div>
    </div>
  );
}
