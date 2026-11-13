import { useState } from 'react'
import { copyText } from '../format.js'

const ICONS = {
  home: <><path d="M3 10.5 12 3l9 7.5" /><path d="M5 9.5V21h14V9.5" /><path d="M10 21v-6h4v6" /></>,
  table: <><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M3 10h18M3 15h18M9 4v16" /></>,
  mapping: <><circle cx="6" cy="6" r="2.5" /><circle cx="6" cy="18" r="2.5" /><circle cx="18" cy="12" r="2.5" /><path d="M8.5 6.5 15.6 11M8.5 17.5l7.1-4.5" /></>,
  shield: <><path d="M12 3 4 6v6c0 4.5 3.4 8.2 8 9 4.6-.8 8-4.5 8-9V6l-8-3Z" /><path d="m8.5 12 2.5 2.5 4.5-5" /></>,
  database: <><ellipse cx="12" cy="5.5" rx="8" ry="3" /><path d="M4 5.5v13c0 1.7 3.6 3 8 3s8-1.3 8-3v-13" /><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></>,
  agent: <><path d="M12 3v3M12 18v3M3 12h3M18 12h3" /><rect x="7" y="7" width="10" height="10" rx="2.5" /><path d="M10 11h.01M14 11h.01M10 14h4" /></>,
  upload: <><path d="M12 15V4" /><path d="m7 9 5-5 5 5" /><path d="M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4" /></>,
  download: <><path d="M12 4v11" /><path d="m7 10 5 5 5-5" /><path d="M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4" /></>,
  file: <><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z" /><path d="M14 3v5h5" /></>,
  code: <><path d="m8 7-5 5 5 5M16 7l5 5-5 5" /></>,
  play: <><path d="M7 4.5v15l12-7.5-12-7.5Z" /></>,
  refresh: <><path d="M20 11a8 8 0 0 0-14.6-4.5L3 9" /><path d="M3 4v5h5" /><path d="M4 13a8 8 0 0 0 14.6 4.5L21 15" /><path d="M21 20v-5h-5" /></>,
  trash: <><path d="M4 7h16M10 11v6M14 11v6" /><path d="M6 7l1 13h10l1-13M9 7V4h6v3" /></>,
  check: <><path d="m5 12.5 4.5 4.5L19 7.5" /></>,
  alert: <><path d="M12 3 2 20h20L12 3Z" /><path d="M12 10v4M12 17h.01" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></>,
  x: <><path d="M6 6l12 12M18 6 6 18" /></>,
  copy: <><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" /></>,
  arrow: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
  search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></>,
  bolt: <><path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" /></>,
  sparkle: <><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z" /><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z" /></>,
  layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m3 13 9 5 9-5" /></>,
}

export function Icon({ name, size = 18, className = '' }) {
  return (
    <svg className={`icon ${className}`} width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {ICONS[name] || ICONS.info}
    </svg>
  )
}

export function Spinner({ size = 16 }) {
  return <span className="spinner" style={{ width: size, height: size }} aria-hidden="true" />
}

export function Button({ variant = 'primary', icon, busy = false, children, className = '', ...props }) {
  return (
    <button className={`btn btn-${variant} ${className}`} disabled={busy || props.disabled} {...props}>
      {busy ? <Spinner /> : icon && <Icon name={icon} size={16} />}
      {children && <span>{children}</span>}
    </button>
  )
}

export function LinkButton({ variant = 'secondary', icon, children, className = '', ...props }) {
  return (
    <a className={`btn btn-${variant} ${className}`} {...props}>
      {icon && <Icon name={icon} size={16} />}
      <span>{children}</span>
    </a>
  )
}

const STATUS = {
  success: ['success', 'Complete'],
  nonconformant: ['warning', 'Issues found'],
  error: ['danger', 'Failed'],
  running: ['info', 'Running'],
}

export function Badge({ tone = 'neutral', children, dot = false }) {
  return <span className={`badge badge-${tone}`}>{dot && <i />}{children}</span>
}

export function StatusBadge({ status, idle = 'Not started' }) {
  const [tone, label] = STATUS[status] || ['neutral', idle]
  return <Badge tone={tone} dot>{label}</Badge>
}

export function Card({ title, subtitle, icon, actions, children, className = '', padded = true }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-header">
          <div className="card-title">
            {icon && <span className="card-icon"><Icon name={icon} size={18} /></span>}
            <div>
              {title && <h3>{title}</h3>}
              {subtitle && <p>{subtitle}</p>}
            </div>
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      <div className={padded ? 'card-body' : ''}>{children}</div>
    </section>
  )
}

export function Kpi({ label, value, hint, icon, tone = 'neutral', onClick }) {
  const Tag = onClick ? 'button' : 'div'
  return (
    <Tag className={`kpi kpi-${tone}`} onClick={onClick} type={onClick ? 'button' : undefined}>
      <div className="kpi-top">
        <span>{label}</span>
        {icon && <span className="kpi-icon"><Icon name={icon} size={16} /></span>}
      </div>
      <strong title={typeof value === 'string' ? value : undefined}>{value}</strong>
      {hint && <small>{hint}</small>}
    </Tag>
  )
}

export function EmptyState({ icon = 'info', title, children, action }) {
  return (
    <div className="empty-state">
      <span className="empty-icon"><Icon name={icon} size={26} /></span>
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action && <div className="empty-action">{action}</div>}
    </div>
  )
}

export function Notice({ tone = 'info', title, children, onClose }) {
  const icon = { success: 'check', warning: 'alert', danger: 'alert', info: 'info' }[tone]
  return (
    <div className={`notice notice-${tone}`} role={tone === 'danger' ? 'alert' : 'status'}>
      <Icon name={icon} size={18} />
      <div>
        {title && <strong>{title}</strong>}
        {children && <div className="notice-text">{children}</div>}
      </div>
      {onClose && <button className="icon-button" onClick={onClose} aria-label="Dismiss"><Icon name="x" size={16} /></button>}
    </div>
  )
}

export function Segmented({ options, value, onChange, label }) {
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {options.map((option) => (
        <button key={option.value} type="button" role="radio" aria-checked={value === option.value}
          className={value === option.value ? 'active' : ''} onClick={() => onChange(option.value)}>
          {option.icon && <Icon name={option.icon} size={15} />}
          {option.label}
        </button>
      ))}
    </div>
  )
}

export function CopyButton({ text, label = 'Copy' }) {
  const [copied, setCopied] = useState(false)
  async function handleCopy() {
    if (await copyText(text)) {
      setCopied(true)
      setTimeout(() => setCopied(false), 1400)
    }
  }
  return (
    <button type="button" className="copy-button" onClick={handleCopy} title={`Copy ${text}`}>
      <Icon name={copied ? 'check' : 'copy'} size={14} />{copied ? 'Copied' : label}
    </button>
  )
}

export function StageResult({ result, children }) {
  if (!result) return null
  const tone = { success: 'success', nonconformant: 'warning', error: 'danger', running: 'info' }[result.status] || 'info'
  return (
    <div className="stage-result">
      <Notice tone={tone} title={result.message} />
      {children}
      {result.log && (
        <details className="log-details">
          <summary>Technical log</summary>
          <pre>{result.log}</pre>
        </details>
      )}
    </div>
  )
}
