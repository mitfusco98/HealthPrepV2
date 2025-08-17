"""
Epic Token Background Scheduler
Implements blueprint suggestion for background token checking and notifications
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

from services.epic_connection_monitor import get_connection_monitor

logger = logging.getLogger(__name__)

class EpicTokenScheduler:
    """
    Background scheduler for Epic token expiry checking
    Implements blueprint suggestion for proactive token management
    """
    
    def __init__(self, check_interval_minutes: int = 30):
        self.check_interval_minutes = check_interval_minutes
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.monitor = get_connection_monitor()
        
        logger.info(f"Epic Token Scheduler initialized with {check_interval_minutes} minute intervals")
    
    def start(self):
        """Start the background scheduler"""
        if self.running:
            logger.warning("Epic Token Scheduler already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()
        
        logger.info("Epic Token Scheduler started")
    
    def stop(self):
        """Stop the background scheduler"""
        if not self.running:
            return
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        
        logger.info("Epic Token Scheduler stopped")
    
    def _run_scheduler(self):
        """Main scheduler loop"""
        logger.info(f"Epic Token Scheduler loop started - checking every {self.check_interval_minutes} minutes")
        
        while self.running:
            try:
                self._check_tokens()
                
                # Sleep for the specified interval (in seconds)
                for _ in range(self.check_interval_minutes * 60):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in Epic Token Scheduler loop: {str(e)}")
                # Continue running but wait before retrying
                time.sleep(60)
    
    def _check_tokens(self):
        """Check all organization tokens and perform necessary actions"""
        try:
            logger.debug("Starting Epic token check cycle")
            
            # Get summary of connection status
            stats = self.monitor.check_all_organizations()
            
            if 'error' in stats:
                logger.error(f"Error during token check cycle: {stats['error']}")
                return
            
            # Log summary
            logger.info(f"Token check completed: {stats['connected']} connected, "
                       f"{stats['expiring_soon']} expiring soon, "
                       f"{stats['expired']} expired, "
                       f"{stats['disconnected']} disconnected")
            
            # Get organizations needing attention for potential notifications
            attention_needed = self.monitor.get_organizations_needing_attention()
            
            if attention_needed:
                logger.warning(f"{len(attention_needed)} organizations need admin attention:")
                for org_info in attention_needed:
                    logger.warning(f"  - {org_info['org_name']}: {org_info['status_message']}")
            
            # Here you could implement notification logic (email, Slack, etc.)
            # For now, we just log the issues
            
        except Exception as e:
            logger.error(f"Error during Epic token check: {str(e)}")
    
    def force_check(self):
        """Manually trigger a token check (for testing/admin use)"""
        logger.info("Manual Epic token check triggered")
        self._check_tokens()


# Global scheduler instance
_scheduler_instance: Optional[EpicTokenScheduler] = None

def get_scheduler() -> EpicTokenScheduler:
    """Get or create the global scheduler instance"""
    global _scheduler_instance
    
    if _scheduler_instance is None:
        # Default to 30-minute intervals
        _scheduler_instance = EpicTokenScheduler(check_interval_minutes=30)
    
    return _scheduler_instance

def start_epic_scheduler(check_interval_minutes: int = 30):
    """Start the Epic token scheduler with specified interval"""
    scheduler = get_scheduler()
    scheduler.check_interval_minutes = check_interval_minutes
    scheduler.start()
    
    logger.info(f"Epic Token Scheduler started with {check_interval_minutes} minute intervals")

def stop_epic_scheduler():
    """Stop the Epic token scheduler"""
    global _scheduler_instance
    
    if _scheduler_instance:
        _scheduler_instance.stop()
        _scheduler_instance = None
        
    logger.info("Epic Token Scheduler stopped")

def is_scheduler_running() -> bool:
    """Check if the scheduler is currently running"""
    global _scheduler_instance
    return _scheduler_instance is not None and _scheduler_instance.running