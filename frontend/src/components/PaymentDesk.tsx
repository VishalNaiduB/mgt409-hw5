import { useState, type FormEvent } from "react";
import { formatMoney } from "../format";
import type { Payment, Ticket } from "../types";
import { Dialog } from "./Dialog";

interface PaymentDeskProps {
  payments: Payment[];
  tickets: Ticket[];
  onApprove: (paymentId: number, approvedBy: string) => Promise<void>;
}

function describe(payment: Payment, tickets: Ticket[]): { title: string; ticket: Ticket | undefined } {
  const ticket = tickets.find((t) =>
    payment.kind === "invoice" ? t.invoice_id === payment.ref_id : t.lease_id === payment.ref_id,
  );
  const title = payment.kind === "invoice" ? `Invoice ${payment.ref_id}` : `Rent · Lease ${payment.ref_id}`;
  return { title, ticket };
}

export function PaymentDesk({ payments, tickets, onApprove }: PaymentDeskProps) {
  const [approving, setApproving] = useState<Payment | null>(null);
  const [name, setName] = useState("Vishal");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function open(payment: Payment) {
    setApproving(payment);
    setName("Vishal");
    setError(null);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!approving || !name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await onApprove(approving.id, name.trim());
      setApproving(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card paydesk" aria-labelledby="paydesk-title">
      <div className="card__head">
        <h2 id="paydesk-title" className="card__title">
          Payments awaiting approval
        </h2>
        <span className="muted small">{payments.length === 0 ? "none" : `${payments.length} staged`}</span>
      </div>

      {payments.length === 0 ? (
        <p className="muted small">
          Nothing is staged. Accounting stages payments here; only a human approval moves cash.
        </p>
      ) : (
        <ul className="paydesk__list">
          {payments.map((payment) => {
            const { title, ticket } = describe(payment, tickets);
            return (
              <li key={payment.id} className="voucher">
                <div className="voucher__top">
                  <span className="voucher__no mono">Voucher #{payment.id}</span>
                  <span className="voucher__amount mono">{formatMoney(payment.amount)}</span>
                </div>
                <p className="voucher__what">
                  {title}
                  {ticket && <> · Job {ticket.id} ({ticket.requester})</>}
                </p>
                <p className="muted small">From {payment.account} · staged, not paid</p>
                <button type="button" className="btn btn--approve btn--wide" onClick={() => open(payment)}>
                  Approve {formatMoney(payment.amount)}
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <Dialog
        open={approving !== null}
        title={approving ? `Approve voucher #${approving.id}` : "Approve payment"}
        onClose={() => !busy && setApproving(null)}
      >
        {approving && (
          <form onSubmit={submit}>
            <p>
              Pay <strong className="mono">{formatMoney(approving.amount)}</strong> for{" "}
              {describe(approving, tickets).title} from <strong>{approving.account}</strong>. This deducts the money
              and resolves the job.
            </p>
            <label className="field">
              <span className="field__label">Approved by</span>
              <input
                className="field__input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                autoFocus
                autoComplete="name"
              />
            </label>
            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}
            <div className="slip-dialog__actions">
              <button type="button" className="btn btn--ghost" onClick={() => setApproving(null)} disabled={busy}>
                Cancel
              </button>
              <button type="submit" className="btn btn--approve" disabled={busy || !name.trim()}>
                {busy ? "Approving…" : "Approve payment"}
              </button>
            </div>
          </form>
        )}
      </Dialog>
    </section>
  );
}
