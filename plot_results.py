import csv
import statistics
from pathlib import Path

import matplotlib.pyplot as plt


# ---------------------------------------------------------
# Experiment files
# ---------------------------------------------------------

EXPERIMENTS = {
    "Delay": "results_delay_3.csv",
    "Loss": "results_loss_1.csv",
    "Combined": "results_combined_1.csv",
}

BASELINE_END = 20.0
IMPAIRMENT_END = 40.0
WINDOW_SIZE = 5.0

RTT_TOLERANCE = 0.20
LOSS_TOLERANCE = 0.01
JITTER_TOLERANCE = 0.20

MIN_IMPAIRMENT_MULTIPLIER = 1.20


# ---------------------------------------------------------
# Load CSV
# ---------------------------------------------------------

def load_results(filename):

    rows = []

    with open(filename, newline="", encoding="utf-8") as f:

        reader = csv.DictReader(f)

        for row in reader:

            rows.append({
                "time": float(row["time_s"]),
                "rtt": (
                    float(row["rtt_ms"])
                    if row["status"] == "ok"
                    else None
                ),
                "ok": row["status"] == "ok"
            })

    return rows


# ---------------------------------------------------------
# Create 5-second windows
# ---------------------------------------------------------

def make_windows(rows):

    windows = []

    start = 0.0

    while start < 90.0:

        end = start + WINDOW_SIZE

        window = [
            r for r in rows
            if start <= r["time"] < end
        ]

        if window:

            successful = [
                r for r in window
                if r["ok"]
            ]

            loss_rate = (
                1.0 -
                len(successful) / len(window)
            )

            rtts = [
                r["rtt"]
                for r in successful
                if r["rtt"] is not None
            ]

            if rtts:

                median_rtt = statistics.median(rtts)

                if len(rtts) > 1:
                    jitter = statistics.stdev(rtts)
                else:
                    jitter = 0.0

            else:

                median_rtt = None
                jitter = None

            if start < BASELINE_END:
                phase = "baseline"

            elif start < IMPAIRMENT_END:
                phase = "impairment"

            else:
                phase = "recovery"

            windows.append({
                "start": start,
                "phase": phase,
                "loss": loss_rate,
                "rtt": median_rtt,
                "jitter": jitter
            })

        start += WINDOW_SIZE

    return windows


# ---------------------------------------------------------
# Median helper
# ---------------------------------------------------------

def median(values):

    values = [
        v for v in values
        if v is not None
    ]

    if not values:
        return None

    return statistics.median(values)


# ---------------------------------------------------------
# Check impairment
# ---------------------------------------------------------

def is_impaired(metric, value, baseline):

    if value is None or baseline is None:
        return False

    if metric == "rtt":
        return value > baseline * MIN_IMPAIRMENT_MULTIPLIER

    if metric == "loss":
        return value > max(
            baseline + LOSS_TOLERANCE,
            0.01
        )

    if metric == "jitter":
        return value > baseline * MIN_IMPAIRMENT_MULTIPLIER

    return False


# ---------------------------------------------------------
# Check recovery
# ---------------------------------------------------------

def recovered(metric, value, baseline):

    if value is None or baseline is None:
        return False

    if metric == "rtt":

        lower = baseline * (1 - RTT_TOLERANCE)
        upper = baseline * (1 + RTT_TOLERANCE)

        return lower <= value <= upper

    if metric == "loss":

        return value <= baseline + LOSS_TOLERANCE

    if metric == "jitter":

        lower = baseline * (1 - JITTER_TOLERANCE)
        upper = baseline * (1 + JITTER_TOLERANCE)

        return lower <= value <= upper

    return False


# ---------------------------------------------------------
# Calculate recovery time
# ---------------------------------------------------------

