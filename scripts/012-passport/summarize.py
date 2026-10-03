#!/usr/bin/env python3
"""Tables + figures for paper 012 from results/012-passport/e{1..5}_*.json.

E1 classification accuracy + Cohen's kappa + per-jurisdiction confusion (Fig 1);
E2 PCCP gating ROC/AUC + operating point (Fig 2); E3 cross-jurisdiction agreement
matrix (Fig 3); E4 fingerprint detection/localization by granularity (Fig 4);
E5 deployment-gate overhead (shared Fig). Rates use Wilson 95% CIs.
Deterministic. Run: python3 scripts/012-passport/summarize.py
"""
import json
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RES = "results/012-passport"
FIGS = "papers/012-passport/figs"
os.makedirs(FIGS, exist_ok=True)

JURIS = ["fda", "eu_ai_act", "health_canada", "mhra"]
JNAME = {"fda": "FDA", "eu_ai_act": "EU AI Act", "health_canada": "Health Canada", "mhra": "MHRA"}
RISK = ["minimal", "low", "moderate", "high"]


def load(name):
    with open(os.path.join(RES, name)) as f:
        return json.load(f)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))


def cohen_kappa(pairs):
    """pairs: list of (pred, truth) over the same label set."""
    labels = RISK
    idx = {l: i for i, l in enumerate(labels)}
    m = np.zeros((len(labels), len(labels)))
    for pr, tr in pairs:
        m[idx[pr], idx[tr]] += 1
    n = m.sum()
    if n == 0:
        return float("nan")
    po = np.trace(m) / n
    pe = sum((m[i, :].sum() / n) * (m[:, i].sum() / n) for i in range(len(labels)))
    return 1.0 if pe == 1.0 else (po - pe) / (1 - pe)


def roc_auc(scores, labels):
    """labels: 1 = positive (out-of-envelope). Returns (fpr, tpr, auc)."""
    order = np.argsort(-np.asarray(scores))
    s = np.asarray(scores)[order]
    y = np.asarray(labels)[order]
    P = y.sum()
    N = len(y) - P
    tpr, fpr = [0.0], [0.0]
    tp = fp = 0
    prev = None
    for si, yi in zip(s, y):
        if prev is not None and si != prev:
            tpr.append(tp / P if P else 0)
            fpr.append(fp / N if N else 0)
        tp += yi == 1
        fp += yi == 0
        prev = si
    tpr.append(tp / P if P else 0)
    fpr.append(fp / N if N else 0)
    auc = float(np.trapz(tpr, fpr))
    return fpr, tpr, auc


def summarize_e1():
    d = load("e1_classification.json")
    preds = d["predictions"]
    # overall + per-jurisdiction accuracy and kappa
    per = {}
    confus = {j: np.zeros((4, 4)) for j in JURIS}
    ridx = {r: i for i, r in enumerate(RISK)}
    for p in preds:
        j = p["jurisdiction"]
        confus[j][ridx[p["predicted"]], ridx[p["truth"]]] += 1
    for j in JURIS:
        rows = [p for p in preds if p["jurisdiction"] == j]
        k = sum(p["correct"] for p in rows)
        acc, lo, hi = wilson(k, len(rows))
        kap = cohen_kappa([(p["predicted"], p["truth"]) for p in rows])
        per[j] = {"acc": acc, "ci": [lo, hi], "kappa": kap, "n": len(rows)}
    kall = sum(p["correct"] for p in preds)
    overall = wilson(kall, len(preds))
    # boundary vs clear
    b = [p for p in preds if p["stratum"] == "boundary"]
    c = [p for p in preds if p["stratum"] == "clear"]
    bstat = wilson(sum(p["correct"] for p in b), len(b))
    cstat = wilson(sum(p["correct"] for p in c), len(c))

    # Fig 1 — per-jurisdiction confusion grid
    fig, axes = plt.subplots(1, 4, figsize=(13, 3.4))
    for ax, j in zip(axes, JURIS):
        ax.imshow(confus[j], cmap="Blues")
        ax.set_xticks(range(4)); ax.set_yticks(range(4))
        ax.set_xticklabels(RISK, rotation=45, ha="right", fontsize=7)
        ax.set_yticklabels(RISK, fontsize=7)
        for x in range(4):
            for y in range(4):
                v = int(confus[j][y, x])
                if v:
                    ax.text(x, y, v, ha="center", va="center", fontsize=7,
                            color="white" if v > confus[j].max() / 2 else "black")
        ax.set_title(f"{JNAME[j]}\n$\\kappa$={per[j]['kappa']:.2f}", fontsize=9)
        ax.set_xlabel("ground truth", fontsize=7)
    axes[0].set_ylabel("predicted", fontsize=8)
    fig.suptitle("E1 — risk classification vs framework-grounded labels (rows=predicted, cols=truth)", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "fig1_classification.pdf"))
    plt.close(fig)

    return {"overall_acc": overall[0], "overall_ci": [overall[1], overall[2]],
            "per_jurisdiction": per, "boundary_acc": bstat[0], "clear_acc": cstat[0],
            "n_boundary": len(b), "n_clear": len(c)}


