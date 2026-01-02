"""
Performance Monitoring and Instrumentation for HealthPrep
Tracks CPU usage, processing duration, queue depth, and throughput metrics

Provides:
- Per-job CPU and wall-clock timing
- Queue depth monitoring
- Pages-per-second throughput metrics
- Memory usage tracking
- Scalability analysis
"""
import os
import time
import psutil
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import deque
import json

logger = logging.getLogger(__name__)


@dataclass
class JobMetrics:
    """Metrics for a single processing job"""
    job_id: str
    job_type: str  # 'ocr', 'fhir_sync', 'screening_update', etc.
    start_time: float
    end_time: Optional[float] = None
    cpu_time_start: float = 0.0
    cpu_time_end: float = 0.0
    memory_start_mb: float = 0.0
    memory_end_mb: float = 0.0
    pages_processed: int = 0
    bytes_processed: int = 0
    success: bool = True
    error_message: Optional[str] = None
    
    @property
    def wall_time_seconds(self) -> float:
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time
    
    @property
    def cpu_time_seconds(self) -> float:
        return self.cpu_time_end - self.cpu_time_start
    
    @property
    def memory_delta_mb(self) -> float:
        return self.memory_end_mb - self.memory_start_mb
    
    @property
    def pages_per_second(self) -> float:
        if self.wall_time_seconds <= 0 or self.pages_processed <= 0:
            return 0.0
        return self.pages_processed / self.wall_time_seconds
    
    @property
    def bytes_per_second(self) -> float:
        if self.wall_time_seconds <= 0 or self.bytes_processed <= 0:
            return 0.0
        return self.bytes_processed / self.wall_time_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'job_id': self.job_id,
            'job_type': self.job_type,
            'wall_time_seconds': round(self.wall_time_seconds, 3),
            'cpu_time_seconds': round(self.cpu_time_seconds, 3),
            'memory_delta_mb': round(self.memory_delta_mb, 2),
            'pages_processed': self.pages_processed,
            'bytes_processed': self.bytes_processed,
            'pages_per_second': round(self.pages_per_second, 2),
            'bytes_per_second': round(self.bytes_per_second, 0),
            'success': self.success,
            'error_message': self.error_message,
            'timestamp': datetime.utcnow().isoformat()
        }


