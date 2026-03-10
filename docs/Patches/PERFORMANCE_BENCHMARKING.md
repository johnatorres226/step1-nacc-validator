# Performance Benchmarking Plan: Unified Rule Routing

**Branch**: `feature/unified-rule-routing`  
**Date**: February 14, 2026  
**Status**: Ready for Performance Testing  

---

## Overview

This document provides a comprehensive plan for benchmarking the performance of the unified rule routing system against the legacy instrument-based routing approach. The goal is to quantify performance improvements and ensure the system meets production requirements.

---

## Benchmarking Objectives

### Primary Objectives

1. **Compare Throughput**: Measure records/second for unified vs. legacy
2. **Measure Latency**: Track validation time per record
3. **Assess Memory Usage**: Monitor memory consumption patterns
4. **Validate Caching**: Verify cache effectiveness
5. **Identify Bottlenecks**: Find optimization opportunities

### Success Criteria

- **Throughput**: Unified ≥ 90% of legacy (actually expect improvement)
- **Latency**: Average time per record ≤ 110% of legacy
- **Memory**: Peak memory ≤ 120% of legacy
- **Cache**: Hit rate > 95% after warmup
- **Scalability**: Linear scaling up to 10,000 records

---

## Benchmark Datasets

### Dataset 1: Small (100 records)

**Purpose**: Quick smoke test, cache warmup behavior  
**Source**: First 100 records from QC_CompleteVisits  
**Expected Time**: 5-10 seconds  
**Key Metrics**: Cache behavior, initialization overhead  

### Dataset 2: Medium (500 records)

**Purpose**: Typical production workload  
**Source**: QC_CompleteVisits or QC_AllIncompleteVisits  
**Expected Time**: 25-50 seconds  
**Key Metrics**: Steady-state throughput, memory usage  

### Dataset 3: Large (2,000 records)

**Purpose**: High-volume workload simulation  
**Source**: Multiple output directories combined  
**Expected Time**: 100-200 seconds  
**Key Metrics**: Scalability, memory stability  

### Dataset 4: Extra Large (5,000+ records)

**Purpose**: Stress test, production peak load  
**Source**: Historical data aggregation  
**Expected Time**: 250-500 seconds  
**Key Metrics**: Performance degradation, memory leaks  

### Dataset 5: Mixed Packets

**Purpose**: Test packet switching overhead  
**Source**: Records from I, I4, and F packets mixed  
**Expected Time**: Varies  
**Key Metrics**: Rule loading efficiency, cache effectiveness  

---

## Benchmark Metrics

### Timing Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| Total Time | End-to-end validation time | < Legacy * 1.1 |
| Time per Record | Average time per record | < 100ms |
| Rule Loading Time | Time to load all rules | < 500ms per packet |
| Schema Building Time | Time to build Cerberus schema | < 200ms per packet |
| Validation Time | Pure validation time | < 50ms per record |
| Startup Overhead | Initial setup time | < 1 second |

### Memory Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| Peak Memory | Maximum memory used | < Legacy * 1.2 |
| Baseline Memory | Memory before validation | Track |
| Memory Growth | Memory increase during run | < 10% |
| Memory per Record | Average memory per record | Track |
| Memory Leak | Memory not released | 0 |

### Cache Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| Cache Hit Rate | % of cache hits | > 95% |
| Cache Miss Rate | % of cache misses | < 5% |
| Cache Size | Memory used by cache | Track |
| Cache Load Time | Time to populate cache | < 500ms |
| Cache Effectiveness | Time saved by cache | Track |

### Throughput Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| Records/Second | Overall throughput | > 15 rec/sec |
| Errors/Second | Error generation rate | Track |
| Rules/Second | Rule evaluations/sec | Track |
| CPU Utilization | CPU usage % | Track |

---

## Benchmarking Tools

### Tool 1: Python `time` Module

**Use Case**: Basic timing measurements  
**Pros**: Built-in, simple  
**Cons**: Low precision  

```python
import time

start = time.time()
# ... run validation ...
end = time.time()
elapsed = end - start
```

### Tool 2: Python `timeit` Module

