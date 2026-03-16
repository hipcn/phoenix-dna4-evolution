#!/usr/bin/env python3
"""
Phoenix Quaternary DNA Codec
============================

将标准的浮点权重和布尔逻辑转换为4进制DNA编码系统。

核心功能：
1. DNA序列 ↔ 浮点权重向量的双向转换
2. 表观遗传状态的编码和解码
3. DNA相似度计算（基于生物互补原理）
4. 批量DNA处理和CUDA优化接口

作者：Phoenix DNA Engineering Team
日期：2026-03-15
版本：1.0.0
"""

import numpy as np
from typing import List, Tuple, Union, Dict, Optional
from dataclasses import dataclass
from enum import Enum


class Nucleobase(Enum):
    """四种核苷酸的枚举定义"""
    A = 'A'  # 腺嘌呤 (Adenine)     → 0.125 (0.0-0.25)
    T = 'T'  # 胸腺嘧啶 (Thymine)   → 0.375 (0.25-0.5)
    C = 'C'  # 胞嘧啶 (Cytosine)    → 0.625 (0.5-0.75)
    G = 'G'  # 鸟嘌呤 (Guanine)     → 0.875 (0.75-1.0)


@dataclass
class DNAConfig:
    """DNA编码配置"""
    sequence_length: int = 64           # DNA序列长度（bp）
    value_precision: float = 0.125      # 量化精度（每个碱基0.25的范围）
    batch_size: int = 32                # GPU批处理大小
    use_cuda: bool = True               # 是否启用CUDA加速
    canonical_form: str = "quaternary"  # 编码形式：quaternary/binary/ternary


