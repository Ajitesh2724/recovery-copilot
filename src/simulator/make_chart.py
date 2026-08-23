import os
import sys
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ""))
from simulator.baseline import run as run_baseline
from simulator.sensitivity import SCENARIOS, run_scenario


def build():
    baseline_rate = run_baseline()["recovery_rate"] * 100
    scenario_rates = {name: run_scenario(name, params) * 100 for name, params in SCENARIOS.items()}

    labels = ["Naive\nbaseline", "Conservative", "Expected", "Optimistic"]
    values = [baseline_rate, scenario_rates["conservative"],
              scenario_rates["expected"], scenario_rates["optimistic"]]
    colors = ["#999999", "#7fb37f", "#3f8f3f", "#0a5c36"]

    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(labels, values, color=colors)

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 1, f"{val:.1f}%",
                ha="center", fontweight="bold")

    ax.set_ylabel("Recovery rate (%)")
    ax.set_title("Recovery Copilot vs. naive retry, across assumption scenarios")
    ax.set_ylim(0, max(values) + 10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    os.makedirs("docs", exist_ok=True)
    out_path = "docs/recovery_comparison.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"saved chart -> {out_path}")


if __name__ == "__main__":
    build()