**Use Case**: Accurate micro-benchmarks  
**Pros**: Precise, repeatable  
**Cons**: Overhead for setup  

```python
import timeit

def benchmark():
    validate_data_unified(data, "ptid", config)

time_taken = timeit.timeit(benchmark, number=10) / 10
```

### Tool 3: `memory_profiler`

**Use Case**: Memory usage tracking  
**Installation**: `pip install memory-profiler`  

```python
from memory_profiler import profile

@profile
def run_validation():
    validate_data_unified(data, "ptid", config)
```

### Tool 4: `cProfile` and `pstats`

**Use Case**: Function-level profiling  
**Built-in**: Standard library  

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()
# ... run validation ...
profiler.disable()

stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 functions
```

### Tool 5: `line_profiler`

**Use Case**: Line-by-line profiling  
**Installation**: `pip install line-profiler`  

```bash
kernprof -l -v benchmark_script.py
```

### Tool 6: Custom Benchmark Script

**Use Case**: Comprehensive benchmarking  
**Location**: `scripts/benchmark_validation.py`  

---

## Benchmark Implementation

### Create Benchmark Script

**File**: `scripts/benchmark_validation.py`

```python
"""
Performance benchmarking script for unified vs legacy validation.

Usage:
    python scripts/benchmark_validation.py --dataset medium --runs 5
"""

import argparse
import time
import pandas as pd
import psutil
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

from src.pipeline.config.config_manager import QCConfig
from src.pipeline.reports.report_pipeline import (
    validate_data_with_hierarchical_routing,
    validate_data_unified
)


