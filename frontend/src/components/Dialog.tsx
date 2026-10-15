import { useEffect, useRef, type ReactNode } from "react";

interface DialogProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}

/** A native modal <dialog>: focus is trapped, Escape closes it, and the page behind is inert. */
export function Dialog({ open, title, onClose, children }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog ref={ref} className="slip-dialog" aria-label={title} onClose={onClose} onCancel={onClose}>
      <div className="slip-dialog__body">
        <h2 className="slip-dialog__title">{title}</h2>
        {children}
      </div>
    </dialog>
  );
}
