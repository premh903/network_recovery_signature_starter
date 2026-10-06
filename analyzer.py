import csv
import statistics
from typing import Optional

import matplotlib.pyplot as plt


INPUT_FILE = "results_delay_2.csv"

BASELINE_END = 20.0
IMPAIRMENT_END = 40.0

WINDOW_SIZE = 5.0

# How far a metric may deviate from its baseline
# and still be considered "recovered".
RTT_TOLERANCE = 0.20       # ±20%
LOSS_TOLERANCE = 0.01      # ±1 percentage point
JITTER_TOLERANCE = 0.20    # ±20%

MIN_IMPAIRMENT_MULTIPLIER = 1.20


def load_results():
    rows = []

    with open(INPUT_FILE, newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            status = row["status"]

            rows.append({
                "time": float(row["time_s"]),
                "rtt": float(row["rtt_ms"]) if status == "ok" else None,
                "ok": status == "ok"
            })

    return rows


def make_windows(rows):
    windows = []

    start = 0.0

    while start < 90.0:
        end = start + WINDOW_SIZE

        window = [
            r for r in rows
            if start <= r["time"] < end
        ]

        total = len(window)
        successful = [
            r for r in window
            if r["ok"]
        ]

        if total > 0:
            loss_rate = 1.0 - (
                len(successful) / total
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
                "end": end,
                "phase": phase,
                "loss": loss_rate,
                "rtt": median_rtt,
                "jitter": jitter
            })

        start += WINDOW_SIZE

    return windows


def median(values) -> Optional[float]:
    values = [
        v for v in values
        if v is not None
    ]

    if not values:
        return None

    return float(statistics.median(values))


def is_impaired(
    metric: str,
    value: Optional[float],
    baseline: Optional[float]
) -> bool:

    if value is None or baseline is None:
        return False

    if metric == "rtt":
        return value > (
            baseline * MIN_IMPAIRMENT_MULTIPLIER
        )

    if metric == "loss":
        return value > max(
            baseline + LOSS_TOLERANCE,
            0.01
        )

    if metric == "jitter":
        return value > (
            baseline * MIN_IMPAIRMENT_MULTIPLIER
        )

    return False


def recovered(
    metric: str,
    value: Optional[float],
    baseline: Optional[float]
) -> bool:

    if value is None or baseline is None:
        return False

    if metric == "rtt":
        lower = baseline * (
            1 - RTT_TOLERANCE
        )

        upper = baseline * (
            1 + RTT_TOLERANCE
        )

        return lower <= value <= upper

    if metric == "loss":
        return value <= (
            baseline + LOSS_TOLERANCE
        )

    if metric == "jitter":

        # If baseline jitter is zero, percentage-based
        # recovery cannot be calculated meaningfully.
        if baseline == 0:
            return value == 0

        lower = baseline * (
            1 - JITTER_TOLERANCE
        )

        upper = baseline * (
            1 + JITTER_TOLERANCE
        )

        return lower <= value <= upper

    return False


def recovery_time(
    metric: str,
    windows,
    baseline: Optional[float]
) -> Optional[float]:

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
        is_impaired(
            metric,
            value,
            baseline
        )
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
            # Recovery is confirmed when the second
            # consecutive recovered window ends.
            return float(
                second["end"] - IMPAIRMENT_END
            )

    return None


def save_window_metrics(windows):

    output = "window_metrics.csv"

    with open(output, "w", newline="") as f:

        writer = csv.writer(f)

        writer.writerow([
            "window_start_s",
            "window_end_s",
            "phase",
            "loss_rate",
            "median_rtt_ms",
            "jitter_ms"
        ])

        for w in windows:

            writer.writerow([
                f"{w['start']:.1f}",
                f"{w['end']:.1f}",
                w["phase"],
                f"{w['loss']:.4f}",
                (
                    ""
                    if w["rtt"] is None
                    else f"{w['rtt']:.3f}"
                ),
                (
                    ""
                    if w["jitter"] is None
                    else f"{w['jitter']:.3f}"
                )
            ])


