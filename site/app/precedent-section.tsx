'use client';

import { AlertTriangle, ArrowUpRight, Ban } from 'lucide-react';
import data from './precedent-data.json';
import './precedent.css';

type Row = {
  path: string; true: number; naive: number | null; matched: number | null;
  naive_error: number | null; matched_error: number | null;
  winner: string | null; sign_inverted: boolean;
};
type Path = {
  label: string; n: number; share: number; crude_admission_rate: number;
  adjusted_admission_rate: number; median_cost: number; note: string;
};

const pretty = (s: string) => s.replace(/_/g, ' ');
const pct = (n: number) => (n * 100).toFixed(0) + '%';
const usd = (n: number) => '$' + Math.round(n).toLocaleString();

export function PrecedentSection() {
  const rows = data.validation as Row[];
  const example = (data.examples as any[])[0];
  const refusal = data.refusal as any;
  const inverted = rows.find((r) => r.sign_inverted);
  const lost = rows.find((r) => r.winner === 'naive');

  return (
    <section className="section wrap" id="precedent">
      <div className="section-heading">
        <span className="section-number">05 / PRECEDENT</span>
        <div>
          <h2>What happened to<br />patients like this one?</h2>
          <p className="section-deck">
            The question doctors ask each other in hallways. A full-risk plan is the only party
            positioned to answer it.
          </p>
        </div>
      </div>

      <div className="pr-premise">
        <div>
          <p className="lead">
            Trials exclude the multi-morbid elderly, because they confound endpoints.
          </p>
          <p>
            So a large share of the guidance governing Medicare Advantage care was established on
            populations that exclude many Medicare Advantage members. A member with kidney disease,
            heart failure, diabetes and eight medications is not well represented in that evidence base.
          </p>
        </div>
        <div>
          <p>
            A health system&rsquo;s record stops at its own walls. It holds the referral that was
            written, not the specialist who was seen; the prescription, not the fill; and it does not
            hold what the episode cost.
          </p>
          <p>
            A plan&rsquo;s record follows the member. For this particular question that is the more
            complete view &mdash; which is why the idea below is worth testing at a payer rather than
            anywhere else.
          </p>
        </div>
      </div>

      <div className="pr-headline">
        <div className="pr-headline-top">
          <span className="eyebrow">THE RESULT · SYNTHETIC POPULATION, n={data.population_size.toLocaleString()}</span>
          <h3>Naive analysis says a protective treatment is harmful.</h3>
          <p>
            The population below was generated with a <strong>known true effect</strong> per care
            path, and with the confounding real data has: sicker members are referred far more often.
            The question is whether matched cohorts recover the truth that a crude comparison misses.
          </p>
        </div>
        <table className="pr-table">
          <thead>
            <tr>
              <th>Care path</th><th>True effect</th><th>Naive comparison</th>
              <th>Matched cohorts</th><th>Closer</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.path}>
                <td>
                  {pretty(r.path)}
                  <span className="pr-path-note">
                    {r.true <= 0.80 ? 'strong true benefit' : r.true < 0.98 ? 'mild true benefit' : r.true > 1.05 ? 'genuinely harmful' : 'no real effect'}
                  </span>
                </td>
                <td>{r.true.toFixed(2)}</td>
                <td className={r.sign_inverted ? 'pr-bad' : undefined}>
                  {r.naive?.toFixed(2)}
                  {r.sign_inverted && (
                    <span className="pr-flag"><AlertTriangle size={11} /> WRONG DIRECTION</span>
                  )}
                </td>
                <td className={r.winner === 'matched' ? 'pr-good' : undefined}>{r.matched?.toFixed(2)}</td>
                <td><span className={'pr-win ' + r.winner}>{r.winner}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="assumptions">
        {inverted && (
          <>
            <strong>Read the first row.</strong> A path with a true effect of {inverted.true.toFixed(2)} &mdash;
            meaningfully protective &mdash; measures at {inverted.naive?.toFixed(2)} under naive comparison,
            because the members who received it were sicker to begin with. Anyone reading the crude
            numbers concludes it causes harm. Matched cohorts return {inverted.matched?.toFixed(2)}.{' '}
          </>
        )}
        The third row matters as much: a path with <strong>no real effect</strong> is correctly
        returned as no effect. {lost && (
          <>
            <strong> And matching is not uniformly better.</strong> On {pretty(lost.path)} &mdash; the
            weakest true effect &mdash; it overstates the benefit and does worse than the naive
            comparison. That is a real limitation of the method as built, not a rounding artefact.
          </>
        )}
      </p>

      <div className="pr-readout">
        <div className="pr-card">
          <span className="eyebrow">A REPORTABLE MEMBER</span>
          <div className="pr-cohort">{example.cohort_size}<span>similar members found · {example.confidence}</span></div>
          <div className="pr-paths">
            {(example.paths as Path[]).map((p) => (
              <div className="pr-path" key={p.label}>
                <div className="pr-path-head">
                  <span>{pretty(p.label)}</span>
                  <em>n={p.n} · {pct(p.share)} of cohort</em>
                </div>
                <div className="pr-rates">
                  <span>Crude<strong>{pct(p.crude_admission_rate)}</strong></span>
                  <span>Adjusted<strong>{pct(p.adjusted_admission_rate)}</strong></span>
                  <span>Median cost<strong>{usd(p.median_cost)}</strong></span>
                </div>
                {p.note && <p className="pr-disagree">{p.note}</p>}
              </div>
            ))}
          </div>
          <div className="pr-caveats">
            <ul>{(example.caveats as string[]).map((c) => <li key={c}>{c}</li>)}</ul>
          </div>
        </div>

        <div className="pr-card pr-refusal">
          <span className="eyebrow">A RARE MEMBER &mdash; THE REFUSAL</span>
          <div className="pr-cohort">{refusal.cohort_size}<span>similar members · minimum is {data.min_cohort_size}</span></div>
          <h4><Ban size={15} style={{ verticalAlign: '-2px', marginRight: 8 }} />No result shown</h4>
          <p>{refusal.reason}. A distribution computed over this few members would be noise wearing the costume of evidence.</p>
          <p>
            This behaviour is the point rather than a gap. A tool that answers every question is a
            tool that cannot be trusted on any of them. {data.cohorts_reportable} of{' '}
            {data.cohorts_sampled} sampled members had a cohort large enough to report; the rest
            returned nothing.
          </p>
          <div className="pr-caveats">
            <ul>
              <li><strong>Matched on:</strong> {(example.matched_on as string[]).join(', ')}.</li>
              <li><strong>Adjusted for:</strong> {(example.adjusted_for as string[]).join(', ')}.</li>
              <li>Severity is deliberately excluded from the match vector, so it remains available as an adjustment stratum rather than being absorbed into the matching.</li>
            </ul>
          </div>
        </div>
      </div>

      <div className="pr-prior">
        <span className="eyebrow">PRIOR ART &mdash; THIS IS NOT A NEW IDEA</span>
        <p>
          Aggregate patient data at the point of care was proposed as the &ldquo;Green Button&rdquo; by{' '}
          <a className="source-link" href="https://www.healthaffairs.org/doi/10.1377/hlthaff.2014.0099" target="_blank" rel="noreferrer">
            Shah et al., Health Affairs, 2014 <ArrowUpRight size={12} />
          </a>{' '}
          and commercialised for health systems by Atropos Health. What I could not find is a
          payer-side implementation: one that follows the member beyond any single institution,
          includes cost, and is <strong>precomputed for point-of-care latency</strong> rather than run
          as a consult. The published barrier to these tools is that cohort generation takes weeks,
          which is untenable in a fifteen-minute visit. Precomputation trades freshness for latency,
          and freshness is not the binding constraint for this question.{' '}
          <strong>If a payer-side implementation exists, I would rather use it than rebuild it.</strong>
        </p>
      </div>

      <div className="pr-prior" style={{ borderLeftColor: 'var(--against)' }}>
        <span className="eyebrow" style={{ color: 'var(--against)' }}>WHAT THIS DOES NOT SHOW</span>
        <p>
          {(data.limitations as string[]).join(' ')}
        </p>
      </div>
    </section>
  );
}
