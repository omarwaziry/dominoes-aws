import time
import logging
from flask import request, g
from datetime import datetime

class RequestLoggingMiddleware:
    """Middleware for logging HTTP requests and responses"""
    
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize the middleware with Flask app"""
        app.before_request(self.before_request)
        app.after_request(self.after_request)
        
        # Set up request logger
        self.logger = logging.getLogger('dominoes.requests')
        if not app.debug:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def before_request(self):
        """Called before each request"""
        g.start_time = time.time()
        g.request_id = f"{int(time.time())}-{id(request)}"
        
        # Log incoming request
        self.logger.info(
            f"REQUEST {g.request_id} - {request.method} {request.path} "
            f"from {request.remote_addr} - User-Agent: {request.headers.get('User-Agent', 'Unknown')}"
        )
    
    def after_request(self, response):
        """Called after each request"""
        if hasattr(g, 'start_time') and hasattr(g, 'request_id'):
            duration = time.time() - g.start_time
            
            # Log response
            self.logger.info(
                f"RESPONSE {g.request_id} - {response.status_code} "
                f"in {duration*1000:.2f}ms - Size: {response.content_length or 0} bytes"
            )
            
            # Log slow requests (>1 second)
            if duration > 1.0:
                self.logger.warning(
                    f"SLOW REQUEST {g.request_id} - {request.method} {request.path} "
                    f"took {duration:.2f}s"
                )
        
        return response

class ErrorHandlingMiddleware:
    """Middleware for handling application errors"""
    
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize error handling with Flask app"""
        self.logger = logging.getLogger('dominoes.errors')
        
        if not app.debug:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.ERROR)
        
        # Register error handlers
        app.register_error_handler(404, self.handle_404)
        app.register_error_handler(500, self.handle_500)
        app.register_error_handler(Exception, self.handle_exception)
    
    def handle_404(self, error):
        """Handle 404 Not Found errors"""
        self.logger.warning(f"404 Not Found: {request.method} {request.path}")
        return {
            'error': 'Not Found',
            'message': 'The requested resource was not found',
            'timestamp': datetime.utcnow().isoformat(),
            'path': request.path
        }, 404
    
    def handle_500(self, error):
        """Handle 500 Internal Server Error"""
        self.logger.error(f"500 Internal Server Error: {str(error)}")
        return {
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred',
            'timestamp': datetime.utcnow().isoformat()
        }, 500
    
    def handle_exception(self, error):
        """Handle all other exceptions"""
        self.logger.error(f"Unhandled exception: {str(error)}", exc_info=True)
        
        # Don't handle HTTP exceptions (they have their own handlers)
        if hasattr(error, 'code'):
            return error
        
        return {
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred',
            'timestamp': datetime.utcnow().isoformat()
        }, 500