/** The Their Take mark: a speech bubble holding a quotation mark. Same artwork as app/icon.svg. */
export function Logo({ className = "h-7 w-7" }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <rect width="64" height="64" rx="14" fill="#b4441e" />
      <path
        fill="#fbfaf8"
        d="M21 12h22a10 10 0 0 1 10 10v12a10 10 0 0 1-10 10H29l-10 8.5V43.4A10 10 0 0 1 11 34V22a10 10 0 0 1 10-10z"
      />
      <g fill="#b4441e" transform="translate(33 29) scale(1.2) translate(-33 -29.6)">
        <path d="M27.5 21.5a5 5 0 0 1 3.4 8.7c-.9 3.4-3.3 6.1-6.6 7.5l-1.3-2c2-1.1 3.4-2.6 4.1-4.4a5 5 0 0 1 .4-9.8z" />
        <path d="M39.5 21.5a5 5 0 0 1 3.4 8.7c-.9 3.4-3.3 6.1-6.6 7.5l-1.3-2c2-1.1 3.4-2.6 4.1-4.4a5 5 0 0 1 .4-9.8z" />
      </g>
    </svg>
  );
}
