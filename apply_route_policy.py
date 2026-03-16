import json
import argparse
from pathlib import Path


def load_policy(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_policy_from_evolution(path: Path):
    data = load_policy(path)
    genome = str(data.get("best_individual", {}).get("genome", ""))
    if not genome:
        genome = str(data.get("peak_generation", {}).get("best_genome", ""))
    base = genome[0] if genome else "A"
    route_map = {
        "A": {"provider": "ollama", "model": "qwen2.5:latest"},
        "T": {"provider": "vllm", "model": "phoenix-soul-vl"},
        "C": {"provider": "sglang", "model": "phoenix-soul-vl"},
        "G": {"provider": "ollama", "model": "qwen2.5:latest"}
    }
    return {
        "genome": genome,
        "route": route_map.get(base, route_map["A"]),
        "source": "benchmark_evolution_report.json"
    }


def main():
    parser = argparse.ArgumentParser(description="Generate runtime route policy artifacts")
    parser.add_argument("--input-dir", default=".", help="Directory containing benchmark route/evolution reports")
    parser.add_argument("--output-dir", default=".", help="Directory to write route policy artifacts")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    policy_path = input_dir / "benchmark_route_policy.json"
    evolution_path = input_dir / "benchmark_evolution_report.json"

    if policy_path.exists():
        policy = load_policy(policy_path)
    elif evolution_path.exists():
        policy = build_policy_from_evolution(evolution_path)
    else:
        raise FileNotFoundError("benchmark_route_policy.json or benchmark_evolution_report.json not found")
    route = policy.get("route", {})
    provider = str(route.get("provider", "ollama"))
    model = str(route.get("model", "qwen2.5:latest"))
    genome = str(policy.get("genome", ""))

    env_payload = "\n".join(
        [
            f"PHOENIX_ROUTE_PROVIDER={provider}",
            f"PHOENIX_ROUTE_MODEL={model}",
            f"PHOENIX_ROUTE_GENOME={genome}"
        ]
    )

    ps1_payload = "\n".join(
        [
            f"$env:PHOENIX_ROUTE_PROVIDER = \"{provider}\"",
            f"$env:PHOENIX_ROUTE_MODEL = \"{model}\"",
            f"$env:PHOENIX_ROUTE_GENOME = \"{genome}\"",
            "Write-Host \"PhoenixDNA route policy applied\""
        ]
    )

    Path(output_dir / "route_policy.env").write_text(env_payload, encoding="utf-8")
    Path(output_dir / "apply_route_policy.ps1").write_text(ps1_payload, encoding="utf-8")

    summary = {
        "provider": provider,
        "model": model,
        "genome": genome,
        "source": str(policy.get("source", "benchmark_route_policy.json")),
        "artifacts": ["route_policy.env", "apply_route_policy.ps1"]
    }
    Path(output_dir / "route_policy_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("✅ route_policy.env generated")
    print("✅ apply_route_policy.ps1 generated")
    print("✅ route_policy_summary.json generated")
    print(f"   Route: {provider}/{model}")


if __name__ == "__main__":
    main()