def summarize_e2():
    d = load("e2_pccp.json")
    rows = d["rows"]
    scores = [r["score"] for r in rows]
    labels = [1 if r["true_out"] else 0 for r in rows]
    fpr, tpr, auc = roc_auc(scores, labels)
    # operating point = the gate's actual decision (estimated magnitude vs bound)
    tp = sum(1 for r in rows if r["true_out"] and r["predicted_out"])
    fn = sum(1 for r in rows if r["true_out"] and not r["predicted_out"])
    fp = sum(1 for r in rows if not r["true_out"] and r["predicted_out"])
    tn = sum(1 for r in rows if not r["true_out"] and not r["predicted_out"])
    pgd = wilson(tp, tp + fn)            # out-of-envelope detection rate
    ft = wilson(fp, fp + tn)             # in-envelope false-trigger rate

    fig, ax = plt.subplots(figsize=(4.6, 4.2))
    ax.plot(fpr, tpr, "-", lw=2, label=f"PCCP gate (AUC={auc:.3f})")
    ax.plot([0, 1], [0, 1], "k--", lw=0.8, alpha=0.5)
    ax.scatter([ft[0]], [pgd[0]], color="crimson", zorder=5,
               label=f"operating point\nPGD={pgd[0]:.3f}, FT={ft[0]:.3f}")
    ax.set_xlabel("in-envelope false-trigger rate")
    ax.set_ylabel("out-of-envelope detection rate")
    ax.set_title("E2 — PCCP change-gating ROC")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "fig2_pccp_roc.pdf"))
    plt.close(fig)

    return {"auc": auc, "pgd": pgd[0], "pgd_ci": [pgd[1], pgd[2]],
            "ft": ft[0], "ft_ci": [ft[1], ft[2]], "tp": tp, "fn": fn, "fp": fp, "tn": tn}


def summarize_e3():
    d = load("e3_harmonization.json")
    mat = np.eye(4)
    rate = {(JNAME_inv(p["pair"].split("|")[0]), JNAME_inv(p["pair"].split("|")[1])): p["rate"]
            for p in d["pairwise_matrix"]}
    for (a, b), r in rate.items():
        ia, ib = JURIS.index(a), JURIS.index(b)
        mat[ia, ib] = mat[ib, ia] = r

    fig, ax = plt.subplots(figsize=(4.6, 4.0))
    im = ax.imshow(mat, cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks(range(4)); ax.set_yticks(range(4))
    ax.set_xticklabels([JNAME[j] for j in JURIS], rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels([JNAME[j] for j in JURIS], fontsize=8)
    for x in range(4):
        for y in range(4):
            ax.text(x, y, f"{mat[y, x]:.2f}", ha="center", va="center", fontsize=8)
    ax.set_title(f"E3 — cross-jurisdiction risk agreement\nHCA={d['mean_agreement']:.3f}, "
                 f"all divergences explained={d['all_divergences_explained']}")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "fig3_harmonization.pdf"))
    plt.close(fig)

    return {"hca": d["mean_agreement"], "total_divergences": d["total_divergences"],
            "all_explained": d["all_divergences_explained"]}


def JNAME_inv(name):
    for k, v in JNAME.items():
        if v == name:
            return k
    raise KeyError(name)


