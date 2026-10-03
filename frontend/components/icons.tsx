export const Star = (p: { size?: number }) => (
  <svg width={p.size ?? 28} height={p.size ?? 28} viewBox="0 0 24 24" aria-hidden="true">
    <path fill="currentColor" d="M12 1l1.6 7.2L20 4l-4.2 6.4L23 12l-7.2 1.6L20 20l-6.4-4.2L12 23l-1.6-7.2L4 20l4.2-6.4L1 12l7.2-1.6L4 4l6.4 4.2z" />
  </svg>
);

export const Arrow = () => (
  <svg width="18" height="18" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <path d="M5 11L11 5M6 5h5v5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const Clip = () => (
  <svg className="clip" viewBox="0 0 26 54" fill="none" aria-hidden="true">
    <path d="M18 14v26a6 6 0 0 1-12 0V9a4.5 4.5 0 0 1 9 0v29a2 2 0 0 1-4 0V14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
  </svg>
);

export const Wave = () => (
  <svg width="220" height="56" viewBox="0 0 220 56" aria-hidden="true">
    <path fill="currentColor" d="M0 27h20q6 0 8-3t6 0 6 3h8q8-24 18-24t14 24q4-24 14-24t14 24h6q4 0 6-4t8-4 10 8h10q4 0 6-3t8-3 8 6h40v2H172q-4 0-8 6t-8-6-8 0h-10q-6 8-10 8t-8-8h-6q-4 24-14 24T86 29q-4 24-14 24T54 29h-8q-4 0-6 3t-6 0-8-3H0z" />
  </svg>
);
