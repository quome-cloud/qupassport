#!/usr/bin/env python3
"""PassportBench generator (paper 012 — the regulatory passport).

Deterministic (seed 42), synthetic, stdlib-only, no network, Apache-2.0. Emits:

  datasets/012-passport/passports/passports.jsonl   E1 (classification) + E3 (harmonize)
  datasets/012-passport/changes/changes.jsonl       E2 (PCCP gating) + E4 (fingerprint)
  datasets/012-passport/pccp/schema.json             machine-readable PCCP schema
  datasets/012-passport/pccp/examples.jsonl          example plans
  datasets/012-passport/README.md                    provenance + label methodology

Honesty boundary (read the README): the per-jurisdiction ground-truth labels are
*author-encoded from published regulatory criteria*, NOT a live multi-rater expert
panel. This generator is an INDEPENDENT Python re-statement of the same primary
sources the Rust classifier encodes; E1 therefore measures cross-implementation
reproducibility of documented criteria. A predicate-defined "boundary" stratum
(the genuinely contested FDA non-device CDS carve-out for *serious* conditions)
carries a documented stricter expert interpretation, so the mechanical classifier
diverges there in an explainable direction — the source of any sub-100% accuracy.
No counts are tuned to hit a target; strata are defined by objective predicates and
whatever number results is what we report.
"""

import hashlib
import json
import os
import random

SEED = 42
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT = os.path.normpath(os.path.join(ROOT, "datasets", "012-passport"))

TASKS = ["inform", "drive", "diagnose", "treat"]
OUTPUTS = ["information", "recommendation", "action"]
AUTONOMY = ["informational", "advisory", "supervised", "autonomous"]
SEVERITY = ["non_serious", "serious", "critical"]
JURISDICTIONS = ["fda", "eu_ai_act", "health_canada", "mhra"]
RISK_ORDER = ["minimal", "low", "moderate", "high"]
AUT_TIER = {"informational": 0, "advisory": 1, "supervised": 2, "autonomous": 3}

TOOL_POOL = [
    "vitals_lookup", "ews_score", "order_entry", "note_writer", "guideline_rag",
    "lab_query", "imaging_view", "med_reconcile", "alert_push", "scheduler",
]


# ── mechanical criteria (independent Python re-statement of the Rust classifier) ──

def imdrf_spine(task, sev):
    """IMDRF SaMD WG/N12 risk category → framework-agnostic spine class."""
    grid = {
        ("treat", "critical"): "high", ("treat", "serious"): "moderate", ("treat", "non_serious"): "low",
        ("diagnose", "critical"): "high", ("diagnose", "serious"): "moderate", ("diagnose", "non_serious"): "low",
        ("drive", "critical"): "moderate", ("drive", "serious"): "low", ("drive", "non_serious"): "minimal",
        ("inform", "critical"): "low", ("inform", "serious"): "minimal", ("inform", "non_serious"): "minimal",
    }
    return grid[(task, sev)]


def fda_cds_carveout(m):
    return (m["clinical_task"] in ("inform", "drive")
            and m["output_type"] != "action"
            and not m["patient_facing"]
            and m["condition_severity"] != "critical")


def mechanical_risk(m, j):
    base = imdrf_spine(m["clinical_task"], m["condition_severity"])
    bi = RISK_ORDER.index(base)
    if j == "health_canada":
        return base
    if j == "fda":
        if fda_cds_carveout(m) and bi > 0:
            return "minimal"
        return base
    if j == "eu_ai_act":
        annex_iii = m["clinical_task"] in ("diagnose", "treat") or m["output_type"] == "action"
        if annex_iii and bi < 3:
            return "high"
        return base
    if j == "mhra":
        pf_decision = m["patient_facing"] and m["clinical_task"] in ("drive", "diagnose", "treat")
        if pf_decision and bi < 2:
            return "low" if base == "minimal" else "moderate"
        return base
    raise ValueError(j)


def mechanical_autonomy(m, risk):
    declared = m["autonomy"]
    ceiling = "supervised" if (m["output_type"] == "action" and risk == "high") else "autonomous"
    if AUT_TIER[declared] > AUT_TIER[ceiling]:
        return ceiling
    return declared


# ── expert interpretation: the documented boundary override ──

def is_boundary(m):
    """The genuinely contested zone: FDA non-device CDS carve-out applied to a
    *serious* (not minor) condition. FDA CDS guidance examples treat serious-
    condition decision support as a case-by-case judgement, so an expert reviewer
    does not automatically grant the carve-out here."""
    return fda_cds_carveout(m) and m["condition_severity"] == "serious"


def expert_risk(m, j):
    """Ground-truth label = mechanical criteria, except on the boundary stratum the
    expert declines the FDA carve-out (keeps the IMDRF spine). Documented, cited."""
    if j == "fda" and is_boundary(m):
        return imdrf_spine(m["clinical_task"], m["condition_severity"])  # no carve-out
    return mechanical_risk(m, j)


# ── coherent metadata grid ──

def coherent(task, output, autonomy):
    if output == "information" and autonomy != "informational":
        return False
    if output == "action" and autonomy in ("informational", "advisory"):
        return False
    if task == "inform" and output == "action":
        return False
    if task == "treat" and output == "information":
        return False
    return True


