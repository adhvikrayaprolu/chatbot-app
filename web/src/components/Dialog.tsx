import { useEffect, useRef, type ReactNode } from 'react';

interface Props {
  open: boolean;
  title: string;
  onClose(): void;
  children: ReactNode;
  wide?: boolean;
}

/** Native <dialog>: focus trapping, Escape and backdrop semantics come from the browser. */
export function Dialog({ open, title, onClose, children, wide }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);
  return (
    <dialog ref={ref} className={wide ? 'wide' : undefined} aria-label={title} onClose={onClose}
      onClick={(e) => { if (e.target === ref.current) onClose(); }}>
      <header className="dialog-header">
        <h2>{title}</h2>
        <button type="button" className="icon" aria-label="Close" onClick={onClose}>×</button>
      </header>
      {open && children}
    </dialog>
  );
}
