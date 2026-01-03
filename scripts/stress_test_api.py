#!/usr/bin/env python3
"""
API Stress Test and Security Load Testing Script for HealthPrep

This script simulates:
- High volume concurrent API requests
- Rate limiting verification
- Document processing under severe load
- Login brute force simulation (to verify rate limiting works)

Usage:
    python scripts/stress_test_api.py --test rate_limit
    python scripts/stress_test_api.py --test document_load --docs 50
    python scripts/stress_test_api.py --test concurrent_requests --requests 100
    python scripts/stress_test_api.py --all

Environment Variables:
    DATABASE_URL: PostgreSQL connection string
    TEST_USERNAME: Optional test user username
    TEST_PASSWORD: Optional test user password
"""

import os
import sys
import time
import argparse
import threading
import json
import random
import string
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class StressTestResult:
    """Result of a stress test"""
    test_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    rate_limited_requests: int
    total_time_seconds: float
    requests_per_second: float
    avg_response_time_ms: float
    max_response_time_ms: float
    min_response_time_ms: float
    p95_response_time_ms: float
    errors: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            'test_name': self.test_name,
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'rate_limited_requests': self.rate_limited_requests,
            'total_time_seconds': round(self.total_time_seconds, 2),
            'requests_per_second': round(self.requests_per_second, 2),
            'avg_response_time_ms': round(self.avg_response_time_ms, 2),
            'max_response_time_ms': round(self.max_response_time_ms, 2),
            'min_response_time_ms': round(self.min_response_time_ms, 2),
            'p95_response_time_ms': round(self.p95_response_time_ms, 2),
            'errors': self.errors[:10],
            'timestamp': self.timestamp
        }


