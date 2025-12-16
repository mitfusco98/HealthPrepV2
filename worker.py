#!/usr/bin/env python3
"""
Standalone RQ Worker Entry Point for Containerized Deployment

This script runs RQ workers independently from the Flask web application.
In a containerized environment, this enables:
- Separate scaling of OCR workers from web servers
- Running OCR workers on cost-effective Spot instances
- Independent resource allocation and monitoring

Usage:
    python worker.py                    # Run single worker
    python worker.py --queues high,default  # Run with specific queues
    python worker.py --burst            # Process queue then exit (for batch jobs)

Environment Variables:
    REDIS_URL: Redis connection URL (default: redis://localhost:6379/0)
    OCR_MAX_WORKERS: Max parallel OCR threads per worker process
    RQ_WORKER_NAME: Custom worker name for monitoring
    RQ_QUEUES: Comma-separated queue names (default: fhir_processing,fhir_priority)
"""

import os
import sys
import logging
import argparse
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('rq_worker')


def get_redis_connection():
    """Get Redis connection from environment or default."""
    from redis import Redis
    
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    return Redis.from_url(redis_url)


def get_queues(queue_names=None):
    """Get RQ Queue objects for the specified queue names."""
    from rq import Queue
    
    conn = get_redis_connection()
    
    if queue_names is None:
        queue_names = os.environ.get('RQ_QUEUES', 'fhir_priority,fhir_processing')
    
    if isinstance(queue_names, str):
        queue_names = [q.strip() for q in queue_names.split(',')]
    
    queues = []
    for name in queue_names:
        queues.append(Queue(name, connection=conn))
        logger.info(f"Listening on queue: {name}")
    
    return queues


def run_worker(queues, burst=False, worker_name=None):
    """
    Run the RQ worker with Flask app context.
    
    Args:
        queues: List of Queue objects to listen on
        burst: If True, process queue and exit when empty
        worker_name: Custom name for this worker instance
    """
    from rq import Worker
    from app import app
    
    if worker_name is None:
        worker_name = os.environ.get('RQ_WORKER_NAME')
        if not worker_name:
            import socket
            worker_name = f"worker-{socket.gethostname()}-{os.getpid()}"
    
    logger.info(f"Starting RQ worker: {worker_name}")
    logger.info(f"Burst mode: {burst}")
    logger.info(f"OCR_MAX_WORKERS: {os.environ.get('OCR_MAX_WORKERS', 'auto-detect')}")
    
    with app.app_context():
        worker = Worker(
            queues,
            connection=get_redis_connection(),
            name=worker_name
        )
        
        logger.info(f"Worker {worker_name} started at {datetime.utcnow().isoformat()}")
        worker.work(burst=burst)


def get_queue_info():
    """Get current queue status for monitoring."""
    from rq import Queue
    from rq.job import Job
    
    conn = get_redis_connection()
    queue_names = os.environ.get('RQ_QUEUES', 'fhir_priority,fhir_processing').split(',')
    
    info = {
        'timestamp': datetime.utcnow().isoformat(),
        'queues': {}
    }
    
    for name in queue_names:
        name = name.strip()
        queue = Queue(name, connection=conn)
        
        info['queues'][name] = {
            'count': queue.count,
            'failed_count': queue.failed_job_registry.count,
            'scheduled_count': queue.scheduled_job_registry.count,
            'started_count': queue.started_job_registry.count,
        }
    
    return info


def main():
    parser = argparse.ArgumentParser(
        description='RQ Worker for HealthPrep OCR Processing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--queues', '-q',
        type=str,
        default=None,
        help='Comma-separated list of queue names to listen on'
    )
    
    parser.add_argument(
        '--burst', '-b',
        action='store_true',
        help='Run in burst mode: process queue and exit when empty'
    )
    
    parser.add_argument(
        '--name', '-n',
        type=str,
        default=None,
        help='Worker name for monitoring'
    )
    
    parser.add_argument(
        '--info', '-i',
        action='store_true',
        help='Show queue info and exit'
    )
    
    args = parser.parse_args()
    
    if args.info:
        info = get_queue_info()
        print(f"\nQueue Status ({info['timestamp']})")
        print("-" * 50)
        for queue_name, stats in info['queues'].items():
            print(f"\n{queue_name}:")
            print(f"  Pending: {stats['count']}")
            print(f"  Started: {stats['started_count']}")
            print(f"  Scheduled: {stats['scheduled_count']}")
            print(f"  Failed: {stats['failed_count']}")
        return
    
    queues = get_queues(args.queues)
    run_worker(queues, burst=args.burst, worker_name=args.name)


if __name__ == '__main__':
    main()
