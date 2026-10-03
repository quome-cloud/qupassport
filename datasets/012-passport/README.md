# PassportBench — the regulatory-passport benchmark (paper 012)

Synthetic, deterministic (seed 42), Apache-2.0, **no PHI**. Regenerate with:

```bash
python3 scripts/012-passport/gen_passports.py
```

`gen_passports.py` is stdlib-only and deterministic — a re-run produces byte-identical files.

## Contents

| Path | Rows | Used by |
|---|---|---|
| `passports/passports.jsonl` | 150 | E1 (classification accuracy), E3 (harmonization) |
| `changes/changes.jsonl` | 400 | E2 (PCCP gating), E4 (fingerprint sensitivity) |
| `pccp/schema.json` | — | machine-readable PCCP schema (JSON-Schema draft-07) |
| `pccp/examples.jsonl` | 3 | example change-control plans |

### `passports.jsonl`
Each record: `{id, metadata, stratum, labels}`. `metadata` is the declarative
`AgentMetadata` (clinical task, output type, declared autonomy, condition severity,
patient-facing, tool inventory). `labels` maps each of the four jurisdictions
(`fda`, `eu_ai_act`, `health_canada`, `mhra`) to its **ground-truth**
`{risk_class, autonomy_level}`. The grid is the coherent cross-product of
task × output × autonomy × severity × patient-facing (incoherent combinations —
e.g. an information-only output with autonomous action — are pruned).

### `changes.jsonl`
Each record is a paired change-event: a `deployed_fingerprint` (per-component
SHA-256), a `live_fingerprint` differing in 1–3 components, the attached `pccp`,
the changed components, per-component `deltas` (a weights delta carries both the
`true` magnitude and a noisy admission-time `est`imate), and the ground-truth
`true_out_of_envelope` label.

## Label-encoding methodology (read this — the honesty boundary)

The per-jurisdiction labels are **author-encoded from published regulatory
criteria**, *not* a live multi-rater expert panel (we did not run one, and we do
not claim concordance with one). The encoded primary sources are:

- **IMDRF SaMD WG/N12** risk-categorization grid (significance of information ×
  state of healthcare situation) — the framework-agnostic risk spine.
- **FDA** Clinical Decision Support guidance (2022) / 21st Century Cures Act §3060
  non-device CDS carve-out.
- **EU AI Act** Annex III(5) (high-risk AI) layered over the MDR safety-component
  rule.
- **Health Canada** SaMD guidance (adopts IMDRF N12 verbatim).
- **MHRA** "Software and AI as a Medical Device" framework (IMDRF-aligned; stricter
  on patient-facing decision support).

The generator is an **independent Python re-statement** of these criteria; the Rust
classifier (`src/lifecycle/classifier.rs`) encodes the same sources separately. E1
therefore measures the **cross-implementation reproducibility of documented
criteria** — determinism and fidelity — not a contest against human judgement.

### The `boundary` stratum (where mechanical ≠ expert)
Most cases are unambiguous (`stratum = "clear"`): the documented criteria map
metadata to a class with no judgement. A small **objectively-defined** subset
(`stratum = "boundary"`) is the genuinely contested zone — the FDA non-device CDS
carve-out applied to a **serious** condition, which FDA guidance treats as a
case-by-case judgement. There the ground-truth label reflects the **stricter expert
interpretation** (the carve-out is declined, keeping the IMDRF spine), while the
mechanical classifier still applies the carve-out. The classifier therefore
diverges from the label on exactly these FDA-boundary cases — an explainable,
documented gap, *defined by a predicate, not tuned to a number*. Whatever accuracy
results is reported as-is (see `results/012-passport/`). This mirrors the paper's
thesis: the passport mechanically classifies and *flags* the contested band for
human adjudication.
