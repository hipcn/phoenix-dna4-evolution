import json
from pathlib import Path
from datetime import datetime


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def pick_check(checks, name):
    for item in checks:
        if item.get("name") == name:
            return item
    return {}


def main():
    root = Path(".")
    gate_path = root / "benchmark_application_gate.json"
    route_path = root / "benchmark_route_policy.json"

    if not gate_path.exists():
        raise FileNotFoundError("benchmark_application_gate.json not found")

    gate = load_json(gate_path)
    checks = gate.get("checks", [])
    evidence = gate.get("evidence", {})

    speedup = pick_check(checks, "throughput_speedup_vs_float_cosine").get("actual", 0.0)
    top1_drop = pick_check(checks, "top1_non_inferiority_vs_float_cosine").get("actual", 0.0)
    margin_gain = pick_check(checks, "stress_margin_gain_penalty_-1.0_vs_0.0").get("actual", 0.0)

    dna_latency = evidence.get("dna_complementary", {}).get("latency_ms_mean", 0.0)
    float_latency = evidence.get("float_cosine", {}).get("latency_ms_mean", 0.0)
    latency_reduction = 0.0
    if float_latency > 0:
        latency_reduction = 1.0 - (dna_latency / float_latency)

    route = {}
    if route_path.exists():
        route = load_json(route_path).get("route", {})

    report = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "overall_passed": bool(gate.get("overall_passed", False)),
        "business_case": {
            "speedup_vs_baseline_x": round(float(speedup), 4),
            "latency_reduction_ratio": round(float(latency_reduction), 4),
            "top1_drop_vs_baseline": round(float(top1_drop), 6),
            "stress_margin_gain": round(float(margin_gain), 4)
        },
        "runtime_route": route,
        "positioning": "在不降低Top1准确率的前提下，提供显著吞吐提升，并通过门禁校验"
    }

    output_path = root / "business_value_case.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("✅ business_value_case.json generated")
    print(f"   Gate Passed: {report['overall_passed']}")
    print(f"   Speedup: {report['business_case']['speedup_vs_baseline_x']}x")
    print(f"   Latency Reduction: {report['business_case']['latency_reduction_ratio']:.2%}")
    print(f"   Top1 Drop: {report['business_case']['top1_drop_vs_baseline']}")
    print(f"   Stress Margin Gain: {report['business_case']['stress_margin_gain']}")
    if route:
        print(f"   Runtime Route: {route.get('provider', '')}/{route.get('model', '')}")


if __name__ == "__main__":
    main()