class PerformanceMonitor:
    """
    Central performance monitoring for document processing
    
    Thread-safe singleton that tracks:
    - Active job metrics
    - Historical performance data
    - System resource utilization
    - Queue depth and throughput
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._active_jobs: Dict[str, JobMetrics] = {}
        self._completed_jobs: deque = deque(maxlen=1000)  # Keep last 1000 jobs
        self._lock = threading.Lock()
        
        # Aggregated metrics
        self._total_jobs_completed = 0
        self._total_jobs_failed = 0
        self._total_pages_processed = 0
        self._total_bytes_processed = 0
        self._total_processing_time = 0.0
        
        # System baseline
        self._process = psutil.Process()
        self._cpu_count = psutil.cpu_count() or 1
        
        logger.info(f"PerformanceMonitor initialized with {self._cpu_count} CPU cores")
    
    def start_job(self, job_id: str, job_type: str = 'ocr') -> JobMetrics:
        """Start tracking a new job"""
        metrics = JobMetrics(
            job_id=job_id,
            job_type=job_type,
            start_time=time.time(),
            cpu_time_start=self._get_cpu_time(),
            memory_start_mb=self._get_memory_mb()
        )
        
        with self._lock:
            self._active_jobs[job_id] = metrics
        
        logger.debug(f"Started tracking job {job_id} (type: {job_type})")
        return metrics
    
    def update_job(self, job_id: str, pages: int = 0, bytes_processed: int = 0):
        """Update job progress"""
        with self._lock:
            if job_id in self._active_jobs:
                self._active_jobs[job_id].pages_processed += pages
                self._active_jobs[job_id].bytes_processed += bytes_processed
    
    def complete_job(self, job_id: str, success: bool = True, error_message: Optional[str] = None) -> Optional[JobMetrics]:
        """Complete job tracking and record metrics"""
        with self._lock:
            if job_id not in self._active_jobs:
                logger.warning(f"Job {job_id} not found in active jobs")
                return None
            
            metrics = self._active_jobs.pop(job_id)
            metrics.end_time = time.time()
            metrics.cpu_time_end = self._get_cpu_time()
            metrics.memory_end_mb = self._get_memory_mb()
            metrics.success = success
            metrics.error_message = error_message
            
            # Update aggregates
            self._total_jobs_completed += 1
            if not success:
                self._total_jobs_failed += 1
            self._total_pages_processed += metrics.pages_processed
            self._total_bytes_processed += metrics.bytes_processed
            self._total_processing_time += metrics.wall_time_seconds
            
            self._completed_jobs.append(metrics)
        
        logger.info(
            f"Job {job_id} completed: {metrics.wall_time_seconds:.2f}s wall, "
            f"{metrics.pages_processed} pages, {metrics.pages_per_second:.1f} pps"
        )
        
        return metrics
    
    def _get_cpu_time(self) -> float:
        """Get current process CPU time"""
        try:
            times = self._process.cpu_times()
            return times.user + times.system
        except Exception:
            return 0.0
    
    def _get_memory_mb(self) -> float:
        """Get current process memory usage in MB"""
        try:
            return self._process.memory_info().rss / (1024 * 1024)
        except Exception:
            return 0.0
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system resource metrics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            
            return {
                'cpu_percent': cpu_percent,
                'cpu_count': self._cpu_count,
                'memory_total_gb': round(memory.total / (1024**3), 2),
                'memory_used_gb': round(memory.used / (1024**3), 2),
                'memory_percent': memory.percent,
                'process_memory_mb': round(self._get_memory_mb(), 2),
                'active_jobs': len(self._active_jobs),
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {}
    
    def get_queue_metrics(self, alert_threshold: int = 50) -> Dict[str, Any]:
        """Get RQ queue depth and status with alerting
        
        Args:
            alert_threshold: Number of pending jobs to trigger a warning alert (default: 50)
        
        Returns:
            Queue metrics dict with alert status
        """
        try:
            from redis import Redis
            from rq import Queue
            
            redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
            conn = Redis.from_url(redis_url)
            
            queue_names = ['fhir_priority', 'fhir_processing']
            metrics = {
                'timestamp': datetime.utcnow().isoformat(),
                'queues': {},
                'total_pending': 0,
                'total_started': 0,
                'alert_threshold': alert_threshold,
                'alert_triggered': False
            }
            
            for name in queue_names:
                queue = Queue(name, connection=conn)
                pending = queue.count
                metrics['queues'][name] = {
                    'pending': pending,
                    'started': queue.started_job_registry.count,
                    'failed': queue.failed_job_registry.count
                }
                metrics['total_pending'] += pending
                metrics['total_started'] += queue.started_job_registry.count
            
            # Queue depth alerting - log warning when threshold exceeded
            if metrics['total_pending'] > alert_threshold:
                metrics['alert_triggered'] = True
                logger.warning(
                    f"QUEUE DEPTH ALERT: {metrics['total_pending']} pending jobs exceeds "
                    f"threshold of {alert_threshold}. SLA may be at risk. "
                    f"Consider scaling workers or investigating backlog."
                )
            
            return metrics
            
        except Exception as e:
            logger.warning(f"Could not get queue metrics: {e}")
            return {'error': str(e)}
    
    def get_throughput_metrics(self, window_seconds: int = 300) -> Dict[str, Any]:
        """Get throughput metrics for the specified time window"""
        cutoff = time.time() - window_seconds
        
        with self._lock:
            recent_jobs = [
                job for job in self._completed_jobs
                if job.end_time and job.end_time >= cutoff
            ]
        
        if not recent_jobs:
            return {
                'window_seconds': window_seconds,
                'jobs_completed': 0,
                'pages_processed': 0,
                'avg_job_time': 0,
                'pages_per_second': 0,
                'bytes_per_second': 0,
                'success_rate': 0
            }
        
        total_pages = sum(j.pages_processed for j in recent_jobs)
        total_bytes = sum(j.bytes_processed for j in recent_jobs)
        total_time = sum(j.wall_time_seconds for j in recent_jobs)
        successful = sum(1 for j in recent_jobs if j.success)
        
        return {
            'window_seconds': window_seconds,
            'jobs_completed': len(recent_jobs),
            'pages_processed': total_pages,
            'bytes_processed': total_bytes,
            'avg_job_time': round(total_time / len(recent_jobs), 2) if recent_jobs else 0,
            'pages_per_second': round(total_pages / window_seconds, 2),
            'bytes_per_second': round(total_bytes / window_seconds, 0),
            'success_rate': round(successful / len(recent_jobs) * 100, 1) if recent_jobs else 0
        }
    
    def get_scaling_recommendations(self) -> Dict[str, Any]:
        """Analyze performance and provide scaling recommendations"""
        system = self.get_system_metrics()
        throughput = self.get_throughput_metrics(60)  # Last minute
        queue = self.get_queue_metrics()
        
        recommendations = []
        scaling_factor = 1.0
        
        # CPU-based recommendations
        cpu_percent = system.get('cpu_percent', 0)
        if cpu_percent > 80:
            recommendations.append({
                'type': 'scale_up',
                'reason': f'High CPU utilization ({cpu_percent}%)',
                'action': 'Add more worker instances or increase OCR_MAX_WORKERS'
            })
            scaling_factor = 1.5
        elif cpu_percent < 30 and throughput.get('jobs_completed', 0) > 0:
            recommendations.append({
                'type': 'optimize',
                'reason': f'Low CPU utilization ({cpu_percent}%) with active processing',
                'action': 'Consider increasing parallel workers to improve throughput'
            })
        
        # Queue depth recommendations
        pending = queue.get('total_pending', 0)
        if pending > 100:
            recommendations.append({
                'type': 'scale_up',
                'reason': f'High queue depth ({pending} pending jobs)',
                'action': 'Add more worker instances to reduce backlog'
            })
            scaling_factor = max(scaling_factor, 2.0)
        
        # Throughput recommendations
        avg_job_time = throughput.get('avg_job_time', 0)
        if avg_job_time > 10:  # >10 seconds per job
            recommendations.append({
                'type': 'performance',
                'reason': f'High average job time ({avg_job_time}s)',
                'action': 'Consider page-level parallelism for large documents'
            })
        
        # Memory recommendations
        memory_percent = system.get('memory_percent', 0)
        if memory_percent > 85:
            recommendations.append({
                'type': 'memory',
                'reason': f'High memory utilization ({memory_percent}%)',
                'action': 'Reduce OCR_MAX_WORKERS or add more memory'
            })
        
        return {
            'current_state': {
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'queue_depth': pending,
                'avg_job_time': avg_job_time,
                'pages_per_second': throughput.get('pages_per_second', 0)
            },
            'recommendations': recommendations,
            'suggested_scaling_factor': scaling_factor,
            'can_meet_10s_sla': avg_job_time <= 10 or throughput.get('jobs_completed', 0) == 0
        }
    
    def get_full_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        return {
            'system': self.get_system_metrics(),
            'queue': self.get_queue_metrics(),
            'throughput_1min': self.get_throughput_metrics(60),
            'throughput_5min': self.get_throughput_metrics(300),
            'scaling': self.get_scaling_recommendations(),
            'totals': {
                'jobs_completed': self._total_jobs_completed,
                'jobs_failed': self._total_jobs_failed,
                'pages_processed': self._total_pages_processed,
                'bytes_processed': self._total_bytes_processed,
                'total_processing_time': round(self._total_processing_time, 2)
            },
            'active_jobs': len(self._active_jobs)
        }


# Decorator for automatic job tracking
def track_performance(job_type: str = 'ocr'):
    """Decorator to automatically track function performance"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            monitor = PerformanceMonitor()
            job_id = f"{job_type}_{int(time.time()*1000)}"
            
            monitor.start_job(job_id, job_type)
            try:
                result = func(*args, **kwargs)
                monitor.complete_job(job_id, success=True)
                return result
            except Exception as e:
                monitor.complete_job(job_id, success=False, error_message=str(e))
                raise
        
        return wrapper
    return decorator


