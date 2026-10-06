/** Minimal inline SVG icon set — avoids an icon-library dependency. */

const base = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.75,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
}

const wrap = (children, viewBox = '0 0 24 24') => (props) => (
  <svg {...base} viewBox={viewBox} aria-hidden="true" {...props}>
    {children}
  </svg>
)

export const UploadIcon = wrap(
  <>
    <path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5" />
    <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
  </>,
)

export const FileIcon = wrap(
  <>
    <path d="M14 3v5h5" />
    <path d="M19 8v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5Z" />
  </>,
)

export const TrashIcon = wrap(
  <>
    <path d="M4 7h16M10 11v6M14 11v6" />
    <path d="M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12" />
    <path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
  </>,
)

export const SendIcon = wrap(
  <>
    <path d="M4.5 12 20 4l-4 16-4.5-6L4.5 12Z" />
    <path d="M11.5 14 20 4" />
  </>,
)

export const StopIcon = wrap(
  <>
    <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none" />
  </>,
)

export const SparkIcon = wrap(
  <>
    <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3Z" />
    <path d="M18.5 15.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2Z" />
  </>,
)

export const ChevronIcon = wrap(<path d="m9 6 6 6-6 6" />)

export const CheckIcon = wrap(<path d="m5 13 4.5 4.5L19 7" />)

export const AlertIcon = wrap(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7.5v5.5M12 16.2v.3" />
  </>,
)

export const DatabaseIcon = wrap(
  <>
    <ellipse cx="12" cy="6" rx="8" ry="3" />
    <path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6" />
    <path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" />
  </>,
)

export const CodeIcon = wrap(
  <>
    <polyline points="16 18 22 12 16 6" />
    <polyline points="8 6 2 12 8 18" />
  </>,
)

export const CopyIcon = wrap(
  <>
    <rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
    <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
  </>,
)

export const TerminalIcon = wrap(
  <>
    <polyline points="4 17 10 11 4 5" />
    <line x1="12" x2="20" y1="19" y2="19" />
  </>,
)

export const ArchiveIcon = wrap(
  <>
    <polyline points="21 8 21 21 3 21 3 8" />
    <rect x="1" y="3" width="22" height="5" />
    <line x1="10" y1="12" x2="14" y2="12" />
  </>,
)

export const BookOpenIcon = wrap(
  <>
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
  </>,
)
