import { useEffect, useRef, useState } from 'react';

interface Props {
  disabled: boolean;
  placeholder: string;
  onSend(text: string): Promise<boolean>;
  onCompare?: (text: string) => void;
}

export function Composer({ disabled, placeholder, onSend, onCompare }: Props) {
  const [text, setText] = useState('');
  const area = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = area.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
  }, [text]);

  async function submit() {
    const value = text.trim();
    if (!value || disabled) return;
    setText('');
    // Keep the draft if the send fails so nothing typed is lost.
    if (!(await onSend(value))) setText(value);
    area.current?.focus();
  }

  return (
    <form className="composer" onSubmit={(e) => { e.preventDefault(); void submit(); }}>
      <label htmlFor="message" className="visually-hidden">Message</label>
      <textarea id="message" ref={area} rows={1} maxLength={2000} value={text} placeholder={placeholder}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void submit(); }
        }} />
      <div className="composer-actions">
        {onCompare && (
          <button type="button" className="ghost" disabled={disabled || !text.trim()} onClick={() => onCompare(text.trim())}
            title="Run every method on this question side by side">
            Compare methods
          </button>
        )}
        <button type="submit" className="primary" disabled={disabled || !text.trim()}>Send</button>
      </div>
    </form>
  );
}
