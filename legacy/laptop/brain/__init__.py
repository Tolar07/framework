"""OLP XDV brain — central persistent memory (SQLite, stdlib only).

The brain is the framework's queryable long-term store: fitted model state
(Elo / Dixon-Coles / cross-league) so the daily run refits only what changed,
every board prediction, a mirror of the CLV ledger, and the corrections/
decisions layer. Additive by design — clv/clv_log.json stays the canonical
ledger; the brain is derived from it.
"""
