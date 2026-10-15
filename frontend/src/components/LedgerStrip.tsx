import { useState } from "react";
import { formatMoney, formatShopDate } from "../format";
import type { CashResponse } from "../types";
import { Dialog } from "./Dialog";

interface LedgerStripProps {
  shopDate: string | null;
  cash: CashResponse | null;
  running: boolean;
  onReset: () => Promise<void>;
}

export function LedgerStrip({ shopDate, cash, running, onReset }: LedgerStripProps) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const account = cash?.account;

  async function confirmReset() {
    setBusy(true);
    setError(null);
    try {
      await onReset();
      setConfirming(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reset failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <header className="ledger">
      <div className="ledger__brand">
        <span className="ledger__est">Est. on Chapel St · Campus Customs</span>
        <span className="ledger__name">Chapel Street Print Shop</span>
        <span className="ledger__sub">&amp; Dispatch Desk</span>
      </div>

      <dl className="ledger__cells">
        <div className="ledger__cell">
          <dt>Shop date</dt>
          <dd className="mono">{shopDate ? formatShopDate(shopDate) : "—"}</dd>
          <span className="ledger__note">desk.date_today</span>
        </div>
        <div className="ledger__cell">
          <dt>Checking balance</dt>
          <dd className="mono ledger__figure">{account ? formatMoney(account.balance) : "—"}</dd>
          <span className="ledger__note">cash on hand</span>
        </div>
        <div className="ledger__cell ledger__cell--key">
          <dt>Uncommitted cash</dt>
          <dd className="mono ledger__figure">{account ? formatMoney(account.available) : "—"}</dd>
          <span className="ledger__note">
            {account && account.pending_staged > 0
              ? `after ${formatMoney(account.pending_staged)} staged`
              : "nothing staged"}
          </span>
        </div>
      </dl>

      <div className="ledger__actions">
        <button
          type="button"
          className="btn btn--brass"
          onClick={() => setConfirming(true)}
          disabled={running}
          title={running ? "Wait for the current run to finish" : undefined}
        >
          Reset DB
        </button>
      </div>

      <Dialog open={confirming} title="Reset the shop database?" onClose={() => !busy && setConfirming(false)}>
        <p>
          This restores <code>campus_customs_new.db</code> from the original: every ticket goes back to open, staged and
          approved payments are cleared, and checking returns to its starting balance.
        </p>
        <p className="muted">The audit trail is kept.</p>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <div className="slip-dialog__actions">
          <button type="button" className="btn btn--ghost" onClick={() => setConfirming(false)} disabled={busy}>
            Cancel
          </button>
          <button type="button" className="btn btn--danger" onClick={confirmReset} disabled={busy}>
            {busy ? "Resetting…" : "Yes, reset the database"}
          </button>
        </div>
      </Dialog>
    </header>
  );
}
