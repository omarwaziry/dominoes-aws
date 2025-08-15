import time
import logging
from functools import wraps
from flask import request, g, jsonify
from datetime import datetime, timedelta
import threading

class ApplicationMonitor:
    """Application monitoring and metrics collection"""
    
    def __init__(self):
        self.request_count = 0
        self.error_count = 0
        self.response_times = []
        self.start_time = datetime.utcnow()
        self.lock = threading.Lock()
        
        # Request tracking by endpoint
        self.endpoint_stats = {}
        
        # Health check tracking
        self.last_health_check = None
        self.health_check_count = 0
        
    def record_request(self, endpoint, method, status_code, response_time):
        """Record request metrics"""
        with self.lock:
            self.request_count += 1
            
            if status_code >= 400:
                self.error_count += 1
            
            self.response_times.append(response_time)
            # Keep only last 1000 response times to prevent memory growth
            if len(self.response_times) > 1000:
                self.response_times = self.response_times[-1000:]
            
            # Track per-endpoint stats
            key = f"{method} {endpoint}"
            if key not in self.endpoint_stats:
                self.endpoint_stats[key] = {
                    'count': 0,
                    'errors': 0,
                    'total_time': 0,
                    'avg_time': 0
                }
            
            stats = self.endpoint_stats[key]
            stats['count'] += 1
            stats['total_time'] += response_time
            stats['avg_time'] = stats['total_time'] / stats['count']
            
            if status_code >= 400:
                stats['errors'] += 1
    
    def record_health_check(self):
        """Record health check"""
        with self.lock:
            self.last_health_check = datetime.utcnow()
            self.health_check_count += 1
    
    def get_metrics(self):
        """Get current application metrics"""
        with self.lock:
            uptime = datetime.utcnow() - self.start_time
            
            # Calculate response time statistics
            avg_response_time = 0
            p95_response_time = 0
            if self.response_times:
                avg_response_time = sum(self.response_times) / len(self.response_times)
                sorted_times = sorted(self.response_times)
                p95_index = int(len(sorted_times) * 0.95)
                p95_response_time = sorted_times[p95_index] if p95_index < len(sorted_times) else 0
            
            # Calculate error rate
            error_rate = (self.error_count / self.request_count * 100) if self.request_count > 0 else 0
            
            return {
                'uptime_seconds': uptime.total_seconds(),
                'uptime_formatted': str(uptime),
                'total_requests': self.request_count,
                'total_errors': self.error_count,
                'error_rate_percent': round(error_rate, 2),
                'avg_response_time_ms': round(avg_response_time * 1000, 2),
                'p95_response_time_ms': round(p95_response_time * 1000, 2),
                'health_check_count': self.health_check_count,
                'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None,
                'endpoint_stats': dict(self.endpoint_stats),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def is_healthy(self):
        """Determine if application is healthy based on metrics"""
        with self.lock:
            # Check error rate
            if self.request_count > 10:  # Only check after some requests
                error_rate = (self.error_count / self.request_count * 100)
                if error_rate > 50:  # More than 50% error rate
                    return False, f"High error rate: {error_rate:.1f}%"
            
            # Check if health checks are recent (within last 5 minutes)
            if self.last_health_check:
                time_since_check = datetime.utcnow() - self.last_health_check
                if time_since_check > timedelta(minutes=5):
                    return False, "No recent health checks"
            
            return True, "All systems operational"

# Global monitor instance
monitor = ApplicationMonitor()

def setup_monitoring(app):
    """Set up monitoring middleware for Flask app"""
    
    @app.before_request
    def before_request():
        g.start_time = time.time()
    
    @app.after_request
    def after_request(response):
        if hasattr(g, 'start_time'):
            response_time = time.time() - g.start_time
            monitor.record_request(
                endpoint=request.endpoint or 'unknown',
                method=request.method,
                status_code=response.status_code,
                response_time=response_time
            )
        return response
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f'Server Error: {error}')
        return jsonify({
            'error': 'Internal server error',
            'timestamp': datetime.utcnow().isoformat()
        }), 500
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': 'Not found',
            'timestamp': datetime.utcnow().isoformat()
        }), 404

def monitor_endpoint(f):
    """Decorator to monitor specific endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        try:
            result = f(*args, **kwargs)
            return result
        except Exception as e:
            # Log the error
            logging.error(f"Error in {f.__name__}: {str(e)}")
            raise
        finally:
            response_time = time.time() - start_time
            # Additional monitoring can be added here
    return decorated_function