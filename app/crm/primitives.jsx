/* primitives.jsx — HubSpot-style CRM controls + tweaks panel */

/* ─── Core form components ─── */

function Field({ label, help, children }) {
  return (
    <div className="crmField">
      <label className="crmLabel">
        {label}
        {help && <span className="help" title={help}>?</span>}
        {children}
      </label>
    </div>
  );
}

function Input(props) { return <input className="crmInput" {...props} />; }

function Select({ value, onChange, options, ...rest }) {
  return (
    <select className="crmSelect" value={value} onChange={(e) => onChange(e.target.value)} {...rest}>
      {options.map(o => typeof o === 'string'
        ? <option key={o} value={o}>{o}</option>
        : <option key={o[1]} value={o[1]}>{o[0]}</option>)}
    </select>
  );
}

function NumberInput({ value, onChange, min, max, step, suffix }) {
  return (
    <div style={{ position: 'relative' }}>
      <input type="number" className="crmInput" value={value} min={min} max={max} step={step}
        style={suffix ? { paddingRight: 48 } : undefined}
        onChange={(e) => onChange(Number(e.target.value))} />
      {suffix && (
        <span style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
          fontSize: 12, color: 'var(--ink-faint)', pointerEvents: 'none' }}>{suffix}</span>
      )}
    </div>
  );
}

function Toggle({ checked, onChange, children }) {
  return (
    <label className="crmToggle">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="track"></span>
      <span>{children}</span>
    </label>
  );
}

function Checkbox({ checked, onChange, children }) {
  return (
    <label className="crmCheck">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{children}</span>
    </label>
  );
}

function Textarea({ value, onChange, disabled, rows = 5, mono = true }) {
  return (
    <textarea className="crmTextarea" value={value} disabled={disabled} rows={rows}
      style={mono ? undefined : { fontFamily: "'Source Sans 3', sans-serif", fontSize: 14 }}
      onChange={(e) => onChange(e.target.value)} />
  );
}

function Btn({ kind = 'secondary', size, full, disabled, onClick, children, type }) {
  const cls = ['crmBtn', kind];
  if (size === 'lg') cls.push('lg');
  if (size === 'sm') cls.push('sm');
  if (full) cls.push('full');
  return (
    <button type={type || 'button'} className={cls.join(' ')} disabled={disabled} onClick={onClick}>
      {children}
    </button>
  );
}

function Multiselect({ value, onChange, options, labels }) {
  const remove = (v) => onChange(value.filter(x => x !== v));
  const add    = (v) => { if (v && !value.includes(v)) onChange([...value, v]); };
  const remaining = options.filter(o => !value.includes(o));
  return (
    <div className="crmMulti">
      {value.map(v => (
        <span key={v} className="crmChip">
          {labels[v] || v}
          <button type="button" className="x" onClick={() => remove(v)} aria-label={`Remove ${labels[v] || v}`}>×</button>
        </span>
      ))}
      {remaining.length > 0 && (
        <select value="" onChange={(e) => add(e.target.value)}>
          <option value="">+ add…</option>
          {remaining.map(o => <option key={o} value={o}>{labels[o] || o}</option>)}
        </select>
      )}
    </div>
  );
}

function Alert({ kind, children }) {
  const ico = { info: 'i', success: '✓', warning: '!', error: '×' }[kind];
  return (
    <div className={`crmAlert ${kind}`}>
      <span className="ico">{ico}</span>
      <span>{children}</span>
    </div>
  );
}

function Expander({ title, defaultOpen, right, children }) {
  return (
    <details className="crmExp" {...(defaultOpen ? { open: true } : {})}>
      <summary>
        <span>{title}</span>
        {right && (
          <span style={{ marginLeft: 'auto', marginRight: 8, fontSize: 12,
            color: 'var(--ink-faint)', fontWeight: 400 }}>{right}</span>
        )}
      </summary>
      <div className="body">{children}</div>
    </details>
  );
}

function Card({ title, right, tight, children }) {
  return (
    <section className="crmCard">
      {title && (
        <header className="crmCardHead">
          <h2>{title}</h2>
          {right && <span className="muted">{right}</span>}
        </header>
      )}
      <div className={`crmCardBody${tight ? ' tight' : ''}`}>{children}</div>
    </section>
  );
}

function Pill({ on, onClick, children, dot }) {
  return (
    <button type="button" className={`crmPill${on ? ' on' : ''}`} onClick={onClick}>
      {dot !== false && <span className="dot"></span>}
      {children}
    </button>
  );
}

function Badge({ kind, children }) {
  return <span className={`crmBadge${kind ? ' ' + kind : ''}`}>{children}</span>;
}

function Kpi({ label, value, delta, deltaKind = 'up' }) {
  return (
    <div className="crmKpi">
      <div className="lbl">{label}</div>
      <div className="val">{value}</div>
      {delta && <div className={`delta ${deltaKind}`}>{delta}</div>}
    </div>
  );
}

/* ─── Tweaks system ─── */

function useTweaks(defaults) {
  const [tweaks, setTweaks] = useState({ ...defaults });
  const setTweak = (key, val) => setTweaks(prev => ({ ...prev, [key]: val }));
  return { tweaks, setTweak };
}

function TweaksPanel({ onClose, children }) {
  return (
    <div className="crmTweaks">
      <div className="crmTweaksHead">
        <span>⚙ Tweaks</span>
        <button onClick={onClose} title="Close">×</button>
      </div>
      <div className="crmTweaksBody">{children}</div>
    </div>
  );
}

function TweakSection({ title, children }) {
  return (
    <div className="crmTweakSection">
      <div className="crmTweakSectionTitle">{title}</div>
      {children}
    </div>
  );
}

function TweakColor({ label, value, onChange }) {
  return (
    <div className="crmTweakRow">
      <span className="crmTweakLabel">{label}</span>
      <input type="color" className="crmTweakColor" value={value}
        onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

function TweakToggle({ label, value, onChange }) {
  return (
    <div className="crmTweakRow">
      <span className="crmTweakLabel">{label}</span>
      <Toggle checked={value} onChange={onChange}>{''}</Toggle>
    </div>
  );
}

function TweakSelect({ label, value, options, onChange }) {
  return (
    <div className="crmTweakRow" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 6 }}>
      <span className="crmTweakLabel">{label}</span>
      <Select value={value} onChange={onChange} options={options}
        style={{ width: '100%', fontSize: 13 }} />
    </div>
  );
}

function TweakSlider({ label, min, max, step, value, onChange }) {
  return (
    <div className="crmTweakRow" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
        <span className="crmTweakLabel">{label}</span>
        <span style={{ fontSize: 12, color: 'var(--ink-faint)' }}>{value}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        style={{ width: '100%', accentColor: 'var(--accent)' }}
        onChange={(e) => onChange(Number(e.target.value))} />
    </div>
  );
}

/* ─── Export everything to window ─── */
Object.assign(window, {
  Field, Input, Select, NumberInput, Toggle, Checkbox, Textarea,
  Btn, Multiselect, Alert, Expander, Card, Pill, Badge, Kpi,
  useTweaks, TweaksPanel, TweakSection,
  TweakColor, TweakToggle, TweakSelect, TweakSlider,
});
