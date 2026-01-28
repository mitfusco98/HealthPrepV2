#!/usr/bin/env python3
"""
Load Testing and Benchmarking Script for HealthPrep Document Processing

This script measures:
- Document processing throughput under varying loads
- CPU utilization patterns during processing
- Scaling characteristics with different worker counts
- Time to process batches of documents

Usage:
    python scripts/benchmark_processing.py --docs 10 --workers 4
    python scripts/benchmark_processing.py --analyze
    python scripts/benchmark_processing.py --quick

Environment Variables:
    DATABASE_URL: PostgreSQL connection string
    OCR_MAX_WORKERS: Number of OCR workers to use
"""

import os
import sys
import time
import argparse
import tempfile
import random
import threading
import psutil
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Text samples for test documents
TEXT_SAMPLES = {
    'light': "Patient Name: [REDACTED]\nDate: 01/01/2026\nNormal findings.",
    'medium': """MEDICAL REPORT
Patient Name: [REDACTED]
Date of Service: 01/01/2026
Provider: Dr. Smith

FINDINGS:
The examination was performed using standard protocols. All vital signs 
within normal limits. Blood pressure 120/80 mmHg, heart rate 72 bpm.

IMPRESSION:
No significant abnormalities detected. Recommend follow-up in 12 months.

RECOMMENDATIONS:
1. Continue current medications
2. Annual screening as scheduled
3. Healthy lifestyle maintenance
""",
    'heavy': """COMPREHENSIVE MEDICAL EXAMINATION REPORT

PATIENT INFORMATION:
Name: [REDACTED]
DOB: [REDACTED]
MRN: 123456789
Date of Service: 01/01/2026
Ordering Provider: Dr. Jane Smith, MD
Performing Provider: Dr. John Doe, MD

CLINICAL HISTORY:
Patient presents for routine annual physical examination. Past medical 
history significant for hypertension, well-controlled on current regimen.
No acute complaints. Family history notable for cardiovascular disease.

VITAL SIGNS:
Blood Pressure: 118/76 mmHg
Heart Rate: 68 bpm, regular
Temperature: 98.4F
Respiratory Rate: 16/min
Oxygen Saturation: 99% on room air

PHYSICAL EXAMINATION:
General: Alert and oriented, no acute distress
HEENT: Normocephalic, atraumatic. PERRLA. TMs clear bilaterally.
Cardiovascular: Regular rate and rhythm, no murmurs, rubs, or gallops
Pulmonary: Clear to auscultation bilaterally

ASSESSMENT AND PLAN:
1. Hypertension - well controlled, continue lisinopril 10mg daily
2. Health maintenance - up to date on all screenings
3. Follow-up in 12 months for annual examination
"""
}


def generate_test_pdf(num_pages: int = 1, text_density: str = 'medium') -> bytes:
    """Generate a test PDF with specified characteristics"""
    text = TEXT_SAMPLES.get(text_density, TEXT_SAMPLES['medium'])
    
    try:
        from reportlab.lib.pagesizes import letter  # type: ignore
        from reportlab.pdfgen import canvas  # type: ignore
        from io import BytesIO
        
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        
        for page in range(num_pages):
            c.setFont("Helvetica", 12)
            y_position = 750
            for line in text.split('\n'):
                if y_position < 50:
                    break
                c.drawString(72, y_position, line.strip())
                y_position -= 14
            
            c.drawString(500, 30, f"Page {page + 1}")
            c.showPage()
        
        c.save()
        buffer.seek(0)
        return buffer.read()
        
    except ImportError:
        # Fallback: create a simple text file if reportlab not available
        return (text * num_pages).encode('utf-8')


