> **Paper 012 proposal — The regulatory passport.** Imported 2026-06-07 from the local
> outline `P8` (`ongoing-papers/papers/08-lifecycle-regulatory-passport/`). Read with the
> [`ROADMAP.md`](../ROADMAP.md) deltas in mind: **monorepo** — features are `qfire`
> modules, not `haarf-*` crates or spin-out repos — and **confidential-enclave**
> production deployment, validated locally on Ollama via the OpenAI-compatible
> bridge. The threat model, hypotheses, experiments, datasets, and figures below
> are the pre-registered working plan; they are reconciled against the gateway as
> built at the feature-spec (stage 2) and paper-spec (stage 4) gates.

---

# Paper 8 — The Regulatory Passport: Lifecycle & Change-Control Automation for Clinical AI Agents

**Crate:** `haarf-lifecycle` · **New dataset:** HAARF-Lifecycle · **Covers:** C1 (full), C6.1, C2.6 · **Status:** outline

## Abstract

HAARF Category 1 (Unified Risk & Lifecycle Assessment) is the framework's regulatory
backbone — risk classification, FDA 510(k) predicate analysis, Predetermined Change
Control Plans (PCCP), real-world evidence, and international harmonization — yet none of
it is operationalized in the harness. We build `haarf-lifecycle`, a machine-readable
**regulatory passport** for an agent: a versioned, signed artifact that classifies the
agent's risk and autonomy level (C6.1), encodes its PCCP, and gates deployment/changes
against it. We contribute **HAARF-Lifecycle**, a corpus of agent change-events and PCCP
scenarios with risk-class labels, and show automated change-control catches
out-of-envelope modifications that would otherwise require manual regulatory review.

## Stakeholders & expert-in-the-loop

The passport only earns regulatory trust if experts-in-the-loop shape its classification
rules, change envelopes, and gating logic so the artifact stays clinically grounded and
credible to reviewers:

- **Regulatory-affairs specialist (FDA SaMD / 510(k) / PCCP)** — defines what a valid
  passport must assert and what counts as an in-envelope change under real PCCP guidance.
- **Quality / QMS lead (ISO 13485 / IEC 62304)** — ensures passport versioning and
  change gating map onto auditable design-control and software-lifecycle records.
- **Clinical risk manager (ISO 14971)** — grounds the risk-class labels in actual harm
  analysis so autonomy levels reflect clinical consequence, not just metadata.
- **CMIO / clinical informaticist** — validates that intended-use and scope statements
  match how the agent is actually deployed in care workflows.
- **Health-law / regulatory counsel** — adjudicates harmonization drift (L4) and signs
  off on cross-jurisdiction classification divergences as documented, defensible findings.
- **MLOps / model-governance engineer** — wires change-fingerprinting and the deployment
  gate into CI/CD so out-of-envelope model/prompt/tool swaps cannot ship silently.
- **Frontline clinician** — stress-tests whether an assigned autonomy level matches the
  oversight they can realistically provide at the bedside, flagging mis-classification.

## Problem model

- **L1 Mis-classification** — agent deployed at wrong risk/autonomy level for its
  clinical impact.
- **L2 Silent scope creep** — a model/prompt/tool change pushes the agent outside its
  cleared intended use without re-review.
- **L3 PCCP violation** — a change exceeds the pre-authorized change envelope (PCCP) and
  should trigger re-submission, but ships anyway.
- **L4 Harmonization drift** — the same agent is classified inconsistently across FDA /
  EU AI Act / Health Canada / MHRA.

## Research questions

- **RQ1** Can risk + autonomy level be assigned reproducibly from declarative agent
  metadata, matching expert/regulatory classification?
- **RQ2** Can a machine-readable PCCP automatically distinguish in-envelope vs.
  out-of-envelope changes (L3)?
- **RQ3** Does cross-framework mapping (reusing `HAARF/1.0/mappings/`) produce
  consistent multi-jurisdiction classifications (L4)?
- **RQ4** What change-detection granularity (weights, prompt, tools, data) is needed to
  catch L2 scope creep?