# Context manager for job tracking
class TrackJob:
    """Context manager for tracking job performance
    
    Important: This context manager does NOT suppress exceptions.
    If an error occurs during processing, it will be recorded and re-raised.
    """
    
    def __init__(self, job_id: str, job_type: str = 'ocr'):
        self.job_id = job_id
        self.job_type = job_type
        self.monitor = PerformanceMonitor()
        self.metrics: Optional[JobMetrics] = None
        self._exception_occurred = False
    
    def __enter__(self) -> 'TrackJob':
        self.metrics = self.monitor.start_job(self.job_id, self.job_type)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Record success/failure accurately based on exception state
        success = exc_type is None and not self._exception_occurred
        error_msg = str(exc_val) if exc_val else None
        self.monitor.complete_job(self.job_id, success=success, error_message=error_msg)
        # Never suppress exceptions - they must propagate
        return False
    
    def update(self, pages: int = 0, bytes_processed: int = 0):
        """Update job progress with actual values"""
        self.monitor.update_job(self.job_id, pages, bytes_processed)
    
    def mark_failed(self, error_message: str = None):
        """Explicitly mark job as failed (useful when exception is caught internally)"""
        self._exception_occurred = True
        if self.metrics:
            self.metrics.error_message = error_message


def get_ocr_max_workers_recommendation() -> Dict[str, Any]:
    """Recommend optimal OCR_MAX_WORKERS based on system resources"""
    cpu_count = psutil.cpu_count() or 1
    memory_gb = psutil.virtual_memory().total / (1024**3)
    
    # OCR is CPU-bound, use cores - 1 to leave headroom
    recommended_by_cpu = max(2, cpu_count - 1)
    
    # Each OCR worker can use ~500MB RAM for PDF processing
    recommended_by_memory = int(memory_gb / 0.5)
    
    recommended = min(recommended_by_cpu, recommended_by_memory)
    
    return {
        'cpu_cores': cpu_count,
        'memory_gb': round(memory_gb, 2),
        'recommended_workers': recommended,
        'recommended_by_cpu': recommended_by_cpu,
        'recommended_by_memory': recommended_by_memory,
        'current_setting': os.environ.get('OCR_MAX_WORKERS', 'auto')
    }
