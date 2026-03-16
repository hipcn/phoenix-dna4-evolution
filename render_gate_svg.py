import json
import argparse
from pathlib import Path


def load_gate(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def esc(text: str):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def main():
    parser = argparse.ArgumentParser(description="Render gate snapshot SVG from benchmark_application_gate.json")
    parser.add_argument("--input-dir", default=".", help="Directory containing benchmark_application_gate.json")
    parser.add_argument("--output-dir", default=".", help="Directory to write gate_snapshot.svg")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    gate_path = input_dir / "benchmark_application_gate.json"
    if not gate_path.exists():
        raise FileNotFoundError("benchmark_application_gate.json not found")

    gate = load_gate(gate_path)
    checks = gate.get("checks", [])
    if not checks:
        raise ValueError("No checks found in benchmark_application_gate.json")

    width = 980
    height = 360
    left = 260
    right = 920
    top = 70
    row_h = 78
    bar_h = 22
    track_w = right - left

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect x="0" y="0" width="100%" height="100%" fill="#0b1020"/>',
        '<text x="36" y="42" fill="#f2f5ff" font-size="24" font-family="Segoe UI, Arial">PhoenixDNA Gate Snapshot</text>'
    ]

    for i, check in enumerate(checks[:3]):
        y = top + i * row_h
        name = check.get("name", f"check_{i+1}")
        actual = float(check.get("actual", 0.0))
        threshold = float(check.get("threshold", 0.0))
        op = check.get("operator", ">=")
        passed = bool(check.get("passed", False))

        if op == "<=":
            scale = max(actual, threshold) if max(actual, threshold) > 0 else 1.0
            ratio = min(actual / scale, 1.0)
            threshold_ratio = min(threshold / scale, 1.0)
            good = "#35d07f" if passed else "#ff6b6b"
            bad = "#ff6b6b"
            bar_color = good
            threshold_color = bad
        else:
            scale = max(actual, threshold) if max(actual, threshold) > 0 else 1.0
            ratio = min(actual / scale, 1.0)
            threshold_ratio = min(threshold / scale, 1.0)
            bar_color = "#35d07f" if passed else "#ff6b6b"
            threshold_color = "#ffcc66"

        bar_w = track_w * ratio
        threshold_x = left + track_w * threshold_ratio
        status = "PASS" if passed else "FAIL"

        lines.append(f'<text x="36" y="{y + 16}" fill="#c8d1ee" font-size="14" font-family="Segoe UI, Arial">{esc(name)}</text>')
        lines.append(f'<rect x="{left}" y="{y}" width="{track_w}" height="{bar_h}" rx="6" fill="#1f2a44"/>')
        lines.append(f'<rect x="{left}" y="{y}" width="{bar_w:.2f}" height="{bar_h}" rx="6" fill="{bar_color}"/>')
        lines.append(f'<line x1="{threshold_x:.2f}" y1="{y - 6}" x2="{threshold_x:.2f}" y2="{y + bar_h + 6}" stroke="{threshold_color}" stroke-width="2"/>')
        lines.append(f'<text x="{left}" y="{y + 44}" fill="#9eb0df" font-size="12" font-family="Consolas, monospace">actual={actual:.4f}  threshold={threshold:.4f}  op={esc(op)}</text>')
        lines.append(f'<text x="{right + 12}" y="{y + 16}" fill="{bar_color}" font-size="13" font-family="Segoe UI, Arial">{status}</text>')

    overall = "PASS" if gate.get("overall_passed") else "FAIL"
    overall_color = "#35d07f" if overall == "PASS" else "#ff6b6b"
    lines.append(f'<text x="36" y="{height - 24}" fill="{overall_color}" font-size="16" font-family="Segoe UI, Arial">Overall Gate: {overall}</text>')
    lines.append("</svg>")

    svg_path = output_dir / "gate_snapshot.svg"
    svg_path.write_text("\n".join(lines), encoding="utf-8")
    print("✅ gate_snapshot.svg generated")


if __name__ == "__main__":
    main()
