import { useEffect, useRef } from 'react';

export function SkipLink() {
  const ref = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Tab' && ref.current) {
        ref.current.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown, { once: true });
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <a
      ref={ref}
      href="#main-content"
      style={{
        position: 'absolute',
        top: '-100px',
        left: '0',
        background: '#0056b3',
        color: '#fff',
        padding: '8px 16px',
        zIndex: 10000,
        textDecoration: 'underline',
      }}
      onFocus={(e) => {
        (e.target as HTMLElement).style.top = '0';
      }}
      onBlur={(e) => {
        (e.target as HTMLElement).style.top = '-100px';
      }}
    >
      Skip to main content
    </a>
  );
}