## Hypotheses

- **H1** Rule-based classification from agent metadata matches expert risk/autonomy
  labels on ≥ 90% of HAARF-Lifecycle cases.
- **H2** Automated PCCP checking flags ≥ 95% of out-of-envelope changes with ≤ 5% false
  triggers on in-envelope changes.
- **H3** Cross-framework classification disagreements are ≤ 10% and every disagreement
  is explainable by a documented regulatory difference (a finding, not a bug).
- **H4** Component-level change fingerprinting detects 100% of tool/prompt/model swaps.

## Experiments → figures

- **E1 Classification accuracy (→ Fig 1):** predicted vs. expert risk/autonomy class;
  confusion matrix per jurisdiction.
- **E2 PCCP gating (→ Fig 2):** in/out-of-envelope detection ROC over change scenarios.
- **E3 Harmonization (→ Fig 3):** agreement matrix across FDA/EU/HC/MHRA classifications.
- **E4 Change-fingerprint sensitivity (→ Fig 4):** detection vs. change granularity.
- **E5 Passport overhead (→ shared Fig):** deployment-gate latency (off hot path).

## Datasets

**Public:**
- **FDA AI/ML-enabled device list** + **510(k) database** — real cleared-device
  metadata for predicate analysis and risk-class grounding.
- **EU AI Act Annex III** risk categories, **IMDRF GMLP**, **FDA PCCP guidance** —
  classification rule sources.
- **Existing `HAARF/1.0/mappings/`** — the 9 regulatory mapping JSONs reused as the
  cross-framework substrate.

**New — HAARF-Lifecycle (the contribution):**
- A set of synthetic **agent passports** spanning risk/autonomy levels with expert
  ground-truth classification under each jurisdiction.
- A **change-event corpus**: paired (before, after) agent configs labeled in-/out-of-
  envelope against an attached PCCP, covering weight, prompt, tool, and data changes.
- A machine-readable **PCCP schema** + example plans. Apache-2.0, synthetic.

## Validation & statistics

- Classification accuracy + Cohen's κ vs. expert labels; per-jurisdiction breakdown.
- PCCP gating ROC/AUC; false-trigger analysis.
- Inter-jurisdiction agreement with documented rationale for each divergence.
- **Threats to validity:** regulatory rules evolve (version-pin the rule set); expert
  labels are interpretive (multi-rater + κ).

## Rust components (`haarf-lifecycle`)

- **Passport artifact:** signed (Paper 2 chain) JSON/CBOR with risk class, autonomy
  level (C6.1), intended use, tool inventory, PCCP, and jurisdiction classifications.
- **Classifier:** deterministic rule engine (could reuse `haarf-policy`/Cedar) mapping
  metadata → risk/autonomy level per framework.
- **Change-fingerprinter:** content hashes of weights/prompt/tools/data; diff against
  the deployed passport; evaluate against PCCP envelope.
- **Deployment gate:** CI/CD admission control — an agent cannot start on the gateway
  unless a valid passport + (for changes) an in-envelope or re-reviewed PCCP exists.

## Server / proxy design

- Runs at **admission time**, not per-call: the gateway refuses to register an agent
  (links Paper 1 registry) whose passport is missing, expired, or whose live
  fingerprint diverges from the passport beyond the PCCP envelope.
- Passport version is stamped into every audit entry (Paper 2) for traceability (C2.6).

## Metrics

| Metric | Definition | Target |
|---|---|---|
| CLA | Classification accuracy vs. expert | ≥ 90% |
| PGD | PCCP out-of-envelope detection | ≥ 95% |
| HCA | Cross-jurisdiction agreement | ≥ 90% (else explained) |
| CFD | Change-fingerprint detection | 100% |

## Repo scaffold

```
haarf-lifecycle/
├── crates/haarf-lifecycle/         # passport + classifier + fingerprinter + gate
├── dataset/haarf-lifecycle/        # passports + change-events + PCCP schema
├── figures/
└── paper/
```
