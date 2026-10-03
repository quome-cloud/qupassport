<div align="center">

<img src="assets/qupassport-logo.svg" alt="qupassport" width="520">

### A signed, four-jurisdiction regulatory passport that fail-closes agent deployment on any out-of-PCCP change

![built with](https://img.shields.io/badge/built_with-Rust-DEA584?logo=rust&logoColor=white)
![layer](https://img.shields.io/badge/layer-lifecycle-7c3aed)
![HAARF](https://img.shields.io/badge/HAARF-C1/C6-0ea5e9)
![paper](https://img.shields.io/badge/paper-preprint-2563eb)
![status](https://img.shields.io/badge/status-research_prototype-orange)
![license](https://img.shields.io/badge/license-Apache_2.0-3FB950)
[![dataset](https://img.shields.io/badge/🤗_dataset-Quome%2Fpassportbench-FFD21E)](https://huggingface.co/datasets/Quome/passportbench)

[**Quickstart**](#quickstart) · [How it works](#how-it-works) · [Reproduce](#reproduce-the-experiments) · [Results](#headline-results) · [Paper](papers/012-passport/main.pdf) · [Dataset](https://huggingface.co/datasets/Quome/passportbench) · [Cite](#cite)

</div>

---

A clinical AI agent is cleared at a specific risk class and autonomy level under a Predetermined Change Control Plan (PCCP), then silently drifts as prompts are edited, models swapped, tools added, and data refreshed. The lifecycle layer runs at admission time in the qfire gateway: it verifies an ed25519-signed, versioned passport that classifies the agent's risk and autonomy under FDA, EU AI Act, Health Canada, and MHRA rules, diffs a per-component SHA-256 fingerprint of the live agent against the passport, evaluates every changed component against the PCCP envelope, and refuses registration (fail-closed) on any out-of-envelope change, stamping the passport version into the quledger audit chain. On PassportBench (150 passports, 400 change-events, seed 42) the deterministic classifier reproduces framework-grounded labels at 0.992 accuracy (95% CI [0.981, 0.996]), PCCP gating detects 0.988 of out-of-envelope changes (AUC 0.998), fingerprinting detects and localizes 100% of component swaps, and the gate costs 38.7 us median off the hot path. The central finding is that cross-jurisdiction classification genuinely diverges (mean agreement 0.699), yet every one of the 271 divergences is explained by a documented regulatory difference.

`qupassport` is **a module of the QUOKKAGUARD program**: one Rust security gateway (`qfire`) that sits in front of any OpenAI-compatible model endpoint and decides **ALLOW ▸ forward · BLOCK ▸ refuse · ESCALATE ▸ human review** for every request and response. Each module adds exactly one enforcement layer to that gateway plus one adversarial dataset and one paper. This repository is a self-contained snapshot of the gateway with **this layer** (`src/lifecycle/`, on the *admission* path, HAARF control C1/C6), its dataset (**PassportBench**), the experiment harness, and the paper.

> Everything here runs **offline**: no model API keys, no network calls in the experiments.

## How it works

- **Signed passport artifact**: a versioned, ed25519-signed canonical-JSON declaration (agent_id, version, pinned ruleset_version, metadata, per-jurisdiction classifications, PCCP, deployed_fingerprint, autonomy_envelope, not_after). Loading fails closed on a bad or missing signature, expiry, or an agent_id absent from the quorum registry.
- **Deterministic, citation-tagged classifier**: the IMDRF SaMD N12 risk grid (significance of information x healthcare-situation severity) is the framework-agnostic spine; each jurisdiction applies a documented overlay (FDA non-device CDS carve-out, EU AI Act Annex III high-risk trigger, Health Canada adopts IMDRF verbatim, MHRA stricter on patient-facing decision support). Every rule appends a citation to a rationale trace, autonomy is capped by clinical consequence, and the rule set is version-pinned (2026.06).
- **Harmonizer**: classifies under all four jurisdictions and reports mean pairwise agreement plus each divergence with the regulatory rationale that explains it, so disagreement is surfaced and contestable rather than collapsed into one global answer.
- **Per-component fingerprinting + PCCP gating**: at admission the gate hashes weights, prompt, tools, and data separately (SHA-256), diffs against the passport's deployed fingerprint, and evaluates each changed component against the PCCP: forbidden or unlisted components are out-of-envelope (fail-closed); bounded_magnitude components (e.g. weights up to max_fraction 0.05) pass only if the admission-time magnitude estimate is within the bound.
- **Fail-closed admission gate with audit stamping**: a full decision (signature verify, fingerprint diff, four-jurisdiction classify, PCCP evaluate) runs once per agent registration beside the qubom AIBOM gate, with enforce = block|warn|off; the verdict and passport version are stamped into the quledger hash-chained audit log, and Passport::autonomy_envelope() feeds the qudrift drift monitor while the qudrift real-world-evidence bundle feeds re-assessment.

## Quickstart

Requires Rust 1.85+ (`rustup`), Python 3.10+ for the analysis scripts, and `tectonic` (or `pdflatex`) only if you want to rebuild the paper.

```bash
git clone https://github.com/quome-cloud/qupassport
cd qupassport
cargo build --release
cargo test lifecycle && cargo test --test lifecycle_integration   # this layer's tests
```

Then see the layer in action:

```bash
# 1. Classify an agent's declared metadata under all four jurisdictions (deterministic, no model)
./target/release/qfire lifecycle classify --metadata '{"intended_use":"ED sepsis triage prioritisation","clinical_task":"drive","output_type":"recommendation","autonomy":"advisory","condition_severity":"serious","patient_facing":false,"tools":["vitals_lookup","ews_score"]}'
#            fda  risk=...       autonomy=...
#      eu_ai_act  risk=...       autonomy=...   (one line per jurisdiction; add --json for the citation-tagged rationale)

# 2. Harmonize: mean cross-jurisdiction agreement plus every explained divergence
./target/release/qfire lifecycle harmonize --metadata '{"intended_use":"ED sepsis triage prioritisation","clinical_task":"drive","output_type":"recommendation","autonomy":"advisory","condition_severity":"serious","patient_facing":false,"tools":["vitals_lookup","ews_score"]}'
# agreement: 0.xxx (N divergence(s))
#   fda vs eu_ai_act: <regulatory rationale>

# 3. Replay PassportBench end to end (E1-E5, offline, seconds)
cargo run --release --bin passportbench -- --data datasets/012-passport --out results/012-passport --exp all
# E1: 595/600 correct (0.992)
# E2: 400 events (334 out / 66 in)
# E3: HCA 0.699, 271 divergences, all explained = true
# E4: 400 change-events fingerprinted
# E5: median ~39us/gate, p95 ~46us, ~25000 gates/s

# 4. Verify a signed passport / run the admission gate against a live fingerprint
#    (passport JSON as written by SignedPassport; see tests/lifecycle_integration.rs)
./target/release/qfire lifecycle verify --passport passport.json
./target/release/qfire lifecycle gate --passport passport.json --live-fingerprint @live.json --registry sepsis-triage --enforce block
# admitted=false agent_id=sepsis-triage version=2.1.0   (exit 2 = BLOCK)
```

## Reproduce the experiments

Every number in the paper traces to one of these runs (95% Wilson CIs, deterministic seeds, pinned model snapshots). Run outputs land in `results/012-passport/` (not tracked; see [`results/012-passport/README.md`](results/012-passport/README.md) for the exact regeneration commands).

| Exp | What it measures | Needs |
|---|---|---|
| E1 | Classification accuracy: rule classifier vs author-encoded labels per jurisdiction (CLA, Cohen's kappa, clear vs boundary strata) | offline |
| E2 | PCCP gating: out-of-envelope detection rate, in-envelope false-trigger rate, ROC/AUC over 400 change-events | offline |
| E3 | Harmonization: cross-jurisdiction agreement matrix and fraction of divergences explained | offline |
| E4 | Change-fingerprint sensitivity: detection and localization by change granularity, per-component vs whole-config hash ablation | offline |
| E5 | Deployment-gate overhead: median/p95 latency of a full gate decision | offline |
| all | Regenerate corpus, run E1-E5, and rebuild figures + numbers.tex | offline |

```bash
# E1 — Classification accuracy: rule classifier vs author-encoded labels per jurisdiction (CLA, Cohen's kappa, clear vs boundary strata)
cargo run --release --bin passportbench -- --data datasets/012-passport --out results/012-passport --exp e1

# E2 — PCCP gating: out-of-envelope detection rate, in-envelope false-trigger rate, ROC/AUC over 400 change-events
cargo run --release --bin passportbench -- --data datasets/012-passport --out results/012-passport --exp e2

# E3 — Harmonization: cross-jurisdiction agreement matrix and fraction of divergences explained
cargo run --release --bin passportbench -- --data datasets/012-passport --out results/012-passport --exp e3

# E4 — Change-fingerprint sensitivity: detection and localization by change granularity, per-component vs whole-config hash ablation
cargo run --release --bin passportbench -- --data datasets/012-passport --out results/012-passport --exp e4

# E5 — Deployment-gate overhead: median/p95 latency of a full gate decision
cargo run --release --bin passportbench -- --data datasets/012-passport --out results/012-passport --exp e5

# all — Regenerate corpus, run E1-E5, and rebuild figures + numbers.tex
python3 scripts/012-passport/gen_passports.py && cargo run --release --bin passportbench -- --data datasets/012-passport --out results/012-passport && python3 scripts/012-passport/summarize.py
```

**Dataset — PassportBench** (`datasets/012-passport/`): 150 synthetic agent passports (140 clear-stratum, 10 boundary-stratum) with author-encoded ground-truth risk/autonomy labels under FDA, EU AI Act, Health Canada, and MHRA, plus 400 paired change-events (334 out-of-envelope, 66 in-envelope) carrying deployed/live per-component SHA-256 fingerprints, PCCP, and noisy weight-magnitude estimates, with a JSON-Schema PCCP schema and 3 example plans; seed 42, stdlib-only, no PHI.

Regenerate the corpus (deterministic seeds):

```bash
python3 scripts/012-passport/gen_passports.py
```

The corpus is also published as a Hugging Face dataset with a full data card: **[Quome/passportbench](https://huggingface.co/datasets/Quome/passportbench)** (`datasets.load_dataset("Quome/passportbench")`, or `hf download Quome/passportbench --repo-type dataset`).

All data are synthetic; no protected health information is used anywhere in this repository.

## Headline results

| Metric | Value | Context |
|---|---|---|
| Classification accuracy (CLA) | **0.992 (95% CI [0.981, 0.996])** | 600 passport x jurisdiction decisions; clear stratum 1.000, boundary stratum 0.875; kappa FDA 0.955, EU/HC/MHRA 1.00 |
| PCCP out-of-envelope detection (PGD) | **0.988 (95% CI [0.970, 0.995]), AUC 0.998** | 400 change-events; in-envelope false-trigger 0.061 [0.024, 0.146] from noisy weight-magnitude estimates |
| Cross-jurisdiction agreement (HCA) | **0.699** | 271 divergences, 100% explained by documented regulatory differences (EU Annex III high-risk trigger) |
| Component-fingerprint detection / localization | **1.000 / 1.000 (whole-config hash: 0.000 localization)** | per-component SHA-256 both detects and localizes every swap |
| Deployment-gate latency | **38.7 us median, 45.8 us p95 (~25,400 gates/s)** | once per agent registration, zero per-call cost |

Full methodology, ablations, and statistics: **[the paper](papers/012-passport/main.pdf)**.

## The paper

**The Regulatory Passport: Lifecycle and Change-Control Automation for Clinical AI Agents**

- PDF: [`papers/012-passport/main.pdf`](papers/012-passport/main.pdf)
- Source: [`papers/012-passport/`](papers/012-passport/) — `main.tex`, `numbers.tex` (every headline macro, generated by the scripts above), `figs/`, `refs.bib`
- Pre-registered proposal (threat model, hypotheses, experiment→figure map): [`papers/012-passport/PROPOSAL.md`](papers/012-passport/PROPOSAL.md)
- Rebuild: `cd papers/012-passport && make paper` (tectonic, or pdflatex + bibtex)

## Repository layout

| Path | What |
|---|---|
| `src/` | The `qfire` gateway crate. This paper's layer lives in `src/lifecycle/`; the other modules are the always-on baseline it plugs into. |
| `src/bin/` | CLI (`qfire`) and per-paper experiment harnesses |
| `rules/`, `chains/` | Declarative rule and detector-chain library used by the gateway |
| `datasets/012-passport/` | PassportBench (also on Hugging Face: [Quome/passportbench](https://huggingface.co/datasets/Quome/passportbench)) |
| `scripts/012-passport/` | Dataset generator, experiment runners, figure and `numbers.tex` builders |
| `scripts/common/` | Shared helpers |
| `papers/012-passport/` | The paper (LaTeX + PDF + proposal) |
| `results/012-passport/` | Experiment outputs (see above) |
| `tests/`, `benches/` | Integration tests and Criterion benches |
| `SNAPSHOT.md` | Which `quokkaguard` commit this repo was exported from |

## Relationship to QUOKKAGUARD

This repo is a **snapshot** of the QUOKKAGUARD program's gateway (export `1c04c3a34841`, 2026-10-02), filtered to the `qupassport` module. The full `qfire` crate is included so this layer builds, tests, and runs standalone; the other modules are the always-on baseline the layer plugs into. Issues and pull requests are welcome here.

This layer builds on: [qubom](https://github.com/quome-cloud/qubom), [qudrift](https://github.com/quome-cloud/qudrift), [quorum](https://github.com/quome-cloud/quorum), [quledger](https://github.com/quome-cloud/quledger).

Sibling repos in the series: [quanchor](https://github.com/quome-cloud/quanchor), [quledger](https://github.com/quome-cloud/quledger), [qubom](https://github.com/quome-cloud/qubom), [quwarden](https://github.com/quome-cloud/quwarden), [qudam](https://github.com/quome-cloud/qudam), [quantidote](https://github.com/quome-cloud/quantidote), [quorum](https://github.com/quome-cloud/quorum), [qutriage](https://github.com/quome-cloud/qutriage), [qufair](https://github.com/quome-cloud/qufair), [qudrift](https://github.com/quome-cloud/qudrift), [quconsent](https://github.com/quome-cloud/quconsent), [qubroker](https://github.com/quome-cloud/qubroker), [qusiege](https://github.com/quome-cloud/qusiege).

## Cite

If you use this code or dataset, cite the paper and the HAARF framework it implements:

```bibtex
@unpublished{schwoebel2026qupassport,
  author = {{QUOKKAGUARD Project}},
  title  = {The Regulatory Passport: Lifecycle and Change-Control Automation for Clinical AI Agents},
  note   = {Preprint. Quome, QUOKKAGUARD program (qupassport module)},
  year   = {2026},
  url    = {https://github.com/quome-cloud/qupassport}
}

@unpublished{schwoebel2026haarf,
  author = {Schwoebel, Jim and Frasch, Martin and Spalding, Art and Sewell, Ed and Englert, Phil and Halpert, Ben and Overbay, Collin and Semenec, Ingrida and Shor, Joel},
  title  = {{HAARF}: Healthcare {AI} agents regulatory framework --- a comprehensive security verification standard for autonomous {AI} systems in clinical environments},
  note   = {medRxiv Preprint},
  year   = {2026},
  month  = {April},
  doi    = {10.64898/2026.04.09.26350519},
  url    = {https://www.medrxiv.org/content/10.64898/2026.04.09.26350519v1}
}
```

## Status

Research prototype. It demonstrates the layer end to end with reproducible experiments; it is not a certified medical device or a production security product. Threat-model boundaries and known gaps are in the paper's Discussion.

## License

Apache License 2.0 — see [LICENSE](LICENSE). Copyright (c) 2026 Quome, Inc.