class PerformanceBenchmark:
    """Performance benchmarking utility."""

    def __init__(self):
        self.config = QCConfig()
        self.results: List[Dict] = []

    def load_dataset(self, size: str) -> pd.DataFrame:
        """Load benchmark dataset of specified size."""
        output_dir = Path("output")
        complete_dirs = sorted(output_dir.glob("QC_CompleteVisits_*"))
        
        if not complete_dirs:
            raise FileNotFoundError("No test data found")
        
        csv_file = complete_dirs[-1] / "validated_records.csv"
        data = pd.read_csv(csv_file)
        
        sizes = {
            "small": 100,
            "medium": 500,
            "large": 2000,
            "xlarge": 5000
        }
        
        n = sizes.get(size, 100)
        return data.head(n)

    def measure_memory(self) -> float:
        """Get current memory usage in MB."""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024

    def benchmark_legacy(
        self, 
        data: pd.DataFrame, 
        primary_key: str
    ) -> Dict:
        """Benchmark legacy validation."""
        # Warmup
        _ = validate_data_with_hierarchical_routing(
            data.head(10), primary_key, self.config
        )
        
        # Measure
        mem_before = self.measure_memory()
        start = time.time()
        
        errors, logs = validate_data_with_hierarchical_routing(
            data, primary_key, self.config
        )
        
        end = time.time()
        mem_after = self.measure_memory()
        
        return {
            "method": "legacy",
            "total_time": end - start,
            "records": len(data),
            "errors": len(errors),
            "time_per_record": (end - start) / len(data),
            "records_per_second": len(data) / (end - start),
            "memory_before": mem_before,
            "memory_after": mem_after,
            "memory_delta": mem_after - mem_before,
        }

    def benchmark_unified(
        self, 
        data: pd.DataFrame, 
        primary_key: str
    ) -> Dict:
        """Benchmark unified validation."""
        # Warmup
        _ = validate_data_unified(
            data.head(10), primary_key, self.config
        )
        
        # Measure
        mem_before = self.measure_memory()
        start = time.time()
        
        errors, logs = validate_data_unified(
            data, primary_key, self.config
        )
        
        end = time.time()
        mem_after = self.measure_memory()
        
        # Get cache stats if available
        from src.pipeline.io.unified_rule_loader import UnifiedRuleLoader
        loader = UnifiedRuleLoader(self.config)
        cache_stats = loader.get_cache_stats()
        
        return {
            "method": "unified",
            "total_time": end - start,
            "records": len(data),
            "errors": len(errors),
            "time_per_record": (end - start) / len(data),
            "records_per_second": len(data) / (end - start),
            "memory_before": mem_before,
            "memory_after": mem_after,
            "memory_delta": mem_after - mem_before,
            "cache_hits": cache_stats.get("hits", 0),
            "cache_misses": cache_stats.get("misses", 0),
            "cache_hit_rate": cache_stats.get("hits", 0) / 
                            max(cache_stats.get("hits", 0) + cache_stats.get("misses", 0), 1)
        }

    def run_comparison(
        self, 
        dataset_size: str, 
        runs: int = 3
    ) -> List[Dict]:
        """Run comparison benchmark multiple times."""
        print(f"\n{'='*60}")
        print(f"Benchmarking: {dataset_size.upper()} dataset")
        print(f"Runs: {runs}")
        print(f"{'='*60}\n")
        
        data = self.load_dataset(dataset_size)
        print(f"Loaded {len(data)} records\n")
        
        results = []
        
        for run in range(runs):
            print(f"Run {run + 1}/{runs}:")
            
            # Legacy
            print("  - Running legacy validation...")
            legacy_result = self.benchmark_legacy(data, "ptid")
            legacy_result["run"] = run + 1
            legacy_result["dataset_size"] = dataset_size
            results.append(legacy_result)
            print(f"    Time: {legacy_result['total_time']:.2f}s, "
                  f"Throughput: {legacy_result['records_per_second']:.1f} rec/s")
            
            # Unified
            print("  - Running unified validation...")
            unified_result = self.benchmark_unified(data, "ptid")
            unified_result["run"] = run + 1
            unified_result["dataset_size"] = dataset_size
            results.append(unified_result)
            print(f"    Time: {unified_result['total_time']:.2f}s, "
                  f"Throughput: {unified_result['records_per_second']:.1f} rec/s")
            
            # Speedup
            speedup = legacy_result['total_time'] / unified_result['total_time']
            print(f"    Speedup: {speedup:.2f}x\n")
        
        self.results.extend(results)
        return results

    def print_summary(self):
        """Print benchmark summary."""
        if not self.results:
            print("No results to summarize")
            return
        
        legacy_results = [r for r in self.results if r["method"] == "legacy"]
        unified_results = [r for r in self.results if r["method"] == "unified"]
        
        print(f"\n{'='*60}")
        print("BENCHMARK SUMMARY")
        print(f"{'='*60}\n")
        
        # Legacy stats
        legacy_avg_time = sum(r["total_time"] for r in legacy_results) / len(legacy_results)
        legacy_avg_throughput = sum(r["records_per_second"] for r in legacy_results) / len(legacy_results)
        legacy_avg_mem = sum(r["memory_delta"] for r in legacy_results) / len(legacy_results)
        
        print(f"Legacy Validation:")
        print(f"  Average Time: {legacy_avg_time:.2f}s")
        print(f"  Average Throughput: {legacy_avg_throughput:.1f} rec/s")
        print(f"  Average Memory: {legacy_avg_mem:.1f} MB")
        
        # Unified stats
        unified_avg_time = sum(r["total_time"] for r in unified_results) / len(unified_results)
        unified_avg_throughput = sum(r["records_per_second"] for r in unified_results) / len(unified_results)
        unified_avg_mem = sum(r["memory_delta"] for r in unified_results) / len(unified_results)
        unified_avg_cache_rate = sum(r.get("cache_hit_rate", 0) for r in unified_results) / len(unified_results)
        
        print(f"\nUnified Validation:")
        print(f"  Average Time: {unified_avg_time:.2f}s")
        print(f"  Average Throughput: {unified_avg_throughput:.1f} rec/s")
        print(f"  Average Memory: {unified_avg_mem:.1f} MB")
        print(f"  Cache Hit Rate: {unified_avg_cache_rate*100:.1f}%")
        
        # Comparison
        speedup = legacy_avg_time / unified_avg_time
        throughput_improvement = (unified_avg_throughput - legacy_avg_throughput) / legacy_avg_throughput * 100
        memory_change = (unified_avg_mem - legacy_avg_mem) / legacy_avg_mem * 100
        
        print(f"\nComparison:")
        print(f"  Speedup: {speedup:.2f}x")
        print(f"  Throughput Improvement: {throughput_improvement:+.1f}%")
        print(f"  Memory Change: {memory_change:+.1f}%")
        
        # Pass/Fail
        print(f"\n{'='*60}")
        print("SUCCESS CRITERIA:")
        print(f"  Time ≤ 110% of legacy: {'✅ PASS' if unified_avg_time <= legacy_avg_time * 1.1 else '❌ FAIL'}")
        print(f"  Memory ≤ 120% of legacy: {'✅ PASS' if unified_avg_mem <= legacy_avg_mem * 1.2 else '❌ FAIL'}")
        print(f"  Cache hit rate > 95%: {'✅ PASS' if unified_avg_cache_rate > 0.95 else '❌ FAIL'}")
        print(f"{'='*60}\n")

    def save_results(self, output_file: str = None):
        """Save results to JSON file."""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"benchmark_results_{timestamp}.json"
        
        with open(output_file, "w") as f:
            json.dump(self.results, f, indent=2)
        
        print(f"Results saved to: {output_file}")


