"""
Test configuration and utilities for comprehensive testing suite
"""

import os
import boto3
from botocore.exceptions import NoCredentialsError, ClientError

class TestConfig:
    """Configuration class for test environment"""
    
    def __init__(self):
        # AWS Configuration
        self.region = os.environ.get('AWS_REGION', 'us-east-1')
        self.vpc_id = os.environ.get('VPC_ID', '')
        self.asg_name = os.environ.get('ASG_NAME', '')
        self.alb_arn = os.environ.get('ALB_ARN', '')
        self.alb_dns_name = os.environ.get('ALB_DNS_NAME', 'localhost')
        self.target_group_arn = os.environ.get('TARGET_GROUP_ARN', '')
        
        # Test Configuration
        self.skip_aws_tests = os.environ.get('SKIP_AWS_TESTS', 'false').lower() == 'true'
        self.test_timeout = int(os.environ.get('TEST_TIMEOUT', '300'))  # 5 minutes default
        self.load_test_duration = int(os.environ.get('LOAD_TEST_DURATION', '300'))  # 5 minutes
        self.requests_per_second = int(os.environ.get('REQUESTS_PER_SECOND', '10'))
        
        # Application Configuration
        self.app_port = int(os.environ.get('APP_PORT', '80'))
        self.health_check_path = os.environ.get('HEALTH_CHECK_PATH', '/health')
        self.metrics_path = os.environ.get('METRICS_PATH', '/metrics')
        
        # Initialize AWS clients
        self.aws_available = False
        self.clients = {}
        
        if not self.skip_aws_tests:
            self._initialize_aws_clients()
    
    def _initialize_aws_clients(self):
        """Initialize AWS service clients"""
        try:
            self.clients = {
                'ec2': boto3.client('ec2', region_name=self.region),
                'elbv2': boto3.client('elbv2', region_name=self.region),
                'autoscaling': boto3.client('autoscaling', region_name=self.region),
                'cloudwatch': boto3.client('cloudwatch', region_name=self.region),
                'iam': boto3.client('iam', region_name=self.region),
                'cloudformation': boto3.client('cloudformation', region_name=self.region),
                'rds': boto3.client('rds', region_name=self.region),
                'sns': boto3.client('sns', region_name=self.region)
            }
            self.aws_available = True
            print("AWS clients initialized successfully")
        except (NoCredentialsError, Exception) as e:
            print(f"Warning: AWS credentials not available: {e}")
            self.aws_available = False
    
    def get_client(self, service_name):
        """Get AWS service client"""
        if not self.aws_available:
            raise Exception("AWS clients not available")
        
        if service_name not in self.clients:
            raise ValueError(f"Unknown service: {service_name}")
        
        return self.clients[service_name]
    
    def get_base_url(self):
        """Get base URL for application testing"""
        protocol = 'https' if self.app_port == 443 else 'http'
        port_suffix = '' if self.app_port in [80, 443] else f':{self.app_port}'
        return f"{protocol}://{self.alb_dns_name}{port_suffix}"
    
    def get_health_check_url(self):
        """Get health check URL"""
        return f"{self.get_base_url()}{self.health_check_path}"
    
    def get_metrics_url(self):
        """Get metrics URL"""
        return f"{self.get_base_url()}{self.metrics_path}"
    
    def validate_configuration(self):
        """Validate test configuration"""
        issues = []
        
        if not self.skip_aws_tests:
            if not self.aws_available:
                issues.append("AWS credentials not available but AWS tests not skipped")
            
            if not self.vpc_id:
                issues.append("VPC_ID not set")
            
            if not self.asg_name:
                issues.append("ASG_NAME not set")
            
            if not self.alb_arn:
                issues.append("ALB_ARN not set")
        
        if not self.alb_dns_name or self.alb_dns_name == 'localhost':
            issues.append("ALB_DNS_NAME not properly configured")
        
        return issues
    
    def print_configuration(self):
        """Print current test configuration"""
        print("Test Configuration:")
        print(f"  AWS Region: {self.region}")
        print(f"  AWS Available: {self.aws_available}")
        print(f"  Skip AWS Tests: {self.skip_aws_tests}")
        print(f"  VPC ID: {self.vpc_id or 'Not set'}")
        print(f"  ASG Name: {self.asg_name or 'Not set'}")
        print(f"  ALB ARN: {self.alb_arn or 'Not set'}")
        print(f"  ALB DNS Name: {self.alb_dns_name}")
        print(f"  Target Group ARN: {self.target_group_arn or 'Not set'}")
        print(f"  Base URL: {self.get_base_url()}")
        print(f"  Test Timeout: {self.test_timeout}s")
        print(f"  Load Test Duration: {self.load_test_duration}s")
        print(f"  Requests Per Second: {self.requests_per_second}")

# Global test configuration instance
test_config = TestConfig()

def get_test_config():
    """Get the global test configuration instance"""
    return test_config

def setup_test_environment():
    """Set up test environment and validate configuration"""
    config = get_test_config()
    
    print("Setting up test environment...")
    config.print_configuration()
    
    # Validate configuration
    issues = config.validate_configuration()
    if issues:
        print("\nConfiguration Issues:")
        for issue in issues:
            print(f"  - {issue}")
        
        if not config.skip_aws_tests:
            print("\nTo skip AWS tests, set SKIP_AWS_TESTS=true")
    
    return config

def teardown_test_environment():
    """Clean up test environment"""
    print("Cleaning up test environment...")
    # Add any cleanup logic here if needed
    pass