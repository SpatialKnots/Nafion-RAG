"""Plot the explicitly post-hoc Table 4.5 transcription; no model/DB calls."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def main() -> None:
    output = Path(sys.argv[1])
    source = output / "report.json"
    rows = json.loads(source.read_bytes())["assistant_source_review"]["q1"]["rows"]
    fig, ax = plt.subplots(figsize=(11, 7.5))
    y = list(range(len(rows)))
    for offset, field, color, label in (
        (-0.18, "alpha_h", "#527b94", "H-Nafion"),
        (0.18, "alpha_li", "#db873c", "Li-Nafion"),
    ):
        values = [float(row[field]) for row in rows]
        bars = ax.barh([v + offset for v in y], values, height=0.31, color=color, label=label)
        ax.bar_label(bars, labels=[row[field] for row in rows], padding=4, fontsize=10)
    ax.set_yticks(y, [row["solvent"] for row in rows])
    ax.invert_yaxis()
    ax.set_xlim(0, 1.65)
    ax.set_xlabel("Степень набухания α = (m набухшей мембраны − m сухой) / m сухой")
    ax.set_title("H-Nafion → Li-Nafion: изменение зависит от растворителя", pad=38, loc="left")
    ax.legend(loc="lower right", bbox_to_anchor=(1, 1.01), ncol=2, frameon=False)
    ax.set_axisbelow(True)
    ax.grid(axis="x", alpha=0.18)
    ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.03, 0.035, "Источник: диссертация С. Д. Чернюк, табл. 4.5, с. 97; определение α — с. 55.\n"
             "Перенос данных и график — отдельная проверка ассистента; это не исходный ответ модели.", fontsize=9)
    fig.subplots_adjust(left=0.29, right=0.97, top=0.86, bottom=0.14)
    fig.savefig(output / "swelling_comparison.png", dpi=160)
    fig.savefig(output / "swelling_comparison.svg")
    plt.close(fig)
    (output / "plot_provenance.json").write_text(json.dumps({
        "source_report_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": sys.version, "matplotlib": matplotlib.__version__, "rows": len(rows),
        "origin": "assistant_posthoc_transcription_not_independent_gold",
        "temperature": "Table heading does not specify temperature; no temperature added to plot.",
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
