"""
测试 TraceIdGenerator
"""

import pytest
from pylinkagent.pradar.trace_id import TraceIdGenerator, generate_trace_id


class TestTraceIdGenerator:
    """TraceIdGenerator 测试"""

    def setup_method(self):
        """每个测试前的准备"""
        # 重置序列
        TraceIdGenerator._sequence = 0

    def test_generate_trace_id(self):
        """测试生成 Trace ID"""
        trace_id = TraceIdGenerator.generate()

        # 验证格式：时间戳 (15 位) + 主机标识 (12 位) + 线程 ID(5 位) + 序列 (4 位) = 36 位
        assert len(trace_id) == 36
        assert trace_id.isdigit()

    def test_trace_id_uniqueness(self):
        """测试 Trace ID 唯一性"""
        trace_ids = set()
        for _ in range(1000):
            trace_ids.add(TraceIdGenerator.generate())

        # 1000 个 ID 应该全部唯一
        assert len(trace_ids) == 1000

    def test_sequence_increment(self):
        """测试序列自增"""
        TraceIdGenerator._sequence = 0
        id1 = TraceIdGenerator.generate()
        id2 = TraceIdGenerator.generate()

        # 最后 4 位是序列号
        seq1 = int(id1[-4:])
        seq2 = int(id2[-4:])

        # 序列应该递增
        assert seq2 == seq1 + 1

    def test_sequence_overflow(self):
        """测试序列溢出处理"""
        TraceIdGenerator._sequence = 9998
        id1 = TraceIdGenerator.generate()
        id2 = TraceIdGenerator.generate()

        seq1 = int(id1[-4:])
        seq2 = int(id2[-4:])

        # 序列应该循环回 0
        assert seq1 == 9999
        assert seq2 == 0

    def test_host_id_consistency(self):
        """测试主机标识一致性"""
        id1 = TraceIdGenerator.generate()
        id2 = TraceIdGenerator.generate()

        # 主机标识部分（第 15-27 位）应该相同
        host1 = id1[15:27]
        host2 = id2[15:27]

        assert host1 == host2

    def test_generate_with_prefix(self):
        """测试生成带前缀的 Trace ID"""
        trace_id = TraceIdGenerator.generate_with_prefix("TEST")

        assert trace_id.startswith("TEST")
        assert len(trace_id) == 40  # 4 + 36

    def test_generate_cluster_test(self):
        """测试生成压测 Trace ID"""
        trace_id = TraceIdGenerator.generate_cluster_test()

        # 压测 ID 以 "1" 开头
        assert trace_id.startswith("1")
        assert len(trace_id) == 37  # 1 + 36

    def test_generate_trace_id_function(self):
        """测试便捷函数"""
        trace_id = generate_trace_id()

        assert len(trace_id) == 36
        assert trace_id.isdigit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
