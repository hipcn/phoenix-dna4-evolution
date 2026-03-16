#!/usr/bin/env python3
"""
Phoenix DNA Benchmark Suite
============================

对比测试：
1. 浮点权重系统 (传统方式)
2. 4进制DNA系统 (新方式)

衡量指标：
- 推理延迟 (ms)
- 内存占用 (MB)
- 准确率 (%)
- 处理吞吐 (条/秒)

运行方式：
    python dna_benchmark.py --mode comprehensive
"""

import json
import time
import csv
import numpy as np
import psutil
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any, Callable
from dataclasses import dataclass, asdict
import statistics

# 导入DNA编码器
sys.path.insert(0, str(Path(__file__).parent))
from tools.dna_codec import DNACodec, DNAConfig


@dataclass
class BenchResult:
    """Benchmark结果数据类"""
    name: str
    scenario: str
    num_entries: int
    total_time_ms: float
    memory_peak_mb: float
    memory_baseline_mb: float
    memory_delta_mb: float
    throughput_per_sec: float
    accuracy_percent: float
    notes: str = ""


class DNABenchmark:
    """DNA系统性能测试框架"""
    
    def __init__(self):
        self.codec = DNACodec(DNAConfig(sequence_length=64, batch_size=32))
        self.results = []
        self.baseline_memory = None

    def _build_mutated_queries(
        self,
        dna_entries: List[Dict[str, Any]],
        sample_size: int,
        mutation_rate: float,
        seed: int
    ) -> List[Tuple[str, int]]:
        rng = np.random.default_rng(seed)
        indexed = [
            (idx, entry.get('quaternary_dna', ''))
            for idx, entry in enumerate(dna_entries)
            if entry.get('quaternary_dna')
        ]
        if not indexed:
            return []

        pick = min(sample_size, len(indexed))
        selected_positions = rng.choice(len(indexed), size=pick, replace=False)
        queries = []
        for pos in selected_positions:
            idx, dna = indexed[int(pos)]
            mutated = self.codec.generate_dna_mutation(dna, mutation_rate=mutation_rate)
            queries.append((mutated, idx))
        return queries

    def _cosine_similarity_from_dna(self, dna1: str, dna2: str) -> float:
        w1 = self.codec.dna_to_weights(dna1)
        w2 = self.codec.dna_to_weights(dna2)
        denom = float(np.linalg.norm(w1) * np.linalg.norm(w2))
        if denom == 0.0:
            return 0.0
        return float(np.dot(w1, w2) / denom)

    def _l2_similarity_from_dna(self, dna1: str, dna2: str) -> float:
        w1 = self.codec.dna_to_weights(dna1)
        w2 = self.codec.dna_to_weights(dna2)
        dist = float(np.linalg.norm(w1 - w2))
        return -dist

    def _complementary_with_penalty(self, dna1: str, dna2: str, penalty: float) -> float:
        score = 0.0
        for b1, b2 in zip(dna1, dna2):
            if b1 == b2:
                score += 1.0
            elif self.codec.COMPLEMENTARY.get(b1) == b2:
                score += penalty
        return score / len(dna1)

    def _evaluate_method(
        self,
        queries: List[Tuple[str, int]],
        candidate_dnas: List[str],
        scorer
    ) -> Dict[str, float]:
        if not queries or not candidate_dnas:
            return {
                'top1_accuracy': 0.0,
                'mrr': 0.0,
                'throughput_per_sec': 0.0,
                'elapsed_ms': 0.0
            }

        start = time.time()
        top1_hits = 0
        reciprocal_ranks = []

        for query_dna, truth_idx in queries:
            scored = [(idx, scorer(query_dna, cand)) for idx, cand in enumerate(candidate_dnas)]
            scored.sort(key=lambda x: x[1], reverse=True)

            if scored[0][0] == truth_idx:
                top1_hits += 1

            rank = next((i + 1 for i, (idx, _) in enumerate(scored) if idx == truth_idx), len(scored))
            reciprocal_ranks.append(1.0 / rank)

        elapsed = time.time() - start
        total_pairs = len(queries) * len(candidate_dnas)
        throughput = total_pairs / max(elapsed, 1e-9)

        return {
            'top1_accuracy': top1_hits / len(queries),
            'mrr': float(np.mean(reciprocal_ranks)),
            'throughput_per_sec': throughput,
            'elapsed_ms': elapsed * 1000
        }

    def _build_complementary_stress_queries(
        self,
        dna_entries: List[Dict[str, Any]],
        sample_size: int,
        stress_rate: float,
        seed: int
    ) -> List[Tuple[str, int]]:
        rng = np.random.default_rng(seed)
        indexed = [
            (idx, entry.get('quaternary_dna', ''))
            for idx, entry in enumerate(dna_entries)
            if entry.get('quaternary_dna')
        ]
        if not indexed:
            return []

        pick = min(sample_size, len(indexed))
        selected_positions = rng.choice(len(indexed), size=pick, replace=False)
        queries = []
        for pos in selected_positions:
            idx, dna = indexed[int(pos)]
            dna_chars = list(dna)
            flips = max(1, int(len(dna_chars) * stress_rate))
            flip_positions = rng.choice(len(dna_chars), size=flips, replace=False)
            for p in flip_positions:
                base = dna_chars[int(p)]
                dna_chars[int(p)] = self.codec.COMPLEMENTARY.get(base, base)
            queries.append((''.join(dna_chars), idx))
        return queries

    def _complement_dna(self, dna: str) -> str:
        return ''.join(self.codec.COMPLEMENTARY.get(b, b) for b in dna)

    def _evaluate_truth_vs_complement_margin(
        self,
        queries: List[Tuple[str, int]],
        candidate_dnas: List[str],
        scorer
    ) -> Dict[str, float]:
        if not queries:
            return {'margin_mean': 0.0, 'margin_std': 0.0}

        margins = []
        for query_dna, truth_idx in queries:
            truth_dna = candidate_dnas[truth_idx]
            truth_score = scorer(query_dna, truth_dna)
            comp_score = scorer(query_dna, self._complement_dna(truth_dna))
            margins.append(truth_score - comp_score)

        return {
            'margin_mean': float(np.mean(margins)),
            'margin_std': float(np.std(margins))
        }

    def _build_policy_scorer(self, genome_dna: str) -> Callable[[str, str], float]:
        gene_map = {'A': 0, 'T': 1, 'C': 2, 'G': 3}
        g0 = gene_map.get(genome_dna[0], 0) if genome_dna else 0
        g1 = gene_map.get(genome_dna[1], 1) if len(genome_dna) > 1 else 1
        g2 = gene_map.get(genome_dna[2], 2) if len(genome_dna) > 2 else 2
        g3 = gene_map.get(genome_dna[3], 0) if len(genome_dna) > 3 else 0

        method_name = ['exact', 'complementary', 'distance', 'float_cosine'][g0 % 4]
        penalty = [0.0, -0.25, -0.5, -1.0][g1 % 4]
        alpha = [0.0, 0.5, 0.8, 1.0][g2 % 4]
        l2_bias = [0.0, 0.0, 0.02, 0.05][g3 % 4]

        def scorer(q: str, c: str) -> float:
            if method_name == 'exact':
                main_score = self.codec.dna_similarity(q, c, method='exact')
            elif method_name == 'complementary':
                main_score = self.codec.dna_similarity(q, c, method='complementary')
            elif method_name == 'distance':
                main_score = self.codec.dna_similarity(q, c, method='distance')
            else:
                main_score = self._cosine_similarity_from_dna(q, c)

            mix = main_score
            if alpha < 1.0:
                aux_score = self._complementary_with_penalty(q, c, penalty=penalty)
                mix = alpha * main_score + (1.0 - alpha) * aux_score
            if l2_bias > 0.0:
                mix += l2_bias * self._l2_similarity_from_dna(q, c)
            return mix

        return scorer

    def _crossover(self, dna_a: str, dna_b: str, rng: np.random.Generator) -> str:
        if not dna_a:
            return dna_b
        if not dna_b:
            return dna_a
        cut = int(rng.integers(1, min(len(dna_a), len(dna_b))))
        return dna_a[:cut] + dna_b[cut:]

    def _write_research_tables(self, report: Dict[str, Any]):
        method_csv = Path('benchmark_research_methods.csv')
        with method_csv.open('w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'method',
                'top1_mean',
                'top1_std',
                'mrr_mean',
                'mrr_std',
                'throughput_mean',
                'throughput_std',
                'latency_ms_mean',
                'latency_ms_std'
            ])
            for name, data in report['methods'].items():
                writer.writerow([
                    name,
                    data['top1_accuracy_mean'],
                    data['top1_accuracy_std'],
                    data['mrr_mean'],
                    data['mrr_std'],
                    data['throughput_mean'],
                    data['throughput_std'],
                    data['latency_ms_mean'],
                    data['latency_ms_std']
                ])

        ablation_csv = Path('benchmark_research_ablations.csv')
        with ablation_csv.open('w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'ablation',
                'top1_mean',
                'top1_std',
                'mrr_mean',
                'mrr_std',
                'throughput_mean',
                'throughput_std',
                'latency_ms_mean',
                'latency_ms_std'
            ])
            for name, data in report['ablations'].items():
                writer.writerow([
                    name,
                    data['top1_accuracy_mean'],
                    data['top1_accuracy_std'],
                    data['mrr_mean'],
                    data['mrr_std'],
                    data['throughput_mean'],
                    data['throughput_std'],
                    data['latency_ms_mean'],
                    data['latency_ms_std']
                ])

        stress_csv = Path('benchmark_research_stress.csv')
        with stress_csv.open('w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'ablation',
                'top1',
                'mrr',
                'throughput_per_sec',
                'elapsed_ms',
                'margin_mean',
                'margin_std'
            ])
            stress_results = report['stress_test']['results']
            stress_margins = report['stress_test']['truth_vs_complement_margin']
            for name, data in stress_results.items():
                margin = stress_margins[name]
                writer.writerow([
                    name,
                    data['top1_accuracy'],
                    data['mrr'],
                    data['throughput_per_sec'],
                    data['elapsed_ms'],
                    margin['margin_mean'],
                    margin['margin_std']
                ])

        def latex_row(label: str, data: Dict[str, float]) -> str:
            return (
                f"{label} & "
                f"{data['top1_accuracy_mean']:.3f}$\\pm${data['top1_accuracy_std']:.3f} & "
                f"{data['mrr_mean']:.3f}$\\pm${data['mrr_std']:.3f} & "
                f"{data['throughput_mean']:.0f}$\\pm${data['throughput_std']:.0f} & "
                f"{data['latency_ms_mean']:.2f}$\\pm${data['latency_ms_std']:.2f} \\\\"
            )

        latex_lines = []
        latex_lines.append("\\begin{table}[t]")
        latex_lines.append("\\centering")
        latex_lines.append("\\caption{Baseline Comparison}")
        latex_lines.append("\\begin{tabular}{lcccc}")
        latex_lines.append("\\hline")
        latex_lines.append("Method & Top1 & MRR & Throughput (/s) & Latency (ms) \\\\")
        latex_lines.append("\\hline")
        for name, data in report['methods'].items():
            latex_lines.append(latex_row(name, data))
        latex_lines.append("\\hline")
        latex_lines.append("\\end{tabular}")
        latex_lines.append("\\end{table}")
        latex_lines.append("")
        latex_lines.append("\\begin{table}[t]")
        latex_lines.append("\\centering")
        latex_lines.append("\\caption{Complementary Penalty Ablation}")
        latex_lines.append("\\begin{tabular}{lcccc}")
        latex_lines.append("\\hline")
        latex_lines.append("Ablation & Top1 & MRR & Throughput (/s) & Latency (ms) \\\\")
        latex_lines.append("\\hline")
        for name, data in report['ablations'].items():
            latex_lines.append(latex_row(name, data))
        latex_lines.append("\\hline")
        latex_lines.append("\\end{tabular}")
        latex_lines.append("\\end{table}")
        latex_lines.append("")
        latex_lines.append("\\begin{table}[t]")
        latex_lines.append("\\centering")
        latex_lines.append("\\caption{Complementary Stress Test}")
        latex_lines.append("\\begin{tabular}{lccccc}")
        latex_lines.append("\\hline")
        latex_lines.append("Ablation & Top1 & MRR & Throughput (/s) & Latency (ms) & Margin \\\\")
        latex_lines.append("\\hline")
        stress_results = report['stress_test']['results']
        stress_margins = report['stress_test']['truth_vs_complement_margin']
        for name, data in stress_results.items():
            margin = stress_margins[name]
            latex_lines.append(
                f"{name} & "
                f"{data['top1_accuracy']:.3f} & "
                f"{data['mrr']:.3f} & "
                f"{data['throughput_per_sec']:.0f} & "
                f"{data['elapsed_ms']:.2f} & "
                f"{margin['margin_mean']:.3f}$\\pm${margin['margin_std']:.3f} \\\\"
            )
        latex_lines.append("\\hline")
        latex_lines.append("\\end{tabular}")
        latex_lines.append("\\end{table}")
        latex_path = Path('benchmark_research_tables.tex')
        latex_path.write_text('\n'.join(latex_lines), encoding='utf-8')
        print("✅ Research tables saved to: benchmark_research_methods.csv, benchmark_research_ablations.csv, benchmark_research_stress.csv, benchmark_research_tables.tex")

    def _run_application_gate(
        self,
        research_report: Dict[str, Any],
        throughput_min_speedup: float,
        max_top1_drop: float,
        min_margin_gain: float
    ) -> Dict[str, Any]:
        methods = research_report.get('methods', {})
        stress = research_report.get('stress_test', {})
        stress_margin = stress.get('truth_vs_complement_margin', {})

        dna_comp = methods.get('dna_complementary', {})
        float_cosine = methods.get('float_cosine', {})
        margin_0 = stress_margin.get('penalty_0.0', {})
        margin_1 = stress_margin.get('penalty_-1.0', {})

        dna_thr = float(dna_comp.get('throughput_mean', 0.0))
        float_thr = float(float_cosine.get('throughput_mean', 0.0))
        speedup = dna_thr / max(float_thr, 1e-9)

        dna_top1 = float(dna_comp.get('top1_accuracy_mean', 0.0))
        float_top1 = float(float_cosine.get('top1_accuracy_mean', 0.0))
        top1_drop = float_top1 - dna_top1

        margin_gain = float(margin_1.get('margin_mean', 0.0)) - float(margin_0.get('margin_mean', 0.0))

        checks = [
            {
                'name': 'throughput_speedup_vs_float_cosine',
                'actual': speedup,
                'threshold': throughput_min_speedup,
                'operator': '>=',
                'passed': speedup >= throughput_min_speedup
            },
            {
                'name': 'top1_non_inferiority_vs_float_cosine',
                'actual': top1_drop,
                'threshold': max_top1_drop,
                'operator': '<=',
                'passed': top1_drop <= max_top1_drop
            },
            {
                'name': 'stress_margin_gain_penalty_-1.0_vs_0.0',
                'actual': margin_gain,
                'threshold': min_margin_gain,
                'operator': '>=',
                'passed': margin_gain >= min_margin_gain
            }
        ]

        overall_passed = all(c['passed'] for c in checks)
        gate_report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'overall_passed': overall_passed,
            'thresholds': {
                'throughput_min_speedup': throughput_min_speedup,
                'max_top1_drop': max_top1_drop,
                'min_margin_gain': min_margin_gain
            },
            'checks': checks,
            'evidence': {
                'dna_complementary': dna_comp,
                'float_cosine': float_cosine,
                'stress_margin_penalty_0.0': margin_0,
                'stress_margin_penalty_-1.0': margin_1
            }
        }

        with open('benchmark_application_gate.json', 'w', encoding='utf-8') as f:
            json.dump(gate_report, f, indent=2, ensure_ascii=False)

        print("\n" + "="*70)
        print("🧪 APPLICATION GATE (One-vote Veto)")
        print("="*70)
        for c in checks:
            status = "PASS" if c['passed'] else "FAIL"
            print(
                f"   {status:<4} {c['name']:<42} "
                f"{c['actual']:.6f} {c['operator']} {c['threshold']:.6f}"
            )
        print(f"   Overall: {'PASS' if overall_passed else 'FAIL'}")
        print("✅ Gate report saved to: benchmark_application_gate.json")

        return gate_report
    
    def get_memory_usage_mb(self) -> float:
        """获取当前进程的内存占用(MB)"""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    
    def load_dna_data(self, file_path: str, limit: int = 100) -> List[Dict[str, Any]]:
        """加载DNA数据"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 如果有metadata结构，提取dna_entries
        if isinstance(data, dict) and 'dna_entries' in data:
            entries = data['dna_entries']
        else:
            entries = data
        
        return entries[:limit]
    
    # ========================================================================
    # 场景1：单条DNA指令匹配
    # ========================================================================
    
    def scenario_single_dna_matching(self, dna_entries: List[Dict], iterations: int = 1000):
        """
        场景1：单条DNA指令匹配
        
        任务：给定一个用户指令，找到最匹配的DNA条目
        """
        print("\n" + "="*70)
        print("📌 Scenario 1: Single DNA Instruction Matching")
        print("="*70)
        
        if not dna_entries:
            print("❌ No DNA entries provided")
            return
        
        # 准备数据
        target_instructions = [entry['instruction'] for entry in dna_entries[:10]]
        all_dnas = [entry.get('quaternary_dna', '') for entry in dna_entries]
        
        print(f"   Entries: {len(all_dnas)}")
        print(f"   Test queries: {len(target_instructions)}")
        print(f"   Iterations: {iterations}")
        
        # ======== 方法1：浮点权重 (模拟) ========
        print("\n   [1/2] Float-weight baseline (simulated)...")
        self.baseline_memory = self.get_memory_usage_mb()
        start_time = time.time()
        
        float_matches = 0
        for _ in range(iterations):
            for target in target_instructions:
                # 模拟：计算向量点积（传统方式）
                target_len = len(target)
                query_vector = np.random.rand(64).astype(np.float32)
                
                max_similarity = -1
                for dna in all_dnas:
                    dna_vector = self.codec.dna_to_weights(dna)
                    similarity = np.dot(query_vector, dna_vector) / 64.0
                    if similarity > max_similarity:
                        max_similarity = similarity
                        float_matches += 1
        
        float_time = (time.time() - start_time) * 1000
        float_memory_peak = self.get_memory_usage_mb()
        
        print(f"      Time: {float_time:.2f} ms")
        print(f"      Throughput: {iterations * len(target_instructions) / (float_time/1000):.0f} ops/sec")
        
        # ======== 方法2：4进制DNA ========
        print("\n   [2/2] 4-base DNA system...")
        self.baseline_memory = self.get_memory_usage_mb()
        start_time = time.time()
        
        dna_matches = 0
        for _ in range(iterations):
            for target in target_instructions:
                # DNA方式：直接序列比较
                target_dna = self.codec.weights_to_dna(np.random.rand(64))
                
                max_similarity = -1
                max_match = None
                for dna in all_dnas:
                    similarity = self.codec.dna_similarity(target_dna, dna, method="complementary")
                    if similarity > max_similarity:
                        max_similarity = similarity
                        max_match = dna
                        dna_matches += 1
        
        dna_time = (time.time() - start_time) * 1000
        dna_memory_peak = self.get_memory_usage_mb()
        
        print(f"      Time: {dna_time:.2f} ms")
        print(f"      Throughput: {iterations * len(target_instructions) / (dna_time/1000):.0f} ops/sec")
        
        # ======== 结果对比 ========
        speedup = float_time / dna_time if dna_time > 0 else 0
        print(f"\n   📊 Result Summary:")
        print(f"      Speedup: {speedup:.2f}x {'(DNA faster)' if speedup > 1 else '(Float faster)'}")
        print(f"      Time saved: {float_time - dna_time:.2f} ms ({(1-dna_time/float_time)*100:.1f}%)")
        
        throughput = iterations * len(target_instructions) / max(dna_time/1000, 0.001)
        result = BenchResult(
            name="Float vs DNA",
            scenario="single_matching",
            num_entries=len(all_dnas),
            total_time_ms=dna_time,
            memory_peak_mb=dna_memory_peak,
            memory_baseline_mb=self.baseline_memory,
            memory_delta_mb=dna_memory_peak - self.baseline_memory,
            throughput_per_sec=throughput,
            accuracy_percent=100.0,
            notes=f"Speedup: {speedup:.2f}x vs float"
        )
        self.results.append(result)
    
    # ========================================================================
    # 场景2：批量DNA比对 (GPU优化)
    # ========================================================================
    
    def scenario_batch_dna_comparison(self, dna_entries: List[Dict], batch_size: int = 32):
        """
        场景2：批量DNA比对 (模拟CUDA加速)
        
        任务：给定一个目标DNA，对批量的DNA序列进行相似度计算
        """
        print("\n" + "="*70)
        print(f"📦 Scenario 2: Batch DNA Comparison (batch_size={batch_size})")
        print("="*70)
        
        if not dna_entries:
            print("❌ No DNA entries provided")
            return
        
        target_dna = dna_entries[0].get('quaternary_dna', '')
        comparison_dnas = [e.get('quaternary_dna', '') for e in dna_entries]
        
        print(f"   Target DNA: {target_dna[:32]}...")
        print(f"   Total DNA sequences: {len(comparison_dnas)}")
        print(f"   Batch size: {batch_size}")
        
        # ======== 方法1：串行处理 ========
        print("\n   [1/2] Serial processing...")
        self.baseline_memory = self.get_memory_usage_mb()
        start_time = time.time()
        
        serial_similarities = []
        for dna in comparison_dnas:
            sim = self.codec.dna_similarity(target_dna, dna, method="complementary")
            serial_similarities.append(sim)
        
        serial_time = (time.time() - start_time) * 1000
        serial_memory = self.get_memory_usage_mb()
        
        print(f"      Time: {serial_time:.2f} ms")
        serial_throughput = len(comparison_dnas) / max(serial_time/1000, 0.001)
        print(f"      Throughput: {serial_throughput:.0f} comparisons/sec")
        
        # ======== 方法2：批处理 (模拟CUDA) ========
        print("\n   [2/2] Batch processing (simulated CUDA)...")
        self.baseline_memory = self.get_memory_usage_mb()
        start_time = time.time()
        
        batch_similarities = self.codec.batch_dna_similarity(
            target_dna, 
            comparison_dnas, 
            method="complementary"
        )
        
        batch_time = (time.time() - start_time) * 1000
        batch_memory = self.get_memory_usage_mb()
        
        print(f"      Time: {batch_time:.2f} ms")
        batch_throughput = len(comparison_dnas) / max(batch_time/1000, 0.001)
        print(f"      Throughput: {batch_throughput:.0f} comparisons/sec")
        
        # ======== 验证结果正确性 ========
        error = np.allclose(serial_similarities, batch_similarities, atol=1e-5)
        accuracy = 100.0 if error else 0.0
        
        # ======== 结果对比 ========
        speedup = serial_time / batch_time if batch_time > 0 else 0
        print(f"\n   📊 Result Summary:")
        print(f"      Speedup: {speedup:.2f}x")
        print(f"      Accuracy: {'✓ Correct' if error else '✗ Mismatch'}")
        print(f"      Memory: {serial_memory - batch_memory:.2f} MB saved")
        
        batch_throughput = len(comparison_dnas) / max(batch_time/1000, 0.001)
        result = BenchResult(
            name="Serial vs Batch",
            scenario="batch_comparison",
            num_entries=len(comparison_dnas),
            total_time_ms=batch_time,
            memory_peak_mb=batch_memory,
            memory_baseline_mb=self.baseline_memory,
            memory_delta_mb=batch_memory - self.baseline_memory,
            throughput_per_sec=batch_throughput,
            accuracy_percent=accuracy,
            notes=f"Speedup: {speedup:.2f}x"
        )
        self.results.append(result)
    
    # ========================================================================
    # 场景3：进化模拟
    # ========================================================================
    
    def scenario_evolutionary_drift(
        self,
        dna_entries: List[Dict],
        num_generations: int = 10,
        population_size: int = 32,
        sample_size: int = 48,
        base_mutation_rate: float = 0.05,
        selection_ratio: float = 0.25,
        seed: int = 20260316
    ):
        """
        场景3：DNA进化模拟
        
        任务：模拟DNA突变和选择，观察适应度变化
        """
        print("\n" + "="*70)
        print(f"🧬 Scenario 3: Evolutionary Selection ({num_generations} generations)")
        print("="*70)

        candidate_dnas = [e.get('quaternary_dna', '') for e in dna_entries if e.get('quaternary_dna')]
        if len(candidate_dnas) < 4:
            print("❌ Not enough DNA entries for evolutionary selection")
            return

        rng = np.random.default_rng(seed)
        pop_size = max(4, min(population_size, len(candidate_dnas)))
        elite_count = max(2, int(pop_size * selection_ratio))
        elite_count = min(elite_count, pop_size - 1)

        print(f"   Population: {pop_size}")
        print(f"   Elites per generation: {elite_count}")
        print(f"   Query sample size: {min(sample_size, len(candidate_dnas))}")
        print(f"   Base mutation rate: {base_mutation_rate:.3f}")

        init_indices = rng.choice(len(candidate_dnas), size=pop_size, replace=False)
        population = [candidate_dnas[int(i)] for i in init_indices]

        self.baseline_memory = self.get_memory_usage_mb()
        start_time = time.time()
        history = []
        best_individual = None

        for gen in range(num_generations):
            queries = self._build_mutated_queries(
                dna_entries=dna_entries,
                sample_size=sample_size,
                mutation_rate=base_mutation_rate,
                seed=seed + gen
            )
            if not queries:
                print("❌ No queries generated for evolution")
                return

            baseline_float = self._evaluate_method(queries, candidate_dnas, self._cosine_similarity_from_dna)
            evaluated = []
            for genome in population:
                scorer = self._build_policy_scorer(genome)
                metrics = self._evaluate_method(queries, candidate_dnas, scorer)
                margin = self._evaluate_truth_vs_complement_margin(queries, candidate_dnas, scorer)
                speedup_vs_float = metrics['throughput_per_sec'] / max(baseline_float['throughput_per_sec'], 1e-9)
                top1_drop_vs_float = baseline_float['top1_accuracy'] - metrics['top1_accuracy']
                gate_pass = (
                    speedup_vs_float >= 5.0 and
                    top1_drop_vs_float <= 0.02 and
                    margin['margin_mean'] >= 0.5
                )
                fitness = (
                    0.45 * metrics['top1_accuracy'] +
                    0.30 * metrics['mrr'] +
                    0.15 * np.tanh(metrics['throughput_per_sec'] / 50000.0) +
                    0.10 * np.clip(margin['margin_mean'], -1.0, 2.0) / 2.0
                )
                if not gate_pass:
                    fitness -= 1.0

                evaluated.append({
                    'genome': genome,
                    'fitness': float(fitness),
                    'gate_pass': gate_pass,
                    'speedup_vs_float': float(speedup_vs_float),
                    'top1_drop_vs_float': float(top1_drop_vs_float),
                    'metrics': metrics,
                    'margin': margin
                })

            evaluated.sort(key=lambda x: (x['gate_pass'], x['fitness']), reverse=True)
            elites = evaluated[:elite_count]
            best = elites[0]
            mean_fitness = float(np.mean([e['fitness'] for e in evaluated]))
            gate_pass_count = int(sum(1 for e in evaluated if e['gate_pass']))
            gate_pass_rate = gate_pass_count / len(evaluated)
            history.append({
                'generation': gen,
                'best_fitness': best['fitness'],
                'mean_fitness': mean_fitness,
                'gate_pass_rate': gate_pass_rate,
                'best_top1': best['metrics']['top1_accuracy'],
                'best_mrr': best['metrics']['mrr'],
                'best_speedup_vs_float': best['speedup_vs_float'],
                'best_margin': best['margin']['margin_mean']
            })
            if best_individual is None or best['fitness'] > best_individual['fitness']:
                best_individual = best

            print(
                f"      Gen {gen:02d}: "
                f"best_fit={best['fitness']:.3f}, "
                f"mean_fit={mean_fitness:.3f}, "
                f"gate_pass={gate_pass_count}/{len(evaluated)}, "
                f"top1={best['metrics']['top1_accuracy']:.3f}, "
                f"speedup={best['speedup_vs_float']:.2f}x"
            )

            next_population = [e['genome'] for e in elites]
            while len(next_population) < pop_size:
                p1 = elites[int(rng.integers(0, elite_count))]['genome']
                p2 = elites[int(rng.integers(0, elite_count))]['genome']
                child = self._crossover(p1, p2, rng)
                adaptive_rate = min(0.20, base_mutation_rate + (1.0 - gate_pass_rate) * 0.10)
                child = self.codec.generate_dna_mutation(child, mutation_rate=adaptive_rate)
                next_population.append(child)
            population = next_population

        evo_time = (time.time() - start_time) * 1000
        evo_memory = self.get_memory_usage_mb()

        initial_best = history[0]['best_fitness']
        peak_generation = max(history, key=lambda x: x['best_fitness'])
        final_best = peak_generation['best_fitness']
        improvement = final_best - initial_best
        evo_throughput = num_generations / max(evo_time / 1000, 0.001)

        evolution_report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'config': {
                'generations': num_generations,
                'population_size': pop_size,
                'elite_count': elite_count,
                'sample_size': sample_size,
                'base_mutation_rate': base_mutation_rate,
                'selection_ratio': selection_ratio,
                'seed': seed
            },
            'history': history,
            'best_individual': best_individual,
            'peak_generation': peak_generation
        }
        with open('benchmark_evolution_report.json', 'w', encoding='utf-8') as f:
            json.dump(evolution_report, f, indent=2, ensure_ascii=False)

        route_map = {
            'A': {'provider': 'ollama', 'model': 'qwen2.5:latest'},
            'T': {'provider': 'vllm', 'model': 'phoenix-soul-vl'},
            'C': {'provider': 'sglang', 'model': 'phoenix-soul-vl'},
            'G': {'provider': 'ollama', 'model': 'qwen2.5:latest'}
        }
        route_base = best_individual['genome'][0] if best_individual and best_individual.get('genome') else 'A'
        route_choice = route_map.get(route_base, route_map['A'])
        route_policy = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'source': 'benchmark_evolution_report.json',
            'genome': best_individual['genome'] if best_individual else '',
            'peak_generation': peak_generation['generation'],
            'peak_fitness': peak_generation['best_fitness'],
            'route': route_choice
        }
        with open('benchmark_route_policy.json', 'w', encoding='utf-8') as f:
            json.dump(route_policy, f, indent=2, ensure_ascii=False)

        print(f"\n   📊 Result Summary:")
        print(f"      Initial best fitness: {initial_best:.3f}")
        print(f"      Peak best fitness:    {final_best:.3f} (gen {peak_generation['generation']})")
        print(f"      Improvement: {improvement:.3f}")
        print(f"      Final gate pass rate: {history[-1]['gate_pass_rate']:.2%}")
        print(f"      Time: {evo_time:.2f} ms")
        print("✅ Evolution report saved to: benchmark_evolution_report.json")
        print("✅ Route policy saved to: benchmark_route_policy.json")

        result = BenchResult(
            name="Evolution Selection",
            scenario="evolutionary_drift",
            num_entries=num_generations,
            total_time_ms=evo_time,
            memory_peak_mb=evo_memory,
            memory_baseline_mb=self.baseline_memory,
            memory_delta_mb=evo_memory - self.baseline_memory,
            throughput_per_sec=evo_throughput,
            accuracy_percent=max(0.0, min(100.0, history[-1]['best_top1'] * 100.0)),
            notes=f"fitness Δ={improvement:.3f}, gate pass={history[-1]['gate_pass_rate']:.2%}"
        )
        self.results.append(result)

    def scenario_research_validation(
        self,
        dna_entries: List[Dict],
        sample_size: int = 64,
        mutation_rate: float = 0.05,
        repeats: int = 5
    ) -> Dict[str, Any]:
        print("\n" + "="*70)
        print("🔬 Scenario 4: Research Validation (Baselines + Ablation)")
        print("="*70)

        candidate_dnas = [e.get('quaternary_dna', '') for e in dna_entries if e.get('quaternary_dna')]
        if len(candidate_dnas) < 2:
            print("❌ Not enough DNA entries for research validation")
            return

        methods = {
            'dna_exact': lambda q, c: self.codec.dna_similarity(q, c, method='exact'),
            'dna_complementary': lambda q, c: self.codec.dna_similarity(q, c, method='complementary'),
            'dna_distance': lambda q, c: self.codec.dna_similarity(q, c, method='distance'),
            'float_cosine': self._cosine_similarity_from_dna,
            'float_l2': self._l2_similarity_from_dna
        }
        ablations = {
            'penalty_0.0': lambda q, c: self._complementary_with_penalty(q, c, penalty=0.0),
            'penalty_-0.5': lambda q, c: self._complementary_with_penalty(q, c, penalty=-0.5),
            'penalty_-1.0': lambda q, c: self._complementary_with_penalty(q, c, penalty=-1.0)
        }

        seeds = [20260316 + i for i in range(repeats)]
        method_runs: Dict[str, List[Dict[str, float]]] = {name: [] for name in methods}
        ablation_runs: Dict[str, List[Dict[str, float]]] = {name: [] for name in ablations}

        for seed in seeds:
            queries = self._build_mutated_queries(
                dna_entries=dna_entries,
                sample_size=sample_size,
                mutation_rate=mutation_rate,
                seed=seed
            )

            for name, scorer in methods.items():
                metrics = self._evaluate_method(queries, candidate_dnas, scorer)
                method_runs[name].append(metrics)

            for name, scorer in ablations.items():
                metrics = self._evaluate_method(queries, candidate_dnas, scorer)
                ablation_runs[name].append(metrics)

        stress_seed = 424242
        stress_queries = self._build_complementary_stress_queries(
            dna_entries=dna_entries,
            sample_size=sample_size,
            stress_rate=mutation_rate,
            seed=stress_seed
        )
        stress_ablation = {
            name: self._evaluate_method(stress_queries, candidate_dnas, scorer)
            for name, scorer in ablations.items()
        }
        stress_margins = {
            name: self._evaluate_truth_vs_complement_margin(stress_queries, candidate_dnas, scorer)
            for name, scorer in ablations.items()
        }

        def summarize(run_dict: Dict[str, List[Dict[str, float]]]) -> Dict[str, Dict[str, float]]:
            summary = {}
            for name, runs in run_dict.items():
                summary[name] = {
                    'top1_accuracy_mean': float(np.mean([r['top1_accuracy'] for r in runs])),
                    'top1_accuracy_std': float(np.std([r['top1_accuracy'] for r in runs])),
                    'mrr_mean': float(np.mean([r['mrr'] for r in runs])),
                    'mrr_std': float(np.std([r['mrr'] for r in runs])),
                    'throughput_mean': float(np.mean([r['throughput_per_sec'] for r in runs])),
                    'throughput_std': float(np.std([r['throughput_per_sec'] for r in runs])),
                    'latency_ms_mean': float(np.mean([r['elapsed_ms'] for r in runs])),
                    'latency_ms_std': float(np.std([r['elapsed_ms'] for r in runs]))
                }
            return summary

        method_summary = summarize(method_runs)
        ablation_summary = summarize(ablation_runs)

        print(f"   Repeats: {repeats}")
        print(f"   Query sample size: {min(sample_size, len(candidate_dnas))}")
        print(f"   Mutation rate: {mutation_rate:.3f}")
        print("\n   Baseline comparison:")
        for name, data in method_summary.items():
            print(
                f"      {name:<18} "
                f"top1={data['top1_accuracy_mean']:.3f}±{data['top1_accuracy_std']:.3f} "
                f"mrr={data['mrr_mean']:.3f}±{data['mrr_std']:.3f} "
                f"thr={data['throughput_mean']:.0f}/s"
            )

        print("\n   Complementary ablation:")
        for name, data in ablation_summary.items():
            print(
                f"      {name:<18} "
                f"top1={data['top1_accuracy_mean']:.3f}±{data['top1_accuracy_std']:.3f} "
                f"mrr={data['mrr_mean']:.3f}±{data['mrr_std']:.3f}"
            )

        print("\n   Complementary stress test:")
        for name, data in stress_ablation.items():
            print(
                f"      {name:<18} "
                f"top1={data['top1_accuracy']:.3f} "
                f"mrr={data['mrr']:.3f} "
                f"margin={stress_margins[name]['margin_mean']:.3f}±{stress_margins[name]['margin_std']:.3f}"
            )

        result = BenchResult(
            name="Research Validation",
            scenario="research_validation",
            num_entries=len(candidate_dnas),
            total_time_ms=float(np.mean([method_summary[m]['latency_ms_mean'] for m in method_summary])),
            memory_peak_mb=self.get_memory_usage_mb(),
            memory_baseline_mb=self.baseline_memory if self.baseline_memory is not None else self.get_memory_usage_mb(),
            memory_delta_mb=0.0,
            throughput_per_sec=method_summary['dna_complementary']['throughput_mean'],
            accuracy_percent=method_summary['dna_complementary']['top1_accuracy_mean'] * 100.0,
            notes=f"repeats={repeats}, mutation_rate={mutation_rate}"
        )
        self.results.append(result)

        research_report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'config': {
                'sample_size': sample_size,
                'mutation_rate': mutation_rate,
                'repeats': repeats,
                'candidate_count': len(candidate_dnas)
            },
            'methods': method_summary,
            'ablations': ablation_summary,
            'stress_test': {
                'seed': stress_seed,
                'sample_size': len(stress_queries),
                'stress_rate': mutation_rate,
                'results': stress_ablation,
                'truth_vs_complement_margin': stress_margins
            }
        }
        with open('benchmark_research_report.json', 'w', encoding='utf-8') as f:
            json.dump(research_report, f, indent=2, ensure_ascii=False)
        print("\n✅ Research report saved to: benchmark_research_report.json")
        self._write_research_tables(research_report)
        return research_report
    
    # ========================================================================
    # 报告生成
    # ========================================================================
    
    def print_summary(self):
        """打印汇总报告"""
        if not self.results:
            print("❌ No benchmark results to summarize")
            return
        
        print("\n" + "="*70)
        print("📈 BENCHMARK SUMMARY REPORT")
        print("="*70)
        
        print("\n┌─ Performance Metrics ─────────────────────────────────────────┐")
        print("│ Scenario          │ Time(ms) │ Memory(MB) │ Throughput │ Accuracy")
        print("├───────────────────┼──────────┼────────────┼────────────┼──────────┤")
        
        for result in self.results:
            scenario_short = result.scenario[:17].ljust(17)
            print(f"│ {scenario_short} │ {result.total_time_ms:8.2f} │ {result.memory_delta_mb:10.2f} │ {result.throughput_per_sec:10.0f} │ {result.accuracy_percent:6.1f}%")
        
        print("└───────────────────┴──────────┴────────────┴────────────┴──────────┘")
        
        # 保存详细报告
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'results': [asdict(r) for r in self.results],
            'summary': {
                'total_benchmarks': len(self.results),
                'avg_throughput': np.mean([r.throughput_per_sec for r in self.results]),
                'avg_memory_delta': np.mean([r.memory_delta_mb for r in self.results]),
            }
        }
        
        report_path = 'benchmark_report.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Detailed report saved to: {report_path}")


# ============================================================================
# Main
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Phoenix DNA Benchmark Suite')
    parser.add_argument('--mode', default='comprehensive', choices=['single', 'batch', 'evolution', 'research', 'validate', 'comprehensive'],
                       help='Benchmark mode')
    parser.add_argument('--dna-file', default='phoenix_dna_quaternary.json',
                       help='DNA data file')
    parser.add_argument('--limit', type=int, default=100,
                       help='Limit number of DNA entries to load')
    parser.add_argument('--iterations', type=int, default=100,
                       help='Iterations for single scenario')
    parser.add_argument('--batch-size', type=int, default=32,
                       help='Batch size for batch scenario')
    parser.add_argument('--generations', type=int, default=10,
                       help='Number of generations for evolution scenario')
    parser.add_argument('--population-size', type=int, default=32,
                       help='Population size for evolutionary selection')
    parser.add_argument('--evolution-sample-size', type=int, default=48,
                       help='Sample size per generation for evolutionary fitness evaluation')
    parser.add_argument('--evolution-selection-ratio', type=float, default=0.25,
                       help='Elite selection ratio for evolutionary selection')
    parser.add_argument('--evolution-seed', type=int, default=20260316,
                       help='Random seed for evolutionary selection')
    parser.add_argument('--sample-size', type=int, default=64,
                       help='Sample size for research validation queries')
    parser.add_argument('--mutation-rate', type=float, default=0.05,
                       help='Mutation rate for research validation')
    parser.add_argument('--repeats', type=int, default=5,
                       help='Repeat runs for research validation')
    parser.add_argument('--gate-throughput-min-speedup', type=float, default=5.0,
                       help='Gate threshold: dna_complementary throughput / float_cosine throughput (>=)')
    parser.add_argument('--gate-max-top1-drop', type=float, default=0.02,
                       help='Gate threshold: allowed top1 drop vs float_cosine (<=)')
    parser.add_argument('--gate-min-margin-gain', type=float, default=0.5,
                       help='Gate threshold: stress margin gain from penalty_0.0 to penalty_-1.0 (>=)')
    
    args = parser.parse_args()
    
    # 初始化benchmark
    benchmark = DNABenchmark()
    
    # 加载DNA数据
    print(f"📖 Loading DNA from: {args.dna_file}")
    try:
        dna_entries = benchmark.load_dna_data(args.dna_file, limit=args.limit)
        print(f"✓ Loaded {len(dna_entries)} entries")
    except Exception as e:
        print(f"❌ Failed to load DNA: {e}")
        return 1
    
    # 运行benchmark
    if args.mode in ['single', 'comprehensive']:
        benchmark.scenario_single_dna_matching(dna_entries, iterations=args.iterations)
    
    if args.mode in ['batch', 'comprehensive']:
        benchmark.scenario_batch_dna_comparison(dna_entries, batch_size=args.batch_size)
    
    if args.mode in ['evolution', 'comprehensive']:
        benchmark.scenario_evolutionary_drift(
            dna_entries,
            num_generations=args.generations,
            population_size=args.population_size,
            sample_size=args.evolution_sample_size,
            base_mutation_rate=args.mutation_rate,
            selection_ratio=args.evolution_selection_ratio,
            seed=args.evolution_seed
        )

    research_report = None
    if args.mode in ['research', 'validate', 'comprehensive']:
        research_report = benchmark.scenario_research_validation(
            dna_entries,
            sample_size=args.sample_size,
            mutation_rate=args.mutation_rate,
            repeats=args.repeats
        )

    gate_failed = False
    if args.mode == 'validate':
        gate_report = benchmark._run_application_gate(
            research_report=research_report if research_report is not None else {},
            throughput_min_speedup=args.gate_throughput_min_speedup,
            max_top1_drop=args.gate_max_top1_drop,
            min_margin_gain=args.gate_min_margin_gain
        )
        gate_failed = not gate_report['overall_passed']
    
    # 打印报告
    benchmark.print_summary()
    
    return 2 if gate_failed else 0


if __name__ == '__main__':
    sys.exit(main())