def main():
    """Main benchmark execution."""
    parser = argparse.ArgumentParser(description="Performance benchmarking")
    parser.add_argument(
        "--dataset",
        choices=["small", "medium", "large", "xlarge", "all"],
        default="medium",
        help="Dataset size to benchmark"
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of runs per benchmark"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file for results (JSON)"
    )
    
    args = parser.parse_args()
    
    benchmark = PerformanceBenchmark()
    
    if args.dataset == "all":
        datasets = ["small", "medium", "large"]
    else:
        datasets = [args.dataset]
    
    for dataset in datasets:
        benchmark.run_comparison(dataset, args.runs)
    
    benchmark.print_summary()
    benchmark.save_results(args.output)


if __name__ == "__main__":
    main()
```

---

## Running Benchmarks

### Step 1: Prepare Environment

```bash
# Ensure on feature branch
git checkout feature/unified-rule-routing

# Install profiling tools
pip install memory-profiler psutil

# Verify test data available
ls output/QC_CompleteVisits_* | head -5
```

### Step 2: Run Basic Benchmark

```bash
# Quick benchmark (medium dataset, 3 runs)
python scripts/benchmark_validation.py --dataset medium --runs 3

# Save results to file
python scripts/benchmark_validation.py --dataset medium --runs 5 --output bench_medium.json
```

### Step 3: Run Comprehensive Benchmark

```bash
# Benchmark all dataset sizes
python scripts/benchmark_validation.py --dataset all --runs 5 --output bench_comprehensive.json
```

### Step 4: Profile Memory Usage

```bash
# Profile memory line-by-line
python -m memory_profiler scripts/benchmark_validation.py --dataset small --runs 1
```

### Step 5: Profile CPU Usage

```bash
# Profile with cProfile
python -m cProfile -o benchmark.prof scripts/benchmark_validation.py --dataset medium --runs 1

# Analyze profile
python -c "import pstats; p = pstats.Stats('benchmark.prof'); p.sort_stats('cumulative').print_stats(30)"
```

---

## Expected Results

### Preliminary Performance Estimates

Based on unit test results:

| Dataset | Records | Legacy Time | Unified Time | Speedup |
|---------|---------|-------------|--------------|---------|
| Small | 100 | ~8s | ~6s | 1.3x |
| Medium | 500 | ~40s | ~30s | 1.3x |
| Large | 2000 | ~160s | ~120s | 1.3x |
| XLarge | 5000 | ~400s | ~300s | 1.3x |

### Performance Factors

**Unified Advantages**:
- Single validation pass (vs. 19)
- Rule caching
- Reduced overhead
- Optimized schema building

**Legacy Advantages**:
- Smaller rule sets per validation
- More granular error handling

**Expected Outcome**: Unified should be 1.2-1.5x faster

---

## Analysis and Optimization

### Bottleneck Identification

Use profiling to identify bottlenecks:

```python
# Run with profiler
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Run validation
validate_data_unified(data, "ptid", config)

profiler.disable()

# Analyze
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

### Common Bottlenecks