class BenchmarkRunner:
    """Runs document processing benchmarks"""
    
    def __init__(self, num_workers: Optional[int] = None):
        self.num_workers = num_workers if num_workers is not None else self._get_default_workers()
        self.results: List[Dict] = []
        self.cpu_samples: List[Dict] = []
        self.memory_samples: List[Dict] = []
        self._stop_monitoring = threading.Event()
    
    def _get_default_workers(self) -> int:
        """Get default worker count based on system"""
        env_workers = os.environ.get('OCR_MAX_WORKERS')
        if env_workers:
            try:
                return int(env_workers)
            except ValueError:
                pass
        cpu_count = psutil.cpu_count()
        return max(2, (cpu_count or 4) - 1)
    
    def _monitor_resources(self, interval: float = 0.5):
        """Background thread to monitor CPU and memory"""
        process = psutil.Process()
        
        while not self._stop_monitoring.is_set():
            try:
                cpu_percent = psutil.cpu_percent(interval=None)
                memory = process.memory_info()
                
                self.cpu_samples.append({
                    'timestamp': time.time(),
                    'cpu_percent': cpu_percent,
                    'memory_mb': memory.rss / (1024 * 1024)
                })
            except Exception:
                pass
            
            time.sleep(interval)
    
    def run_document_benchmark(self, num_docs: int, pages_per_doc: int = 3) -> Dict[str, Any]:
        """Run benchmark processing multiple documents"""
        print(f"\n{'='*60}")
        print(f"Document Processing Benchmark")
        print(f"Documents: {num_docs}, Pages per doc: {pages_per_doc}")
        print(f"Workers: {self.num_workers}")
        print(f"{'='*60}\n")
        
        # Import app context
        from app import app
        
        # Start resource monitoring
        self._stop_monitoring.clear()
        self.cpu_samples = []
        monitor_thread = threading.Thread(target=self._monitor_resources)
        monitor_thread.start()
        
        start_time = time.time()
        processing_times: List[float] = []
        
        with app.app_context():
            from ocr.processor import OCRProcessor
            
            processor = OCRProcessor()
            
            # Generate test documents
            print("Generating test documents...")
            test_docs = []
            for i in range(num_docs):
                density = random.choice(['light', 'medium', 'heavy'])
                pdf_bytes = generate_test_pdf(pages_per_doc, density)
                test_docs.append({
                    'id': f'bench_{i}',
                    'pages': pages_per_doc,
                    'density': density,
                    'size': len(pdf_bytes),
                    'content': pdf_bytes
                })
            
            print(f"Generated {num_docs} test documents\n")
            
            # Process documents
            with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
                futures = {}
                
                for doc in test_docs:
                    # Create temp file
                    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                        f.write(doc['content'])
                        temp_path = f.name
                    
                    doc['temp_path'] = temp_path
                    
                    # Submit for processing
                    future = executor.submit(
                        self._process_single_doc,
                        processor, doc
                    )
                    futures[future] = doc
                
                # Collect results
                completed = 0
                for future in as_completed(futures):
                    doc = futures[future]
                    try:
                        result = future.result()
                        processing_times.append(result)
                        completed += 1
                        
                        # Progress update
                        if completed % 10 == 0 or completed == num_docs:
                            elapsed = time.time() - start_time
                            rate = completed / elapsed if elapsed > 0 else 0
                            print(f"  Progress: {completed}/{num_docs} docs "
                                  f"({rate:.1f} docs/sec)")
                        
                    except Exception as e:
                        print(f"  Error processing {doc['id']}: {e}")
                    
                    finally:
                        # Cleanup temp file
                        try:
                            os.unlink(doc['temp_path'])
                        except Exception:
                            pass
        
        # Stop monitoring
        self._stop_monitoring.set()
        monitor_thread.join(timeout=2)
        
        total_time = time.time() - start_time
        
        # Calculate statistics
        if processing_times:
            avg_time = sum(processing_times) / len(processing_times)
            max_time = max(processing_times)
            min_time = min(processing_times)
            
            # 95th percentile
            sorted_times = sorted(processing_times)
            p95_idx = int(len(sorted_times) * 0.95)
            p95_time = sorted_times[min(p95_idx, len(sorted_times) - 1)]
        else:
            avg_time = max_time = min_time = p95_time = 0.0
        
        # Calculate CPU statistics
        if self.cpu_samples:
            avg_cpu = sum(s['cpu_percent'] for s in self.cpu_samples) / len(self.cpu_samples)
            max_cpu = max(s['cpu_percent'] for s in self.cpu_samples)
            avg_memory = sum(s['memory_mb'] for s in self.cpu_samples) / len(self.cpu_samples)
        else:
            avg_cpu = max_cpu = avg_memory = 0.0
        
        results = {
            'benchmark_config': {
                'num_docs': num_docs,
                'pages_per_doc': pages_per_doc,
                'total_pages': num_docs * pages_per_doc,
                'workers': self.num_workers
            },
            'timing': {
                'total_seconds': round(total_time, 2),
                'avg_per_doc': round(avg_time, 3),
                'min_per_doc': round(min_time, 3),
                'max_per_doc': round(max_time, 3),
                'p95_per_doc': round(p95_time, 3)
            },
            'throughput': {
                'docs_per_second': round(num_docs / total_time, 2) if total_time > 0 else 0,
                'pages_per_second': round((num_docs * pages_per_doc) / total_time, 2) if total_time > 0 else 0
            },
            'resources': {
                'avg_cpu_percent': round(avg_cpu, 1),
                'max_cpu_percent': round(max_cpu, 1),
                'avg_memory_mb': round(avg_memory, 1)
            },
            'sla_compliance': {
                'target_seconds': 10,
                'max_doc_time': round(max_time, 3),
                'meets_sla': max_time <= 10,
                'p95_meets_sla': p95_time <= 10
            },
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self._print_results(results)
        return results
    
    def _process_single_doc(self, processor: Any, doc: Dict) -> float:
        """Process a single document and return processing time"""
        start = time.time()
        
        try:
            text, confidence = processor._extract_text(doc['temp_path'])
        except Exception:
            raise
        
        return time.time() - start
    
    def _print_results(self, results: Dict):
        """Print benchmark results in a formatted way"""
        print(f"\n{'='*60}")
        print("BENCHMARK RESULTS")
        print(f"{'='*60}")
        
        config = results['benchmark_config']
        timing = results['timing']
        throughput = results['throughput']
        resources = results['resources']
        sla = results['sla_compliance']
        
        print(f"\nConfiguration:")
        print(f"  Documents: {config['num_docs']}")
        print(f"  Pages per doc: {config['pages_per_doc']}")
        print(f"  Total pages: {config['total_pages']}")
        print(f"  Workers: {config['workers']}")
        
        print(f"\nTiming:")
        print(f"  Total time: {timing['total_seconds']}s")
        print(f"  Avg per doc: {timing['avg_per_doc']}s")
        print(f"  Min per doc: {timing['min_per_doc']}s")
        print(f"  Max per doc: {timing['max_per_doc']}s")
        print(f"  P95 per doc: {timing['p95_per_doc']}s")
        
        print(f"\nThroughput:")
        print(f"  Documents/sec: {throughput['docs_per_second']}")
        print(f"  Pages/sec: {throughput['pages_per_second']}")
        
        print(f"\nResource Usage:")
        print(f"  Avg CPU: {resources['avg_cpu_percent']}%")
        print(f"  Max CPU: {resources['max_cpu_percent']}%")
        print(f"  Avg Memory: {resources['avg_memory_mb']} MB")
        
        print(f"\nSLA Compliance (10s target):")
        status = "PASS" if sla['meets_sla'] else "FAIL"
        print(f"  Max document time: {sla['max_doc_time']}s - {status}")
        status = "PASS" if sla['p95_meets_sla'] else "FAIL"
        print(f"  P95 document time: {timing['p95_per_doc']}s - {status}")
        
        print(f"\n{'='*60}\n")
    
    def run_scaling_analysis(self, max_workers: Optional[int] = None) -> Dict[str, Any]:
        """Test scaling characteristics with different worker counts"""
        cpu_count = psutil.cpu_count()
        if max_workers is None:
            max_workers = cpu_count if cpu_count else 4
        
        print(f"\n{'='*60}")
        print("SCALING ANALYSIS")
        print(f"Testing worker counts from 1 to {max_workers}")
        print(f"{'='*60}\n")
        
        scaling_results = []
        
        for workers in range(1, max_workers + 1):
            print(f"\nTesting with {workers} workers...")
            self.num_workers = workers
            self.cpu_samples = []
            
            # Run small benchmark for each worker count
            result = self.run_document_benchmark(num_docs=10, pages_per_doc=2)
            result['workers'] = workers
            scaling_results.append(result)
        
        # Calculate scaling efficiency
        if scaling_results:
            baseline = scaling_results[0]['throughput']['pages_per_second']
            
            for result in scaling_results:
                workers = result['workers']
                current = result['throughput']['pages_per_second']
                ideal = baseline * workers
                efficiency = (current / ideal * 100) if ideal > 0 else 0
                result['scaling_efficiency'] = round(efficiency, 1)
        
        # Print scaling summary
        print(f"\n{'='*60}")
        print("SCALING SUMMARY")
        print(f"{'='*60}")
        print(f"\n{'Workers':<10} {'Pages/sec':<12} {'Efficiency':<12} {'CPU %':<10}")
        print("-" * 44)
        
        for result in scaling_results:
            print(f"{result['workers']:<10} "
                  f"{result['throughput']['pages_per_second']:<12} "
                  f"{result.get('scaling_efficiency', 0):<12}% "
                  f"{result['resources']['avg_cpu_percent']:<10}")
        
        return {
            'scaling_results': scaling_results,
            'optimal_workers': self._find_optimal_workers(scaling_results)
        }
    
    def _find_optimal_workers(self, results: List[Dict]) -> int:
        """Find optimal worker count based on throughput/efficiency balance"""
        if not results:
            return 1
        
        # Find point of diminishing returns (efficiency drops below 70%)
        for result in results:
            if result.get('scaling_efficiency', 100) < 70:
                return max(1, result['workers'] - 1)
        
        # If all efficient, return max
        return results[-1]['workers']


def main():
    parser = argparse.ArgumentParser(description='HealthPrep Processing Benchmark')
    
    parser.add_argument('--docs', type=int, default=10,
                        help='Number of documents to process (default: 10)')
    parser.add_argument('--pages', type=int, default=3,
                        help='Pages per document (default: 3)')
    parser.add_argument('--workers', type=int, default=None,
                        help='Number of OCR workers (default: auto)')
    parser.add_argument('--analyze', action='store_true',
                        help='Run scaling analysis')
    parser.add_argument('--quick', action='store_true',
                        help='Run quick benchmark (5 docs, 1 page each)')
    parser.add_argument('--output', type=str, default=None,
                        help='Output file for JSON results')
    
    args = parser.parse_args()
    
    runner = BenchmarkRunner(num_workers=args.workers)
    
    if args.analyze:
        results = runner.run_scaling_analysis()
    elif args.quick:
        results = runner.run_document_benchmark(num_docs=5, pages_per_doc=1)
    else:
        results = runner.run_document_benchmark(
            num_docs=args.docs,
            pages_per_doc=args.pages
        )
    
    if args.output:
        import json
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {args.output}")


if __name__ == '__main__':
    main()
