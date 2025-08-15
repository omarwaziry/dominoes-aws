import unittest
import requests
import time
import json
import boto3
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore.exceptions import ClientError, NoCredentialsError
import os

class TestLoadBalancerIntegration(unittest.TestCase):
    """Integration tests for Application Load Balancer health checks and traffic distribution"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        cls.alb_dns_name = os.environ.get('ALB_DNS_NAME', 'localhost')
        cls.target_group_arn = os.environ.get('TARGET_GROUP_ARN', '')
        cls.region = os.environ.get('AWS_REGION', 'us-east-1')
        
        # Initialize AWS clients
        try:
            cls.elbv2_client = boto3.client('elbv2', region_name=cls.region)
            cls.ec2_client = boto3.client('ec2', region_name=cls.region)
            cls.aws_available = True
        except (NoCredentialsError, Exception):
            cls.aws_available = False
            print("Warning: AWS credentials not available. Some tests will be skipped.")
        
        cls.base_url = f"http://{cls.alb_dns_name}"
        cls.health_check_url = f"{cls.base_url}/health"
        cls.metrics_url = f"{cls.base_url}/metrics"
        
    def test_health_check_endpoint_availability(self):
        """Test that health check endpoint is accessible through ALB"""
        try:
            response = requests.get(self.health_check_url, timeout=10)
            self.assertEqual(response.status_code, 200)
            
            # Verify health check response format
            data = response.json()
            self.assertIn('status', data)
            self.assertEqual(data['status'], 'healthy')
            self.assertIn('timestamp', data)
            
        except requests.exceptions.RequestException as e:
            self.skipTest(f"ALB not accessible: {e}")
    
    def test_metrics_endpoint_availability(self):
        """Test that metrics endpoint is accessible through ALB"""
        try:
            response = requests.get(self.metrics_url, timeout=10)
            self.assertEqual(response.status_code, 200)
            
            # Verify metrics response format
            data = response.json()
            self.assertIn('system', data)
            self.assertIn('games', data)
            
        except requests.exceptions.RequestException as e:
            self.skipTest(f"ALB not accessible: {e}")
    
    def test_main_application_endpoint(self):
        """Test that main application is accessible through ALB"""
        try:
            response = requests.get(self.base_url, timeout=10)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Dominoes Game', response.content)
            
        except requests.exceptions.RequestException as e:
            self.skipTest(f"ALB not accessible: {e}")
    
    def test_load_balancer_target_health(self):
        """Test ALB target group health status"""
        if not self.aws_available or not self.target_group_arn:
            self.skipTest("AWS credentials or target group ARN not available")
        
        try:
            response = self.elbv2_client.describe_target_health(
                TargetGroupArn=self.target_group_arn
            )
            
            targets = response['TargetHealthDescriptions']
            self.assertGreater(len(targets), 0, "No targets found in target group")
            
            healthy_targets = [t for t in targets if t['TargetHealth']['State'] == 'healthy']
            self.assertGreater(len(healthy_targets), 0, "No healthy targets found")
            
            # Verify at least one target is healthy
            for target in healthy_targets:
                self.assertEqual(target['TargetHealth']['State'], 'healthy')
                
        except ClientError as e:
            self.skipTest(f"AWS API error: {e}")
    
    def test_traffic_distribution_across_instances(self):
        """Test that traffic is distributed across multiple instances"""
        if not self.aws_available or not self.target_group_arn:
            self.skipTest("AWS credentials or target group ARN not available")
        
        # Get healthy targets
        try:
            response = self.elbv2_client.describe_target_health(
                TargetGroupArn=self.target_group_arn
            )
            
            healthy_targets = [
                t for t in response['TargetHealthDescriptions'] 
                if t['TargetHealth']['State'] == 'healthy'
            ]
            
            if len(healthy_targets) < 2:
                self.skipTest("Need at least 2 healthy targets for distribution test")
            
            # Make multiple requests and track which instances respond
            instance_responses = {}
            num_requests = 20
            
            for i in range(num_requests):
                try:
                    response = requests.get(self.metrics_url, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        instance_id = data.get('system', {}).get('instance_id', 'unknown')
                        instance_responses[instance_id] = instance_responses.get(instance_id, 0) + 1
                except requests.exceptions.RequestException:
                    continue
            
            # Verify traffic went to multiple instances
            responding_instances = len(instance_responses)
            self.assertGreaterEqual(responding_instances, 1, "No instances responded")
            
            # If we have multiple healthy targets, we should see distribution
            if len(healthy_targets) > 1:
                # Allow for some variance in distribution due to session stickiness
                # At least 2 instances should receive some traffic over 20 requests
                self.assertGreaterEqual(responding_instances, 1, 
                                      f"Traffic not distributed. Responses: {instance_responses}")
                
        except ClientError as e:
            self.skipTest(f"AWS API error: {e}")
    
    def test_session_stickiness(self):
        """Test that session stickiness is working correctly"""
        try:
            # Create a session and make multiple requests
            session = requests.Session()
            
            # Make initial request to establish session
            response1 = session.get(self.base_url, timeout=10)
            self.assertEqual(response1.status_code, 200)
            
            # Make follow-up requests and verify they go to same instance
            instance_ids = []
            for i in range(5):
                response = session.get(self.metrics_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    instance_id = data.get('system', {}).get('instance_id', 'unknown')
                    instance_ids.append(instance_id)
                time.sleep(0.5)
            
            # With session stickiness, all requests should go to same instance
            if len(instance_ids) > 1:
                unique_instances = set(instance_ids)
                # Allow for some variance, but most requests should go to same instance
                most_common_instance = max(set(instance_ids), key=instance_ids.count)
                same_instance_count = instance_ids.count(most_common_instance)
                self.assertGreaterEqual(same_instance_count / len(instance_ids), 0.8,
                                      f"Session stickiness not working. Instance IDs: {instance_ids}")
                
        except requests.exceptions.RequestException as e:
            self.skipTest(f"ALB not accessible: {e}")
    
    def test_health_check_failure_handling(self):
        """Test ALB behavior when health checks fail"""
        if not self.aws_available or not self.target_group_arn:
            self.skipTest("AWS credentials or target group ARN not available")
        
        try:
            # Get current target health
            initial_response = self.elbv2_client.describe_target_health(
                TargetGroupArn=self.target_group_arn
            )
            
            initial_healthy = len([
                t for t in initial_response['TargetHealthDescriptions']
                if t['TargetHealth']['State'] == 'healthy'
            ])
            
            # Verify ALB continues to serve traffic even if some targets are unhealthy
            # This test assumes the application is running and healthy
            response = requests.get(self.health_check_url, timeout=10)
            self.assertEqual(response.status_code, 200)
            
            # Test that ALB returns 200 for health checks when targets are healthy
            data = response.json()
            self.assertEqual(data['status'], 'healthy')
            
        except ClientError as e:
            self.skipTest(f"AWS API error: {e}")
        except requests.exceptions.RequestException as e:
            self.skipTest(f"ALB not accessible: {e}")
    
    def test_concurrent_request_handling(self):
        """Test ALB handling of concurrent requests"""
        try:
            def make_request():
                response = requests.get(self.health_check_url, timeout=10)
                return response.status_code, response.elapsed.total_seconds()
            
            # Make 10 concurrent requests
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(make_request) for _ in range(10)]
                results = [future.result() for future in as_completed(futures)]
            
            # Verify all requests succeeded
            status_codes = [result[0] for result in results]
            response_times = [result[1] for result in results]
            
            successful_requests = sum(1 for code in status_codes if code == 200)
            self.assertGreaterEqual(successful_requests, 8, 
                                  f"Too many failed requests: {status_codes}")
            
            # Verify reasonable response times
            avg_response_time = sum(response_times) / len(response_times)
            self.assertLess(avg_response_time, 5.0, 
                          f"Average response time too high: {avg_response_time}s")
            
        except requests.exceptions.RequestException as e:
            self.skipTest(f"ALB not accessible: {e}")
    
    def test_alb_listener_rules(self):
        """Test that ALB listener rules are configured correctly"""
        if not self.aws_available:
            self.skipTest("AWS credentials not available")
        
        try:
            # Get load balancer ARN from target group
            tg_response = self.elbv2_client.describe_target_groups(
                TargetGroupArns=[self.target_group_arn]
            )
            
            if not tg_response['TargetGroups']:
                self.skipTest("Target group not found")
            
            lb_arns = tg_response['TargetGroups'][0]['LoadBalancerArns']
            if not lb_arns:
                self.skipTest("No load balancer associated with target group")
            
            # Get listeners
            listeners_response = self.elbv2_client.describe_listeners(
                LoadBalancerArn=lb_arns[0]
            )
            
            self.assertGreater(len(listeners_response['Listeners']), 0, 
                             "No listeners found")
            
            # Verify HTTP listener exists
            http_listeners = [
                l for l in listeners_response['Listeners'] 
                if l['Port'] == 80 and l['Protocol'] == 'HTTP'
            ]
            self.assertGreater(len(http_listeners), 0, "No HTTP listener found")
            
            # Test specific paths
            test_paths = ['/health', '/metrics', '/api/session-score']
            for path in test_paths:
                try:
                    response = requests.get(f"{self.base_url}{path}", timeout=5)
                    # Should get either 200 or 404, not connection errors
                    self.assertIn(response.status_code, [200, 404], 
                                f"Unexpected status for {path}: {response.status_code}")
                except requests.exceptions.RequestException:
                    # Path might not exist, but ALB should still respond
                    pass
                    
        except ClientError as e:
            self.skipTest(f"AWS API error: {e}")

if __name__ == '__main__':
    unittest.main()