def save_recovery_graphs(windows):

    times = [
        w["start"]
        for w in windows
    ]

    # -------------------------
    # RTT GRAPH
    # -------------------------

    rtt_values = [
        w["rtt"]
        for w in windows
    ]

    plt.figure(figsize=(10, 5))

    plt.plot(
        times,
        rtt_values,
        marker="o",
        markersize=3,
        color="steelblue",
        label="Median RTT"
    )

    plt.axvline(
        BASELINE_END,
        color="green",
        linestyle="--",
        label="Impairment starts"
    )

    plt.axvline(
        IMPAIRMENT_END,
        color="red",
        linestyle="--",
        label="Recovery starts"
    )

    plt.xlabel("Time (s)")
    plt.ylabel("RTT (ms)")
    plt.title("RTT Recovery")
    plt.legend()
    plt.grid(True, alpha=0.3)

    plt.tight_layout()

    plt.savefig(
        "rtt_recovery.png",
        dpi=300,
        bbox_inches="tight"
    )

    plt.close()

    # -------------------------
    # LOSS GRAPH
    # -------------------------

    loss_values = [
        w["loss"] * 100
        for w in windows
    ]

    plt.figure(figsize=(10, 5))

    plt.plot(
        times,
        loss_values,
        marker="o",
        markersize=3,
        color="orange",
        label="Packet Loss"
    )

    plt.axvline(
        BASELINE_END,
        color="green",
        linestyle="--",
        label="Impairment starts"
    )

    plt.axvline(
        IMPAIRMENT_END,
        color="red",
        linestyle="--",
        label="Recovery starts"
    )

    plt.xlabel("Time (s)")
    plt.ylabel("Packet Loss (%)")
    plt.title("Packet Loss Recovery")
    plt.legend()
    plt.grid(True, alpha=0.3)

    plt.tight_layout()

    plt.savefig(
        "loss_recovery.png",
        dpi=300,
        bbox_inches="tight"
    )

    plt.close()

    # -------------------------
    # JITTER GRAPH
    # -------------------------

    jitter_values = [
        w["jitter"]
        for w in windows
    ]

    plt.figure(figsize=(10, 5))

    plt.plot(
        times,
        jitter_values,
        marker="o",
        markersize=3,
        color="seagreen",
        label="RTT Jitter"
    )

    plt.axvline(
        BASELINE_END,
        color="green",
        linestyle="--",
        label="Impairment starts"
    )

    plt.axvline(
        IMPAIRMENT_END,
        color="red",
        linestyle="--",
        label="Recovery starts"
    )

    plt.xlabel("Time (s)")
    plt.ylabel("Jitter (ms)")
    plt.title("Jitter Recovery")
    plt.legend()
    plt.grid(True, alpha=0.3)

    plt.tight_layout()

    plt.savefig(
        "jitter_recovery.png",
        dpi=300,
        bbox_inches="tight"
    )

    plt.close()

    print()
    print("Saved graphs:")
    print("  rtt_recovery.png")
    print("  loss_recovery.png")
    print("  jitter_recovery.png")


def main():

    rows = load_results()

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

    rtt_recovery = recovery_time(
        "rtt",
        windows,
        baseline_rtt
    )

    loss_recovery = recovery_time(
        "loss",
        windows,
        baseline_loss
    )

    jitter_recovery = recovery_time(
        "jitter",
        windows,
        baseline_jitter
    )

    save_window_metrics(windows)
    save_recovery_graphs(windows)

    print()
    print("NETWORK RECOVERY SIGNATURE REPORT")
    print("=================================")

    if baseline_rtt is not None:
        print(
            f"Baseline median RTT: "
            f"{baseline_rtt:.3f} ms"
        )
    else:
        print("Baseline median RTT: N/A")

    if baseline_loss is not None:
        print(
            f"Baseline loss rate: "
            f"{baseline_loss * 100:.2f}%"
        )
    else:
        print("Baseline loss rate: N/A")

    if baseline_jitter is not None:
        print(
            f"Baseline RTT jitter: "
            f"{baseline_jitter:.3f} ms"
        )
    else:
        print("Baseline RTT jitter: N/A")

    print()
    print(
        "Recovery signature "
        "(time after impairment ended):"
    )

    if rtt_recovery is None:
        print(
            "RTT recovery time: "
            "N/A (not meaningfully impaired)"
        )
    else:
        print(
            f"RTT recovery time: "
            f"{rtt_recovery:.1f} s"
        )

    if loss_recovery is None:
        print(
            "Loss recovery time: "
            "N/A (not meaningfully impaired)"
        )
    else:
        print(
            f"Loss recovery time: "
            f"{loss_recovery:.1f} s"
        )

    if jitter_recovery is None:
        print(
            "Jitter recovery time: "
            "N/A (not meaningfully impaired)"
        )
    else:
        print(
            f"Jitter recovery time: "
            f"{jitter_recovery:.1f} s"
        )

    print()
    print("Saved: window_metrics.csv")


if __name__ == "__main__":
    main()