def recovery_time(metric, windows, baseline):

    impairment_windows = [
        w for w in windows
        if w["phase"] == "impairment"
    ]

    values = [
        w[metric]
        for w in impairment_windows
        if w[metric] is not None
    ]

    actually_impaired = any(
        is_impaired(metric, value, baseline)
        for value in values
    )

    if not actually_impaired:
        return None

    recovery_windows = [
        w for w in windows
        if w["phase"] == "recovery"
    ]

    # Require two consecutive recovered windows.
    for i in range(len(recovery_windows) - 1):

        first = recovery_windows[i]
        second = recovery_windows[i + 1]

        first_ok = recovered(
            metric,
            first[metric],
            baseline
        )

        second_ok = recovered(
            metric,
            second[metric],
            baseline
        )

        if first_ok and second_ok:

            return (
                first["start"]
                - IMPAIRMENT_END
                + WINDOW_SIZE
            )

    return None


# ---------------------------------------------------------
# Analyze one experiment
# ---------------------------------------------------------

def analyze(filename):

    rows = load_results(filename)

    windows = make_windows(rows)

    baseline_windows = [
        w for w in windows
        if w["phase"] == "baseline"
    ]

    baseline_rtt = median([
        w["rtt"]
        for w in baseline_windows
    ])

    baseline_loss = median([
        w["loss"]
        for w in baseline_windows
    ])

    baseline_jitter = median([
        w["jitter"]
        for w in baseline_windows
    ])

    rtt = recovery_time(
        "rtt",
        windows,
        baseline_rtt
    )

    loss = recovery_time(
        "loss",
        windows,
        baseline_loss
    )

    jitter = recovery_time(
        "jitter",
        windows,
        baseline_jitter
    )

    return rtt, loss, jitter


# ---------------------------------------------------------
# Analyze all experiments
# ---------------------------------------------------------

results = {}

for experiment, filename in EXPERIMENTS.items():

    if not Path(filename).exists():

        print(
            f"WARNING: {filename} not found."
        )

        results[experiment] = (
            None,
            None,
            None
        )

        continue

    results[experiment] = analyze(filename)


# ---------------------------------------------------------
# Print results
# ---------------------------------------------------------

print()
print("AUTOMATIC RECOVERY COMPARISON")
print("=============================")

for experiment, values in results.items():

    rtt, loss, jitter = values

    print()
    print(experiment)

    print(
        "  RTT recovery:",
        "N/A" if rtt is None else f"{rtt:.1f} s"
    )

    print(
        "  Loss recovery:",
        "N/A" if loss is None else f"{loss:.1f} s"
    )

    print(
        "  Jitter recovery:",
        "N/A" if jitter is None else f"{jitter:.1f} s"
    )


# ---------------------------------------------------------
# Prepare graph data
# ---------------------------------------------------------

experiments = list(EXPERIMENTS.keys())

rtt = [
    results[e][0]
    for e in experiments
]

loss = [
    results[e][1]
    for e in experiments
]

jitter = [
    results[e][2]
    for e in experiments
]


def graph_values(values):

    return [
        0 if value is None else value
        for value in values
    ]


# ---------------------------------------------------------
# Create graph
# ---------------------------------------------------------

fig, axes = plt.subplots(
    1,
    3,
    figsize=(13, 5)
)


# RTT
axes[0].bar(
    experiments,
    graph_values(rtt),
    color="steelblue"
)

axes[0].set_title("RTT Recovery")
axes[0].set_ylabel("Recovery Time (s)")

for i, value in enumerate(rtt):

    if value is None:

        axes[0].text(
            i,
            0.3,
            "N/A",
            ha="center",
            fontweight="bold"
        )


# Loss
axes[1].bar(
    experiments,
    graph_values(loss),
    color="orange"
)

axes[1].set_title("Loss Recovery")
axes[1].set_ylabel("Recovery Time (s)")

for i, value in enumerate(loss):

    if value is None:

        axes[1].text(
            i,
            0.3,
            "N/A",
            ha="center",
            fontweight="bold"
        )


# Jitter
axes[2].bar(
    experiments,
    graph_values(jitter),
    color="seagreen"
)

axes[2].set_title("Jitter Recovery")
axes[2].set_ylabel("Recovery Time (s)")

for i, value in enumerate(jitter):

    if value is None:

        axes[2].text(
            i,
            0.3,
            "N/A",
            ha="center",
            fontweight="bold"
        )


plt.suptitle(
    "Network Recovery Signature Comparison"
)

plt.tight_layout()

plt.savefig(
    "recovery_comparison.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()

print()
print("Saved: recovery_comparison.png")