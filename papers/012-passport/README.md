# Paper 012 — The Regulatory Passport

Lifecycle & change-control automation for clinical AI agents (`src/lifecycle/`).

- `main.tex` / `main.pdf` — the paper (11pp, house style). Build: `make paper`.
- `numbers.tex` — headline macros; every number traces to `results/012-passport/`.
- `figs/` — figures rendered by `scripts/012-passport/summarize.py`.
- `PROPOSAL.md` — the pre-registered proposal.

Reproduce all numbers and figures:

```bash
python3 scripts/012-passport/gen_passports.py
cargo run --release --bin passportbench -- --data datasets/012-passport --out results/012-passport
python3 scripts/012-passport/summarize.py
cd papers/012-passport && make paper
```

**Headline:** deterministic risk classification reproduces documented criteria at
0.992 (κ ≥ 0.955); PCCP gating detects 0.988 of out-of-envelope changes (AUC 0.998);
fingerprinting detects + localizes 100% of component swaps; the gate adds ~39µs off
the hot path. The central finding: cross-jurisdiction risk classification genuinely
diverges (agreement 0.699), with all 271 divergences documented and explained. Labels
are author-encoded from published criteria, not a human panel (E1 is a reproducibility
claim — see the paper's limitations).