def summarize_e4():
    d = load("e4_fingerprint.json")
    rows = d["rows"]
    ks = sorted(set(r["k"] for r in rows))
    comp_det, comp_loc, whole_loc = [], [], []
    for k in ks:
        rk = [r for r in rows if r["k"] == k]
        comp_det.append(np.mean([r["component_detected"] for r in rk]))
        comp_loc.append(np.mean([r["component_localized"] for r in rk]))
        whole_loc.append(np.mean([r["whole_localized"] for r in rk]))
    cfd = np.mean([r["component_detected"] for r in rows])
    cloc = np.mean([r["component_localized"] for r in rows])

    fig, ax = plt.subplots(figsize=(5.0, 3.6))
    x = np.arange(len(ks)); w = 0.27
    ax.bar(x - w, comp_det, w, label="per-component: detect")
    ax.bar(x, comp_loc, w, label="per-component: localize")
    ax.bar(x + w, whole_loc, w, label="whole-config: localize")
    ax.set_xticks(x); ax.set_xticklabels([f"{k}-comp" for k in ks])
    ax.set_ylim(0, 1.08); ax.set_ylabel("rate")
    ax.set_xlabel("change granularity (components changed)")
    ax.set_title("E4 — fingerprint detection vs localization")
    ax.legend(fontsize=8, loc="center right")
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "fig4_fingerprint.pdf"))
    plt.close(fig)

    return {"cfd": float(cfd), "component_localization": float(cloc),
            "whole_localization": float(np.mean(whole_loc))}


def summarize_e5():
    d = load("e5_overhead.json")
    fig, ax = plt.subplots(figsize=(4.2, 3.2))
    ax.bar(["median", "p95"], [d["median_us"], d["p95_us"]], color=["#4C72B0", "#C44E52"])
    ax.set_ylabel("µs per deployment-gate")
    ax.set_title(f"E5 — gate overhead ({d['gates_per_sec']:.0f} gates/s)")
    for i, v in enumerate([d["median_us"], d["p95_us"]]):
        ax.text(i, v, f"{v:.1f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "fig5_overhead.pdf"))
    plt.close(fig)
    return {"median_us": d["median_us"], "p95_us": d["p95_us"], "gates_per_sec": d["gates_per_sec"]}


def main():
    s = {"E1": summarize_e1(), "E2": summarize_e2(), "E3": summarize_e3(),
         "E4": summarize_e4(), "E5": summarize_e5()}
    with open(os.path.join(RES, "summary.json"), "w") as f:
        json.dump(s, f, indent=2)

    print("\n=== PassportBench headline (paper 012) ===")
    print(f"E1 CLA      : {s['E1']['overall_acc']:.3f}  CI{[round(x,3) for x in s['E1']['overall_ci']]}"
          f"  (clear {s['E1']['clear_acc']:.3f}, boundary {s['E1']['boundary_acc']:.3f})")
    print("   per-jurisdiction kappa:",
          {JNAME[j]: round(s["E1"]["per_jurisdiction"][j]["kappa"], 3) for j in JURIS})
    print(f"E2 PCCP     : AUC {s['E2']['auc']:.3f}  PGD {s['E2']['pgd']:.3f} "
          f"CI{[round(x,3) for x in s['E2']['pgd_ci']]}  FT {s['E2']['ft']:.3f} "
          f"CI{[round(x,3) for x in s['E2']['ft_ci']]}")
    print(f"E3 HCA      : {s['E3']['hca']:.3f}  ({s['E3']['total_divergences']} divergences, "
          f"all explained={s['E3']['all_explained']})")
    print(f"E4 CFD      : {s['E4']['cfd']:.3f}  localization per-comp {s['E4']['component_localization']:.3f} "
          f"vs whole-config {s['E4']['whole_localization']:.3f}")
    print(f"E5 overhead : {s['E5']['median_us']:.2f}µs median, {s['E5']['p95_us']:.2f}µs p95, "
          f"{s['E5']['gates_per_sec']:.0f} gates/s")
    print(f"\nfigures → {FIGS}/  ·  summary → {RES}/summary.json")


if __name__ == "__main__":
    main()
