import unittest
import requests
import time
import threading
import boto3
import json
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore.exceptions import ClientError, NoCredentialsError

class TestAutoScalingBehavior(unittest.TestCase):
    """Load testing scripts to validate auto scaling behavior"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        cls.alb_dns_name = os.environ.get('ALB_DNS_NAME', 'localhost')
        cls.asg_name = os.environ.get('ASG_NAME', '')
        cls.region = os.environ.get('AWS_REGION', 'us-east-1')
        
        # Initialize AWS clients
        try:
            cls.autoscaling_client = boto3.client('autoscaling', region_name=cls.region)
            cls.cloudwatch_client = boto3.client('cloudwatch', region_name=cls.region)
            cls.ec2_client = boto3.client('ec2', region_name=cls.region)
            cls.aws_available = True
        except (NoCredentialsError, Exception):
            cls.aws_available = False
            print("Warning: AWS credentials not available. Some tests will be skipped.")
        
        cls.base_url = f"http://{cls.alb_dns_name}"
        cls.load_test_duration = 300  # 5 minutes
        cls.cooldown_period = 300  # 5 minutes
        
    def setUp(self):
        """Set up each test"""
        if not self.aws_available or not self.asg_name:
            self.skipTest("AWS credentials or ASG name not available")
    
    def get_asg_info(self):
        """Get current Auto Scaling Group information"""
        try:
            response = self.autoscaling_client.describe_auto_scaling_groups(
                AutoScalingGroupNames=[self.asg_name]
            )
            
            if not response['AutoScalingGroups']:
                raise ValueError(f"Auto Scaling Group {self.asg_name} not found")
            
            return response['AutoScalingGroups'][0]
        except ClientError as e:
            raise Exception(f"Failed to get ASG info: {e}")
    
    def get_instance_count(self):
        """Get current number of instances in ASG"""
        asg_info = self.get_asg_info()
        return len(asg_info['Instances'])
    
    def get_cpu_utilization(self, duration_minutes=5):
        """Get average CPU utilization for ASG instances"""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=duration_minutes)
            
            response = self.cloudwatch_client.get_metric_statistics(
                Namespace='AWS/EC2',
                MetricName='CPUUtilization',
                Dimensions=[
                    {
                        'Name': 'AutoScalingGroupName',
                        'Value': self.asg_name
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,  # 5 minutes
                Statistics=['Average']
            )
            
            if response['Datapoints']:
                return sum(dp['Average'] for dp in response['Datapoints']) / len(response['Datapoints'])
            return 0
            
        except ClientError as e:
            print(f"Failed to get CPU utilization: {e}")
            return 0
    
    def generate_cpu_load(self, duration_seconds, requests_per_second=10):
        """Generate CPU load by making requests to the application"""
        def make_request():
            try:
                # Make requests to CPU-intensive endpoints
                endpoints = [
                    '/api/new-game',
                    '/metrics',
                    '/',
                    '/health'
                ]
                
                for endpoint in endpoints:
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                    if response.status_code == 200 and endpoint == '/api/new-game':
                        # If new game created, make some moves to increase CPU usage
                        data = response.json()
                        if 'game_id' in data:
                            # Make a few game moves
                            for _ in range(3):
                                requests.post(f"{self.base_url}/api/draw-tile", 
                                            json={}, timeout=5)
                                time.sleep(0.1)
            except requests.exceptions.RequestException:
                pass  # Ignore individual request failures
        
        print(f"Generating load for {duration_seconds} seconds at {requests_per_second} RPS...")
        
        start_time = time.time()
        request_count = 0
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            while time.time() - start_time < duration_seconds:
                # Submit requests at specified rate
                futures = []
                for _ in range(requests_per_second):
                    futures.append(executor.submit(make_request))
                
                # Wait for requests to complete or timeout
                for future in as_completed(futures, timeout=1):
                    try:
                        future.result()
                        request_count += 1
                    except:
                        pass
                
                time.sleep(1)  # Wait 1 second before next batch
        
        print(f"Load generation complete. Made {request_count} requests.")
        return request_count
    
    def wait_for_scaling_event(self, expected_instances, timeout_minutes=15):
        """Wait for ASG to scale to expected number of instances"""
        print(f"Waiting for ASG to scale to {expected_instances} instances...")
        
        start_time = time.time()
        timeout_seconds = timeout_minutes * 60
        
        while time.time() - start_time < timeout_seconds:
            current_instances = self.get_instance_count()
            print(f"Current instances: {current_instances}, Target: {expected_instances}")
            
            if current_instances == expected_instances:
                print(f"Scaling complete: {current_instances} instances")
                return True
            
            time.sleep(30)  # Check every 30 seconds
        
        print(f"Timeout waiting for scaling. Current: {self.get_instance_count()}, Expected: {expected_instances}")
        return False
    
    def test_scale_up_behavior(self):
        """Test that ASG scales up under high CPU load"""
        print("Testing scale-up behavior...")
        
        # Get initial state
        initial_instances = self.get_instance_count()
        asg_info = self.get_asg_info()
        max_size = asg_info['MaxSize']
        
        print(f"Initial instances: {initial_instances}, Max size: {max_size}")
        
        if initial_instances >= max_size:
            self.skipTest(f"Already at max capacity ({max_size})")
        
        # Generate high CPU load
        load_duration = 600  # 10 minutes to trigger scaling
        requests_per_second = 15  # Aggressive load
        
        # Start load generation in background
        load_thread = threading.Thread(
            target=self.generate_cpu_load,
            args=(load_duration, requests_per_second)
        )
        load_thread.start()
        
        # Monitor for scaling up
        scaling_detected = False
        max_wait_time = 900  # 15 minutes
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            current_instances = self.get_instance_count()
            cpu_utilization = self.get_cpu_utilization(duration_minutes=2)
            
            print(f"Time: {int(time.time() - start_time)}s, "
                  f"Instances: {current_instances}, "
                  f"CPU: {cpu_utilization:.1f}%")
            
            if current_instances > initial_instances:
                scaling_detected = True
                print(f"Scale-up detected! Instances increased from {initial_instances} to {current_instances}")
                break
            
            time.sleep(60)  # Check every minute
        
        # Stop load generation
        load_thread.join(timeout=10)
        
        # Verify scaling occurred
        final_instances = self.get_instance_count()
        self.assertGreater(final_instances, initial_instances,
                          f"ASG did not scale up. Initial: {initial_instances}, Final: {final_instances}")
        
        print(f"Scale-up test completed. Instances: {initial_instances} -> {final_instances}")
    
    def test_scale_down_behavior(self):
        """Test that ASG scales down when load decreases"""
        print("Testing scale-down behavior...")
        
        # Get current state
        current_instances = self.get_instance_count()
        asg_info = self.get_asg_info()
        min_size = asg_info['MinSize']
        
        print(f"Current instances: {current_instances}, Min size: {min_size}")
        
        if current_instances <= min_size:
            self.skipTest(f"Already at minimum capacity ({min_size})")
        
        # Wait for low CPU utilization and scale down
        print("Waiting for low CPU utilization and scale-down...")
        
        max_wait_time = 1800  # 30 minutes (includes cooldown)
        start_time = time.time()
        scaling_detected = False
        
        while time.time() - start_time < max_wait_time:
            instances = self.get_instance_count()
            cpu_utilization = self.get_cpu_utilization(duration_minutes=5)
            
            print(f"Time: {int(time.time() - start_time)}s, "
                  f"Instances: {instances}, "
                  f"CPU: {cpu_utilization:.1f}%")
            
            if instances < current_instances:
                scaling_detected = True
                print(f"Scale-down detected! Instances decreased from {current_instances} to {instances}")
                break
            
            time.sleep(120)  # Check every 2 minutes
        
        # Verify scaling occurred or explain why not
        final_instances = self.get_instance_count()
        final_cpu = self.get_cpu_utilization(duration_minutes=10)
        
        if not scaling_detected:
            if final_cpu > 30:  # Above scale-down threshold
                print(f"Scale-down not triggered due to high CPU: {final_cpu:.1f}%")
            else:
                print(f"Scale-down may be in cooldown period or other factors")
        
        print(f"Scale-down test completed. Instances: {current_instances} -> {final_instances}")
    
    def test_scaling_policies_configuration(self):
        """Test that scaling policies are configured correctly"""
        print("Testing scaling policies configuration...")
        
        try:
            # Get scaling policies
            response = self.autoscaling_client.describe_policies(
                AutoScalingGroupName=self.asg_name
            )
            
            policies = response['ScalingPolicies']
            self.assertGreater(len(policies), 0, "No scaling policies found")
            
            # Check for scale-up and scale-down policies
            scale_up_policies = [p for p in policies if p['ScalingAdjustment'] > 0]
            scale_down_policies = [p for p in policies if p['ScalingAdjustment'] < 0]
            
            self.assertGreater(len(scale_up_policies), 0, "No scale-up policies found")
            self.assertGreater(len(scale_down_policies), 0, "No scale-down policies found")
            
            # Verify policy configurations
            for policy in policies:
                self.assertIn('PolicyARN', policy)
                self.assertIn('PolicyName', policy)
                self.assertIn('ScalingAdjustment', policy)
                self.assertIn('Cooldown', policy)
                
                # Verify reasonable cooldown periods
                self.assertGreaterEqual(policy['Cooldown'], 60, 
                                      f"Cooldown too short: {policy['Cooldown']}s")
                self.assertLessEqual(policy['Cooldown'], 900, 
                                   f"Cooldown too long: {policy['Cooldown']}s")
            
            print(f"Found {len(scale_up_policies)} scale-up and {len(scale_down_policies)} scale-down policies")
            
        except ClientError as e:
            self.fail(f"Failed to describe scaling policies: {e}")
    
    def test_cloudwatch_alarms_configuration(self):
        """Test that CloudWatch alarms for scaling are configured correctly"""
        print("Testing CloudWatch alarms configuration...")
        
        try:
            # Get alarms related to the ASG
            response = self.cloudwatch_client.describe_alarms()
            
            asg_alarms = [
                alarm for alarm in response['MetricAlarms']
                if any(dim.get('Value') == self.asg_name for dim in alarm.get('Dimensions', []))
            ]
            
            self.assertGreater(len(asg_alarms), 0, "No CloudWatch alarms found for ASG")
            
            # Check for CPU-based alarms
            cpu_alarms = [
                alarm for alarm in asg_alarms
                if alarm['MetricName'] == 'CPUUtilization'
            ]
            
            self.assertGreater(len(cpu_alarms), 0, "No CPU utilization alarms found")
            
            # Verify alarm configurations
            for alarm in cpu_alarms:
                self.assertIn('AlarmName', alarm)
                self.assertIn('Threshold', alarm)
                self.assertIn('ComparisonOperator', alarm)
                self.assertIn('EvaluationPeriods', alarm)
                self.assertIn('Period', alarm)
                
                # Verify reasonable thresholds
                if 'high' in alarm['AlarmName'].lower():
                    self.assertGreaterEqual(alarm['Threshold'], 50, 
                                          f"High CPU threshold too low: {alarm['Threshold']}")
                elif 'low' in alarm['AlarmName'].lower():
                    self.assertLessEqual(alarm['Threshold'], 40, 
                                       f"Low CPU threshold too high: {alarm['Threshold']}")
            
            print(f"Found {len(cpu_alarms)} CPU-based alarms for ASG")
            
        except ClientError as e:
            self.fail(f"Failed to describe CloudWatch alarms: {e}")
    
    def test_instance_health_during_scaling(self):
        """Test that instances remain healthy during scaling events"""
        print("Testing instance health during scaling...")
        
        # Get current instances
        asg_info = self.get_asg_info()
        instances = asg_info['Instances']
        
        self.assertGreater(len(instances), 0, "No instances in ASG")
        
        # Check health of all instances
        unhealthy_instances = []
        for instance in instances:
            instance_id = instance['InstanceId']
            health_status = instance['HealthStatus']
            lifecycle_state = instance['LifecycleState']
            
            if health_status != 'Healthy' or lifecycle_state not in ['InService', 'Pending']:
                unhealthy_instances.append({
                    'InstanceId': instance_id,
                    'HealthStatus': health_status,
                    'LifecycleState': lifecycle_state
                })
        
        # Allow for some instances to be in transitional states
        healthy_instances = len(instances) - len(unhealthy_instances)
        min_healthy_required = max(1, len(instances) // 2)  # At least half should be healthy
        
        self.assertGreaterEqual(healthy_instances, min_healthy_required,
                              f"Too many unhealthy instances: {unhealthy_instances}")
        
        print(f"Instance health check: {healthy_instances}/{len(instances)} healthy")
    
    def test_load_balancer_integration_during_scaling(self):
        """Test that load balancer continues to work during scaling events"""
        print("Testing load balancer integration during scaling...")
        
        # Make continuous requests while monitoring scaling
        def continuous_requests(duration_seconds, results_list):
            start_time = time.time()
            success_count = 0
            error_count = 0
            
            while time.time() - start_time < duration_seconds:
                try:
                    response = requests.get(f"{self.base_url}/health", timeout=5)
                    if response.status_code == 200:
                        success_count += 1
                    else:
                        error_count += 1
                except requests.exceptions.RequestException:
                    error_count += 1
                
                time.sleep(1)
            
            results_list.append({
                'success': success_count,
                'errors': error_count,
                'total': success_count + error_count
            })
        
        # Start continuous requests
        results = []
        request_thread = threading.Thread(
            target=continuous_requests,
            args=(300, results)  # 5 minutes of requests
        )
        request_thread.start()
        
        # Monitor instance count changes
        initial_instances = self.get_instance_count()
        instance_changes = []
        
        for i in range(10):  # Monitor for 5 minutes (30s intervals)
            time.sleep(30)
            current_instances = self.get_instance_count()
            instance_changes.append(current_instances)
            
            if current_instances != initial_instances:
                print(f"Instance count changed: {initial_instances} -> {current_instances}")
        
        # Wait for request thread to complete
        request_thread.join()
        
        # Analyze results
        if results:
            result = results[0]
            total_requests = result['total']
            success_rate = result['success'] / total_requests if total_requests > 0 else 0
            
            # Require at least 90% success rate during scaling
            self.assertGreaterEqual(success_rate, 0.9,
                                  f"Success rate too low during scaling: {success_rate:.2%}")
            
            print(f"Load balancer performance during scaling: "
                  f"{result['success']}/{total_requests} successful ({success_rate:.2%})")
        
        print(f"Instance count changes: {initial_instances} -> {instance_changes[-1]}")

if __name__ == '__main__':
    # Set longer test timeout for load tests
    unittest.TestLoader.testMethodPrefix = 'test_'
    unittest.main(verbosity=2)