class StressTestRunner:
    """Runs API stress tests"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:5000"):
        self.base_url = base_url
        self.session = None
        
    def _get_session(self):
        """Get or create requests session"""
        if self.session is None:
            import requests
            self.session = requests.Session()
        return self.session
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Tuple[int, float, Optional[str]]:
        """
        Make an HTTP request and return (status_code, response_time_ms, error_message)
        """
        import requests
        
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            if method == 'GET':
                response = requests.get(url, timeout=30, **kwargs)
            elif method == 'POST':
                response = requests.post(url, timeout=30, **kwargs)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            elapsed_ms = (time.time() - start_time) * 1000
            return response.status_code, elapsed_ms, None
            
        except requests.exceptions.Timeout:
            elapsed_ms = (time.time() - start_time) * 1000
            return 0, elapsed_ms, "Request timed out"
        except requests.exceptions.ConnectionError as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return 0, elapsed_ms, f"Connection error: {str(e)}"
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return 0, elapsed_ms, f"Error: {str(e)}"
    
    def test_rate_limiting(self, num_attempts: int = 20) -> StressTestResult:
        """
        Test that rate limiting is working on the login endpoint.
        Should see 429 responses after exceeding the limit.
        """
        print(f"\n{'='*60}")
        print("RATE LIMITING TEST")
        print(f"Testing {num_attempts} rapid login attempts")
        print(f"{'='*60}\n")
        
        response_times = []
        successful = 0
        failed = 0
        rate_limited = 0
        errors = []
        
        start_time = time.time()
        
        for i in range(num_attempts):
            random_username = ''.join(random.choices(string.ascii_lowercase, k=8))
            random_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            
            status_code, elapsed_ms, error = self._make_request(
                'POST',
                '/login',
                data={'username': random_username, 'password': random_password},
                allow_redirects=False
            )
            
            response_times.append(elapsed_ms)
            
            if error:
                failed += 1
                errors.append(error)
            elif status_code == 429:
                rate_limited += 1
                print(f"  Request {i+1}: Rate limited (429) - {elapsed_ms:.0f}ms")
            elif status_code in [200, 302]:
                successful += 1
                print(f"  Request {i+1}: Normal response ({status_code}) - {elapsed_ms:.0f}ms")
            else:
                failed += 1
                print(f"  Request {i+1}: Status {status_code} - {elapsed_ms:.0f}ms")
        
        total_time = time.time() - start_time
        
        sorted_times = sorted(response_times)
        p95_idx = int(len(sorted_times) * 0.95)
        
        result = StressTestResult(
            test_name="Rate Limiting",
            total_requests=num_attempts,
            successful_requests=successful,
            failed_requests=failed,
            rate_limited_requests=rate_limited,
            total_time_seconds=total_time,
            requests_per_second=num_attempts / total_time if total_time > 0 else 0,
            avg_response_time_ms=sum(response_times) / len(response_times) if response_times else 0,
            max_response_time_ms=max(response_times) if response_times else 0,
            min_response_time_ms=min(response_times) if response_times else 0,
            p95_response_time_ms=sorted_times[min(p95_idx, len(sorted_times) - 1)] if sorted_times else 0,
            errors=errors
        )
        
        self._print_result(result)
        
        if rate_limited > 0:
            print(f"\n  RATE LIMITING WORKING: {rate_limited} requests were rate limited")
        else:
            print(f"\n  WARNING: No requests were rate limited - check rate limiting configuration")
        
        return result
    
    def test_concurrent_requests(self, num_requests: int = 100, num_workers: int = 10) -> StressTestResult:
        """
        Test handling of concurrent requests to public endpoints
        """
        print(f"\n{'='*60}")
        print("CONCURRENT REQUESTS TEST")
        print(f"Requests: {num_requests}, Workers: {num_workers}")
        print(f"{'='*60}\n")
        
        endpoints = [
            ('GET', '/'),
            ('GET', '/login'),
        ]
        
        response_times = []
        successful = 0
        failed = 0
        rate_limited = 0
        errors = []
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            
            for i in range(num_requests):
                method, endpoint = random.choice(endpoints)
                future = executor.submit(self._make_request, method, endpoint)
                futures.append(future)
            
            completed = 0
            for future in as_completed(futures):
                completed += 1
                status_code, elapsed_ms, error = future.result()
                response_times.append(elapsed_ms)
                
                if error:
                    failed += 1
                    errors.append(error)
                elif status_code == 429:
                    rate_limited += 1
                elif 200 <= status_code < 400:
                    successful += 1
                else:
                    failed += 1
                
                if completed % 20 == 0:
                    print(f"  Progress: {completed}/{num_requests}")
        
        total_time = time.time() - start_time
        
        sorted_times = sorted(response_times)
        p95_idx = int(len(sorted_times) * 0.95)
        
        result = StressTestResult(
            test_name="Concurrent Requests",
            total_requests=num_requests,
            successful_requests=successful,
            failed_requests=failed,
            rate_limited_requests=rate_limited,
            total_time_seconds=total_time,
            requests_per_second=num_requests / total_time if total_time > 0 else 0,
            avg_response_time_ms=sum(response_times) / len(response_times) if response_times else 0,
            max_response_time_ms=max(response_times) if response_times else 0,
            min_response_time_ms=min(response_times) if response_times else 0,
            p95_response_time_ms=sorted_times[min(p95_idx, len(sorted_times) - 1)] if sorted_times else 0,
            errors=errors
        )
        
        self._print_result(result)
        return result
    
    def test_document_load(self, num_docs: int = 20) -> StressTestResult:
        """
        Test document processing under severe load using the existing benchmark
        """
        print(f"\n{'='*60}")
        print("DOCUMENT PROCESSING LOAD TEST")
        print(f"Documents: {num_docs}")
        print(f"{'='*60}\n")
        
        from app import app
        
        response_times = []
        successful = 0
        failed = 0
        errors = []
        
        start_time = time.time()
        
        with app.app_context():
            try:
                from ocr.processor import OCRProcessor
                from scripts.benchmark_processing import generate_test_pdf, BenchmarkRunner
                
                runner = BenchmarkRunner()
                result_dict = runner.run_document_benchmark(num_docs=num_docs, pages_per_doc=2)
                
                successful = num_docs
                avg_time_ms = result_dict['timing']['avg_per_doc'] * 1000
                max_time_ms = result_dict['timing']['max_per_doc'] * 1000
                min_time_ms = result_dict['timing']['min_per_doc'] * 1000
                p95_time_ms = result_dict['timing']['p95_per_doc'] * 1000
                
                response_times = [avg_time_ms] * num_docs
                
            except Exception as e:
                failed = num_docs
                errors.append(str(e))
                avg_time_ms = max_time_ms = min_time_ms = p95_time_ms = 0
        
        total_time = time.time() - start_time
        
        result = StressTestResult(
            test_name="Document Processing Load",
            total_requests=num_docs,
            successful_requests=successful,
            failed_requests=failed,
            rate_limited_requests=0,
            total_time_seconds=total_time,
            requests_per_second=num_docs / total_time if total_time > 0 else 0,
            avg_response_time_ms=avg_time_ms,
            max_response_time_ms=max_time_ms,
            min_response_time_ms=min_time_ms,
            p95_response_time_ms=p95_time_ms,
            errors=errors
        )
        
        self._print_result(result)
        return result
    
    def test_memory_pressure(self, duration_seconds: int = 30) -> StressTestResult:
        """
        Simulate memory pressure by making rapid requests and monitoring memory usage
        """
        print(f"\n{'='*60}")
        print("MEMORY PRESSURE TEST")
        print(f"Duration: {duration_seconds} seconds")
        print(f"{'='*60}\n")
        
        import psutil
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / (1024 * 1024)
        
        response_times = []
        successful = 0
        failed = 0
        errors = []
        memory_samples = []
        
        start_time = time.time()
        
        while time.time() - start_time < duration_seconds:
            status_code, elapsed_ms, error = self._make_request('GET', '/')
            response_times.append(elapsed_ms)
            
            if error:
                failed += 1
            elif 200 <= status_code < 400:
                successful += 1
            else:
                failed += 1
            
            memory_samples.append(process.memory_info().rss / (1024 * 1024))
        
        total_time = time.time() - start_time
        final_memory = process.memory_info().rss / (1024 * 1024)
        memory_growth = final_memory - initial_memory
        
        sorted_times = sorted(response_times)
        p95_idx = int(len(sorted_times) * 0.95)
        
        result = StressTestResult(
            test_name="Memory Pressure",
            total_requests=successful + failed,
            successful_requests=successful,
            failed_requests=failed,
            rate_limited_requests=0,
            total_time_seconds=total_time,
            requests_per_second=(successful + failed) / total_time if total_time > 0 else 0,
            avg_response_time_ms=sum(response_times) / len(response_times) if response_times else 0,
            max_response_time_ms=max(response_times) if response_times else 0,
            min_response_time_ms=min(response_times) if response_times else 0,
            p95_response_time_ms=sorted_times[min(p95_idx, len(sorted_times) - 1)] if sorted_times else 0,
            errors=errors
        )
        
        self._print_result(result)
        print(f"\n  Memory: {initial_memory:.1f}MB -> {final_memory:.1f}MB (growth: {memory_growth:+.1f}MB)")
        
        return result
    
    def _print_result(self, result: StressTestResult):
        """Print test result summary"""
        print(f"\n{'='*60}")
        print(f"TEST RESULTS: {result.test_name}")
        print(f"{'='*60}")
        print(f"  Total Requests: {result.total_requests}")
        print(f"  Successful: {result.successful_requests}")
        print(f"  Failed: {result.failed_requests}")
        print(f"  Rate Limited: {result.rate_limited_requests}")
        print(f"  Total Time: {result.total_time_seconds:.2f}s")
        print(f"  Requests/sec: {result.requests_per_second:.2f}")
        print(f"\n  Response Times:")
        print(f"    Average: {result.avg_response_time_ms:.2f}ms")
        print(f"    Min: {result.min_response_time_ms:.2f}ms")
        print(f"    Max: {result.max_response_time_ms:.2f}ms")
        print(f"    P95: {result.p95_response_time_ms:.2f}ms")
        
        if result.errors:
            print(f"\n  Errors ({len(result.errors)}):")
            for err in result.errors[:5]:
                print(f"    - {err}")


def main():
    parser = argparse.ArgumentParser(description='HealthPrep API Stress Test')
    
    parser.add_argument('--test', type=str, choices=['rate_limit', 'concurrent', 'document_load', 'memory'],
                        help='Test to run')
    parser.add_argument('--all', action='store_true', help='Run all tests')
    parser.add_argument('--requests', type=int, default=100, help='Number of requests for concurrent test')
    parser.add_argument('--docs', type=int, default=20, help='Number of documents for load test')
    parser.add_argument('--duration', type=int, default=30, help='Duration for memory test (seconds)')
    parser.add_argument('--output', type=str, help='Output file for JSON results')
    parser.add_argument('--base-url', type=str, default='http://127.0.0.1:5000', help='Base URL for API')
    
    args = parser.parse_args()
    
    runner = StressTestRunner(base_url=args.base_url)
    results = []
    
    if args.all or args.test == 'rate_limit':
        results.append(runner.test_rate_limiting(num_attempts=15))
    
    if args.all or args.test == 'concurrent':
        results.append(runner.test_concurrent_requests(num_requests=args.requests))
    
    if args.all or args.test == 'document_load':
        results.append(runner.test_document_load(num_docs=args.docs))
    
    if args.all or args.test == 'memory':
        results.append(runner.test_memory_pressure(duration_seconds=args.duration))
    
    if not args.all and not args.test:
        print("No test specified. Use --test or --all")
        parser.print_help()
        return
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump([r.to_dict() for r in results], f, indent=2)
        print(f"\nResults saved to {args.output}")
    
    print(f"\n{'='*60}")
    print("ALL TESTS COMPLETE")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
