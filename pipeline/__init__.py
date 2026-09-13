"""NOS veri pipeline paketi.

Fazlar (bkz. .omc/plans/2026-07-24-nos-veri-sqlite-plan.md §5):
  fetch  -> K1 (YÖK Atlas JSON API) + K2 (ÖSYM 2026 kılavuz, opsiyonel)
  merge  -> dedup (kilavuz_kodu), türetmeler, Türkçe fold, programs.json
  validate / build_sqlite / tests -> Faz 3–5 (Task #2)
"""