1. **Rule Loading**:
   - Check file I/O time
   - Verify JSON parsing efficiency
   - Ensure caching works

2. **Schema Building**:
   - Profile schema construction
   - Check for repeated building
   - Optimize data structures

3. **Validation**:
   - Profile Cerberus validation
   - Check rule complexity
   - Identify slow rules

4. **Error Processing**:
   - Profile error formatting
   - Check instrument inference
   - Optimize error collection

### Optimization Strategies

If performance doesn't meet targets:

1. **Improve Caching**:
   - Cache at multiple levels
   - Use LRU cache for schemas
   - Persist cache across runs

2. **Optimize Rule Loading**:
   - Use faster JSON parser (ujson)
   - Lazy load rule files
   - Precompile rules

3. **Parallelize**:
   - Validate records in parallel
   - Use multiprocessing
   - Batch processing

4. **Profile and Iterate**:
   - Identify specific bottlenecks
   - Optimize hot paths
   - Re-benchmark after changes

---

## Performance Report Template

### Create Performance Report

```markdown
# Performance Benchmark Results

**Date**: [Date]
**Tester**: [Name]
**Branch**: feature/unified-rule-routing
**Environment**: [OS, Python version, hardware]

## Configuration

- **CPU**: [Details]
- **RAM**: [Details]
- **Python**: [Version]
- **Dependencies**: [Key versions]

## Benchmark Results

### Summary

| Metric | Legacy | Unified | Improvement |
|--------|--------|---------|-------------|
| Avg Time (500 rec) | [X]s | [Y]s | [Z]% |
| Throughput | [X] rec/s | [Y] rec/s | [Z]% |
| Memory Usage | [X] MB | [Y] MB | [Z]% |
| Cache Hit Rate | N/A | [X]% | N/A |

### Detailed Results

[Include charts, graphs, detailed tables]

### Dataset: Small (100 records)

- Legacy: [time]s, [throughput] rec/s
- Unified: [time]s, [throughput] rec/s
- Speedup: [ratio]x

[Repeat for each dataset size]

## Analysis

### Performance Characteristics

[Describe performance patterns observed]

### Bottlenecks Identified

1. [Bottleneck 1] - [Impact]
2. [Bottleneck 2] - [Impact]

### Optimization Opportunities

1. [Opportunity 1] - [Potential gain]
2. [Opportunity 2] - [Potential gain]

## Recommendations

- [ ] Ready for production (performance acceptable)
- [ ] Needs optimization before production
- [ ] Requires further investigation

**Conclusion**: [Summary statement]

**Approved by**: [Name]
**Date**: [Date]
```

---

## Success Criteria Checklist

- [ ] Unified time ≤ 110% of legacy (target: < 100%)
- [ ] Memory usage ≤ 120% of legacy
- [ ] Cache hit rate > 95%
- [ ] Throughput ≥ 15 records/second
- [ ] Linear scaling up to 10,000 records
- [ ] No memory leaks detected
- [ ] CPU utilization reasonable
- [ ] Performance consistent across runs

---

## Next Steps

### After Successful Benchmarking

1. **Document Results**:
   - Create performance report
   - Include charts and graphs
   - Archive benchmark data

2. **Merge to Dev**:
   - Merge feature branch
   - Update CHANGELOG.md
   - Tag release candidate

3. **Production Deployment**:
   - Deploy to staging
   - Monitor performance
   - Gradual rollout

### If Performance Issues Found

1. **Profile and Analyze**:
   - Use profiling tools
   - Identify specific bottlenecks
   - Document findings

2. **Optimize**:
   - Implement optimizations
   - Re-run benchmarks
   - Verify improvements

3. **Iterate**:
   - Repeat until targets met
   - Document optimization journey
   - Update code and docs

---

## Contact and Support

**For Questions**:
- Review RULE_ROUTING.md for architecture
- Check CODE_REVIEW_SUMMARY.md for implementation
- Reference benchmark script for examples

**Escalation**:
- Open GitHub issue with label `performance`
- Include benchmark results and profiles
- Tag relevant team members

---

**Document Version**: 1.0  
**Last Updated**: February 14, 2026  
**Author**: AI Assistant