def gen_passports(rng):
    records = []
    pid = 0
    for task in TASKS:
        for output in OUTPUTS:
            for autonomy in AUTONOMY:
                if not coherent(task, output, autonomy):
                    continue
                for sev in SEVERITY:
                    for pf in (False, True):
                        m = {
                            "intended_use": f"{task} agent for {sev} conditions",
                            "clinical_task": task,
                            "output_type": output,
                            "autonomy": autonomy,
                            "condition_severity": sev,
                            "patient_facing": pf,
                            "tools": rng.sample(TOOL_POOL, rng.randint(1, 3)),
                        }
                        labels = {}
                        for j in JURISDICTIONS:
                            r = expert_risk(m, j)
                            labels[j] = {"risk_class": r, "autonomy_level": mechanical_autonomy(m, r)}
                        records.append({
                            "id": f"pp-{pid:04d}",
                            "metadata": m,
                            "stratum": "boundary" if is_boundary(m) else "clear",
                            "labels": labels,
                        })
                        pid += 1
    return records


# ── change-events for E2 (PCCP gating) + E4 (fingerprint) ──

def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def gen_changes(rng):
    """Each event: a deployed fingerprint, a live fingerprint differing in one or
    more components, a PCCP, the TRUE in/out-of-envelope label, and a NOISY
    admission-time magnitude estimate (admission knows a component changed, not by
    exactly how much). E2's ROC sweeps the estimate vs the bound."""
    comps = ["weights", "prompt", "tools", "data"]
    events = []
    for i in range(400):
        deployed = {c: sha(f"{c}-base-{i}") for c in comps}
        # PCCP: prompt free, weights bounded@0.05, tools+data forbidden (a typical plan).
        pccp = {
            "allowed": [
                {"component": "prompt", "policy": "any_change"},
                {"component": "weights", "policy": "bounded_magnitude", "max_fraction": 0.05},
            ]
        }
        # choose 1..3 components to change
        k = rng.choice([1, 1, 1, 2, 2, 3])
        changed = rng.sample(comps, k)
        live = dict(deployed)
        true_out = False
        deltas = []
        for c in changed:
            live[c] = sha(f"{c}-changed-{i}-{rng.random()}")
            mag = None
            if c == "weights":
                true_mag = round(rng.uniform(0.0, 0.12), 4)  # spans the 0.05 bound
                # admission-time estimate: true + gaussian noise, clipped to [0,1]
                est = min(1.0, max(0.0, true_mag + rng.gauss(0, 0.015)))
                mag = {"true": true_mag, "est": round(est, 4)}
                if true_mag > 0.05:
                    true_out = True
            elif c == "prompt":
                pass  # any_change ⇒ never a violation
            else:  # tools / data unlisted ⇒ forbidden by default
                true_out = True
            deltas.append({"component": c, "magnitude": mag})
        events.append({
            "id": f"ch-{i:04d}",
            "deployed_fingerprint": deployed,
            "live_fingerprint": live,
            "pccp": pccp,
            "deltas": deltas,
            "changed_components": changed,
            "true_out_of_envelope": true_out,
        })
    return events


PCCP_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "QUOKKAGUARD PCCP (Predetermined Change Control Plan)",
    "type": "object",
    "required": ["allowed"],
    "properties": {
        "allowed": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["component", "policy"],
                "properties": {
                    "component": {"enum": ["weights", "prompt", "tools", "data"]},
                    "policy": {"enum": ["forbidden", "any_change", "bounded_magnitude"]},
                    "max_fraction": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        }
    },
}

PCCP_EXAMPLES = [
    {"name": "prompt-only-tuning", "allowed": [{"component": "prompt", "policy": "any_change"}]},
    {"name": "bounded-weight-refresh", "allowed": [
        {"component": "prompt", "policy": "any_change"},
        {"component": "weights", "policy": "bounded_magnitude", "max_fraction": 0.05}]},
    {"name": "frozen", "allowed": []},
]


def write_jsonl(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")


def main():
    rng = random.Random(SEED)
    os.makedirs(os.path.join(OUT, "passports"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "changes"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "pccp"), exist_ok=True)

    passports = gen_passports(rng)
    changes = gen_changes(rng)

    write_jsonl(os.path.join(OUT, "passports", "passports.jsonl"), passports)
    write_jsonl(os.path.join(OUT, "changes", "changes.jsonl"), changes)
    with open(os.path.join(OUT, "pccp", "schema.json"), "w") as f:
        json.dump(PCCP_SCHEMA, f, indent=2, sort_keys=True)
    write_jsonl(os.path.join(OUT, "pccp", "examples.jsonl"), PCCP_EXAMPLES)

    n_boundary = sum(1 for p in passports if p["stratum"] == "boundary")
    n_out = sum(1 for c in changes if c["true_out_of_envelope"])
    print(f"passports: {len(passports)} ({n_boundary} boundary, {len(passports)-n_boundary} clear)")
    print(f"changes:   {len(changes)} ({n_out} out-of-envelope, {len(changes)-n_out} in-envelope)")
    print(f"written under {OUT}")


if __name__ == "__main__":
    main()