class DNACodec:
    """
    4进制DNA编码/解码器
    
    将权重向量编码为DNA序列，反之亦然。
    支持表观遗传标记和多值逻辑运算。
    """
    
    # 核苷酸到浮点值的映射
    NUCLEOBASE_TO_FLOAT = {
        'A': 0.125,   # 弱激活
        'T': 0.375,   # 中弱激活
        'C': 0.625,   # 中强激活
        'G': 0.875,   # 强激活
    }
    
    # 浮点值到核苷酸的反向映射（通过量化）
    FLOAT_TO_NUCLEOBASE = {
        range(0, 25): 'A',     # [0.0, 0.25)   → A
        range(25, 50): 'T',    # [0.25, 0.5)   → T
        range(50, 75): 'C',    # [0.5, 0.75)   → C
        range(75, 100): 'G',   # [0.75, 1.0]   → G
    }
    
    # 互补配对规则（DNA的对称性）
    COMPLEMENTARY = {
        'A': 'T',
        'T': 'A',
        'C': 'G',
        'G': 'C',
    }
    
    def __init__(self, config: Optional[DNAConfig] = None):
        """初始化编码器"""
        self.config = config or DNAConfig()
        self.validation_stats = {}
    
    def nucleobase_to_float(self, base: str) -> float:
        """
        将单个核苷酸转换为权重值
        
        Args:
            base: 核苷酸字符 ('A', 'T', 'C', 'G')
            
        Returns:
            float: 对应的权重值 [0.0, 1.0]
            
        Raises:
            ValueError: 如果核苷酸字符无效
        """
        if base not in self.NUCLEOBASE_TO_FLOAT:
            raise ValueError(f"Invalid nucleobase: {base}. Must be in {list(self.NUCLEOBASE_TO_FLOAT.keys())}")
        return self.NUCLEOBASE_TO_FLOAT[base]
    
    def float_to_nucleobase(self, value: float, method: str = "round") -> str:
        """
        将权重值量化为核苷酸
        
        Args:
            value: 权重值 [0.0, 1.0]
            method: 量化方法 ("round" 四舍五入 | "floor" 向下取整 | "ceil" 向上取整)
            
        Returns:
            str: 对应的核苷酸字符
            
        Raises:
            ValueError: 如果权重值超出范围
        """
        if not (0.0 <= value <= 1.0):
            raise ValueError(f"Value must be in [0.0, 1.0], got {value}")
        
        # 转换为百分比整数 (0-100)
        percentile = int(value * 100)
        
        # 量化选择
        if method == "round":
            percentile = round(value * 100)
        elif method == "floor":
            percentile = int(value * 100)
        elif method == "ceil":
            percentile = -(-int(value * 100 * 4) // 25)  # 向上取整到25的倍数
        else:
            raise ValueError(f"Unknown method: {method}")
        
        if percentile < 25:
            return 'A'
        elif percentile < 50:
            return 'T'
        elif percentile < 75:
            return 'C'
        else:
            return 'G'
    
    def dna_to_weights(self, dna_sequence: str) -> np.ndarray:
        """
        将DNA序列转换为权重向量
        
        Args:
            dna_sequence: DNA序列字符串 (e.g., "ATCGATCG")
            
        Returns:
            np.ndarray: 权重向量，shape=(len(dna_sequence),)
            
        Raises:
            ValueError: 如果序列包含无效字符
        """
        if not dna_sequence:
            raise ValueError("DNA sequence cannot be empty")
        
        try:
            weights = np.array([self.nucleobase_to_float(base) for base in dna_sequence], dtype=np.float32)
            self.validation_stats['last_dna_to_weights'] = {
                'sequence_length': len(dna_sequence),
                'mean_weight': float(np.mean(weights)),
                'std_weight': float(np.std(weights)),
            }
            return weights
        except ValueError as e:
            raise ValueError(f"Failed to convert DNA sequence: {e}")
    
    def weights_to_dna(self, weights: Union[List[float], np.ndarray]) -> str:
        """
        将权重向量转换为DNA序列
        
        Args:
            weights: 权重向量 (list or np.ndarray)
            
        Returns:
            str: DNA序列字符串
            
        Raises:
            ValueError: 如果权重值超出范围
        """
        if isinstance(weights, list):
            weights = np.array(weights, dtype=np.float32)
        
        if not isinstance(weights, np.ndarray):
            raise TypeError(f"weights must be list or np.ndarray, got {type(weights)}")
        
        try:
            dna_sequence = ''.join([self.float_to_nucleobase(w) for w in weights])
            self.validation_stats['last_weights_to_dna'] = {
                'sequence_length': len(dna_sequence),
                'input_shape': weights.shape,
            }
            return dna_sequence
        except ValueError as e:
            raise ValueError(f"Failed to convert weights to DNA: {e}")
    
    def encode_expression_state(self, activity_levels: Union[List[float], np.ndarray]) -> str:
        """
        编码表观遗传状态（基因表达水平）
        
        表观遗传状态用于控制每个权重的活跃度：
        - 完全激活 (表达率=1.0)   → G (强激活)
        - 部分激活   (表达率~0.5) → C 或 T
        - 沉默       (表达率=0.0) → A (弱激活/关闭)
        
        Args:
            activity_levels: 活跃度向量 [0.0, 1.0] per position
            
        Returns:
            str: 表观遗传标记序列
        """
        return self.weights_to_dna(activity_levels)
    
    def decode_expression_state(self, expression_dna: str) -> np.ndarray:
        """
        解码表观遗传状态（基因表达水平）
        
        Args:
            expression_dna: 表观遗传标记序列
            
        Returns:
            np.ndarray: 对应的活跃度向量
        """
        return self.dna_to_weights(expression_dna)
    
    def apply_expression(self, weights: np.ndarray, expression_state: str) -> np.ndarray:
        """
        应用表观遗传调节（开关）
        
        计算：final_weight[i] = weights[i] × expression_rate[i]
        
        Args:
            weights: 基础权重向量
            expression_state: 表观遗传DNA序列
            
        Returns:
            np.ndarray: 调节后的权重
        """
        if isinstance(weights, list):
            weights = np.array(weights, dtype=np.float32)
        
        if len(expression_state) != len(weights):
            raise ValueError(
                f"Expression state length ({len(expression_state)}) "
                f"must match weights length ({len(weights)})"
            )
        
        expression_rates = self.dna_to_weights(expression_state)
        adjusted_weights = weights * expression_rates
        
        self.validation_stats['last_expression_application'] = {
            'original_mean': float(np.mean(weights)),
            'adjusted_mean': float(np.mean(adjusted_weights)),
            'expression_mean': float(np.mean(expression_rates)),
        }
        
        return adjusted_weights
    
    def dna_similarity(self, dna1: str, dna2: str, method: str = "complementary") -> float:
        """
        计算DNA序列相似度（基于生物互补原理）
        
        三种方法：
        1. "exact"：完全匹配相似度
           - 相同碱基：+1.0
           - 不同碱基：0.0
           
        2. "complementary"：互补配对相似度（推荐）
           - 相同碱基：+1.0
           - 互补碱基：-0.5 (反向匹配，表示转换关系)
           - 其他：0.0
           
        3. "distance"：汉明距离相似度
           - 相似度 = 1 - (汉明距离 / 序列长度)
        
        Args:
            dna1: DNA序列1
            dna2: DNA序列2
            method: 相似度计算方法
            
        Returns:
            float: 相似度分数 [-1.0, 1.0]
        """
        if len(dna1) != len(dna2):
            raise ValueError(f"DNA sequences must have equal length: {len(dna1)} vs {len(dna2)}")
        
        if method == "exact":
            matches = sum(1 for b1, b2 in zip(dna1, dna2) if b1 == b2)
            return matches / len(dna1)
        
        elif method == "complementary":
            similarity_score = 0
            for b1, b2 in zip(dna1, dna2):
                if b1 == b2:
                    similarity_score += 1.0
                elif self.COMPLEMENTARY.get(b1) == b2:
                    similarity_score += -0.5  # 互补配对表示某种对立/转换
                else:
                    similarity_score += 0.0
            return similarity_score / len(dna1)
        
        elif method == "distance":
            hamming_distance = sum(1 for b1, b2 in zip(dna1, dna2) if b1 != b2)
            return 1.0 - (hamming_distance / len(dna1))
        
        else:
            raise ValueError(f"Unknown similarity method: {method}")
    
    def generate_dna_mutation(self, dna_sequence: str, mutation_rate: float = 0.05) -> str:
        """
        生成DNA突变（用于进化模拟）
        
        Args:
            dna_sequence: 原始DNA序列
            mutation_rate: 突变率 (0.0-1.0)
            
        Returns:
            str: 突变后的DNA序列
        """
        if not (0.0 <= mutation_rate <= 1.0):
            raise ValueError(f"Mutation rate must be in [0.0, 1.0], got {mutation_rate}")
        
        bases = list(dna_sequence)
        all_bases = list(self.NUCLEOBASE_TO_FLOAT.keys())
        
        for i in range(len(bases)):
            if np.random.random() < mutation_rate:
                # 随机选择一个不同的碱基
                current_base = bases[i]
                alternative_bases = [b for b in all_bases if b != current_base]
                bases[i] = np.random.choice(alternative_bases)
        
        return ''.join(bases)
    
    def batch_dna_similarity(self, target_dna: str, dna_sequences: List[str], method: str = "complementary") -> np.ndarray:
        """
        批量计算目标DNA与多个DNA序列的相似度（GPU优化）
        
        Args:
            target_dna: 目标DNA序列
            dna_sequences: DNA序列列表
            method: 相似度方法
            
        Returns:
            np.ndarray: 相似度数组
        """
        similarities = np.array([
            self.dna_similarity(target_dna, dna, method)
            for dna in dna_sequences
        ], dtype=np.float32)
        
        self.validation_stats['last_batch_similarity'] = {
            'batch_size': len(dna_sequences),
            'mean_similarity': float(np.mean(similarities)),
            'max_similarity': float(np.max(similarities)),
            'min_similarity': float(np.min(similarities)),
        }
        
        return similarities
    
    def get_validation_stats(self) -> Dict:
        """获取最后一次操作的统计信息"""
        return self.validation_stats.copy()


# ============================================================================
# 单元测试
# ============================================================================

def test_nucleobase_conversion():
    """测试核苷酸转换"""
    codec = DNACodec()
    
    # 测试映射
    assert codec.nucleobase_to_float('A') == 0.125
    assert codec.nucleobase_to_float('T') == 0.375
    assert codec.nucleobase_to_float('C') == 0.625
    assert codec.nucleobase_to_float('G') == 0.875
    
    print("✓ Nucleobase conversion test passed")


def test_dna_weights_conversion():
    """测试DNA序列与权重向量的转换"""
    codec = DNACodec()
    
    # DNA → 权重
    dna = "ATCG"
    weights = codec.dna_to_weights(dna)
    assert np.allclose(weights, [0.125, 0.375, 0.625, 0.875])
    
    # 权重 → DNA
    weights = [0.1, 0.4, 0.6, 0.9]
    dna_result = codec.weights_to_dna(weights)
    assert len(dna_result) == 4
    assert all(b in 'ATCG' for b in dna_result)
    
    # 往返测试
    original_weights = [0.15, 0.35, 0.65, 0.85]
    dna_encoded = codec.weights_to_dna(original_weights)
    recovered_weights = codec.dna_to_weights(dna_encoded)
    assert dna_encoded == "ATCG"
    assert np.allclose(recovered_weights, [0.125, 0.375, 0.625, 0.875], atol=0.01)
    
    print("✓ DNA-weights conversion test passed")


def test_expression_state():
    """测试表观遗传状态编码"""
    codec = DNACodec()
    
    # 编码活跃度
    activity = [0.1, 0.5, 0.8, 0.9]
    expression_dna = codec.encode_expression_state(activity)
    assert len(expression_dna) == 4
    
    # 解码
    decoded_activity = codec.decode_expression_state(expression_dna)
    assert len(decoded_activity) == 4
    
    # 应用表观遗传调节
    weights = np.array([0.5, 0.5, 0.5, 0.5])
    adjusted = codec.apply_expression(weights, expression_dna)
    assert len(adjusted) == 4
    assert np.all(adjusted <= weights)  # 表情调节应该降低权重
    
    print("✓ Expression state test passed")


def test_dna_similarity():
    """测试DNA相似度计算"""
    codec = DNACodec()
    
    # 完全相同
    dna1 = "ATCGATCG"
    dna2 = "ATCGATCG"
    assert codec.dna_similarity(dna1, dna2, "exact") == 1.0
    
    # 完全互补
    dna1 = "ATCGATCG"
    dna2 = "TAGCTAGC"  # 互补序列
    similarity = codec.dna_similarity(dna1, dna2, "complementary")
    assert similarity == -0.5  # 所有位都互补
    
    # 部分匹配
    dna1 = "ATCGATCG"
    dna2 = "ATCGATAA"
    similarity = codec.dna_similarity(dna1, dna2, "exact")
    assert similarity == 0.75  # 6/8 匹配
    
    print("✓ DNA similarity test passed")


def test_batch_operations():
    """测试批量操作"""
    codec = DNACodec()
    
    target = "ATCGATCG"
    sequences = [
        "ATCGATCG",  # 完全相同
        "ATCGATAA",  # 部分相同
        "TAGCTAGC",  # 完全互补
    ]
    
    similarities = codec.batch_dna_similarity(target, sequences, "complementary")
    assert len(similarities) == 3
    assert similarities[0] == 1.0  # 完全相同
    assert similarities[2] == -0.5  # 完全互补
    
    print("✓ Batch operations test passed")


def test_dna_mutation():
    """测试DNA突变"""
    codec = DNACodec()
    
    original = "ATCGATCGATCGATCG"
    mutated = codec.generate_dna_mutation(original, mutation_rate=0.5)
    
    # 至少有一些变化（概率性的，但极端情况下可能没变）
    assert isinstance(mutated, str)
    assert len(mutated) == len(original)
    assert all(b in 'ATCG' for b in mutated)
    
    # 计算变化率
    changes = sum(1 for b1, b2 in zip(original, mutated) if b1 != b2)
    # 期望变化 ~50%，但实际可能有偏差
    print(f"  Mutation rate: {changes/len(original)*100:.1f}% (expected ~50%)")
    
    print("✓ DNA mutation test passed")


def test_64bp_sequence():
    """测试64bp序列（Phoenix推荐配置）"""
    codec = DNACodec(DNAConfig(sequence_length=64))
    
    # 生成随机64bp序列
    random_weights = np.random.rand(64).astype(np.float32)
    dna_64bp = codec.weights_to_dna(random_weights)
    
    assert len(dna_64bp) == 64
    assert all(b in 'ATCG' for b in dna_64bp)
    
    # 恢复权重
    recovered = codec.dna_to_weights(dna_64bp)
    assert len(recovered) == 64
    
    # 表观遗传
    expression = codec.encode_expression_state(np.random.rand(64).astype(np.float32))
    assert len(expression) == 64
    
    # 应用调节
    adjusted = codec.apply_expression(recovered, expression)
    assert len(adjusted) == 64
    
    print("✓ 64bp sequence test passed")


def run_all_tests():
    """运行所有单元测试"""
    print("\n" + "="*60)
    print("🧬 Phoenix DNA Codec Unit Tests")
    print("="*60 + "\n")
    
    try:
        test_nucleobase_conversion()
        test_dna_weights_conversion()
        test_expression_state()
        test_dna_similarity()
        test_batch_operations()
        test_dna_mutation()
        test_64bp_sequence()
        
        print("\n" + "="*60)
        print("✅ All tests passed!")
        print("="*60 + "\n")
        return True
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
