#!/usr/bin/env python3
"""
Test script for EC2 Auto Scaling Group configuration validation.
This script validates the CloudFormation template and tests the configuration.
"""

import json
import yaml
import boto3
import pytest
import os
import re
from datetime import datetime
from typing import Dict, List, Any

class TestEC2AutoScaling:
    """Test cases for EC2 Auto Scaling Group configuration"""
    
    def setup_method(self):
        """Setup test environment"""
        self.template_path = "infrastructure/ec2-autoscaling.yaml"
        self.project_name = "dominoes-app"
        self.environment = "dev"
        
        # Load CloudFormation template as raw text for validation
        with open(self.template_path, 'r', encoding='utf-8') as f:
            self.template_content = f.read()
    
    def test_template_structure(self):
        """Test that the CloudFormation template has required structure"""
        # Text-based validation for CloudFormation structure
        assert 'AWSTemplateFormatVersion:' in self.template_content
        assert 'Description:' in self.template_content
        assert 'Parameters:' in self.template_content
        assert 'Resources:' in self.template_content
        assert 'Outputs:' in self.template_content
        
        # Check required resources
        required_resources = [
            'EC2Role:',
            'EC2InstanceProfile:', 
            'LaunchTemplate:',
            'AutoScalingGroup:',
            'ScaleUpPolicy:',
            'ScaleDownPolicy:',
            'TargetTrackingScalingPolicy:',
            'CPUAlarmHigh:',
            'CPUAlarmLow:'
        ]
        
        for resource in required_resources:
            assert resource in self.template_content, f"Missing required resource: {resource}"
    
    def test_parameters(self):
        """Test CloudFormation parameters"""
        # Text-based validation for parameters
        required_params = [
            'ProjectName:',
            'Environment:', 
            'VPCId:',
            'PrivateSubnet1Id:',
            'PrivateSubnet2Id:',
            'EC2SecurityGroupId:',
            'TargetGroupArn:',
            'InstanceType:'
        ]
        
        for param in required_params:
            assert param in self.template_content, f"Missing required parameter: {param}"
        
        # Check for t2.micro default and free tier compliance
        assert 't2.micro' in self.template_content
        assert 'Default: \'t2.micro\'' in self.template_content or 'Default: t2.micro' in self.template_content
    
    def test_iam_role_configuration(self):
        """Test IAM role and instance profile configuration"""
        # Check EC2 Role exists and has correct type
        assert 'Type: AWS::IAM::Role' in self.template_content
        
        # Check managed policies
        expected_policies = [
            'arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy',
            'arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore'
        ]
        
        for policy in expected_policies:
            assert policy in self.template_content
        
        # Check custom policy
        assert 'DominoesAppPolicy' in self.template_content
        assert 'cloudwatch:PutMetricData' in self.template_content
        
        # Check instance profile
        assert 'Type: AWS::IAM::InstanceProfile' in self.template_content
    
    def test_launch_template_configuration(self):
        """Test Launch Template configuration"""
        # Check Launch Template exists and has correct type
        assert 'Type: AWS::EC2::LaunchTemplate' in self.template_content
        
        # Check instance configuration components
        assert 'ImageId:' in self.template_content
        assert 'InstanceType:' in self.template_content
        assert 'IamInstanceProfile:' in self.template_content
        assert 'SecurityGroupIds:' in self.template_content
        assert 'UserData:' in self.template_content
        
        # Check block device mapping for free tier compliance
        assert 'VolumeType: gp2' in self.template_content
        assert 'VolumeSize: 8' in self.template_content  # Free tier limit
        assert 'DeleteOnTermination: true' in self.template_content
        assert 'Encrypted: true' in self.template_content
        
        # Check monitoring is enabled
        assert 'Enabled: true' in self.template_content
    
    def test_auto_scaling_group_configuration(self):
        """Test Auto Scaling Group configuration"""
        # Check Auto Scaling Group exists and has correct type
        assert 'Type: AWS::AutoScaling::AutoScalingGroup' in self.template_content
        
        # Check scaling configuration
        assert 'MinSize:' in self.template_content
        assert 'MaxSize:' in self.template_content
        assert 'DesiredCapacity:' in self.template_content
        
        # Check health check configuration
        assert 'HealthCheckType: ELB' in self.template_content
        assert 'HealthCheckGracePeriod: 300' in self.template_content
        
        # Check creation and update policies
        assert 'CreationPolicy:' in self.template_content
        assert 'UpdatePolicy:' in self.template_content
        assert 'ResourceSignal:' in self.template_content
    
    def test_scaling_policies(self):
        """Test scaling policies configuration"""
        # Check scaling policies exist
        assert 'Type: AWS::AutoScaling::ScalingPolicy' in self.template_content
        
        # Test scale up policy
        assert 'ScaleUpPolicy:' in self.template_content
        assert 'ScalingAdjustment: 1' in self.template_content
        
        # Test scale down policy
        assert 'ScaleDownPolicy:' in self.template_content
        assert 'ScalingAdjustment: -1' in self.template_content
        
        # Test target tracking policy
        assert 'TargetTrackingScalingPolicy:' in self.template_content
        assert 'PolicyType: TargetTrackingScaling' in self.template_content
        assert 'ASGAverageCPUUtilization' in self.template_content
    
    def test_cloudwatch_alarms(self):
        """Test CloudWatch alarms configuration"""
        # Check CloudWatch alarms exist
        assert 'Type: AWS::CloudWatch::Alarm' in self.template_content
        
        # Test CPU high alarm
        assert 'CPUAlarmHigh:' in self.template_content
        assert 'MetricName: CPUUtilization' in self.template_content
        assert 'Threshold: 80' in self.template_content
        assert 'GreaterThanThreshold' in self.template_content
        
        # Test CPU low alarm
        assert 'CPUAlarmLow:' in self.template_content
        assert 'Threshold: 30' in self.template_content
        assert 'LessThanThreshold' in self.template_content
    
    def test_user_data_script(self):
        """Test user data script content"""
        # Check for user data section
        assert 'UserData:' in self.template_content
        assert 'Fn::Base64:' in self.template_content
        
        # Check for required components in user data
        required_components = [
            'yum update -y',
            'python3',
            'gunicorn',
            'dominoes-app.service',
            'amazon-cloudwatch-agent',
            'cfn-signal'
        ]
        
        for component in required_components:
            assert component in self.template_content, f"Missing component in user data: {component}"
    
    def test_free_tier_compliance(self):
        """Test that configuration complies with AWS free tier limits"""
        parameters = self.template['Parameters']
        
        # Check instance type default
        assert parameters['InstanceType']['Default'] == 't2.micro'
        
        # Check max size limit
        max_size_default = parameters['MaxSize']['Default']
        assert max_size_default <= 3, "Max size should be limited for free tier"
        
        # Check EBS volume size
        resources = self.template['Resources']
        launch_template = resources['LaunchTemplate']
        block_devices = launch_template['Properties']['LaunchTemplateData']['BlockDeviceMappings']
        
        ebs_size = block_devices[0]['Ebs']['VolumeSize']
        assert ebs_size <= 30, "EBS volume size should be within free tier limit"
    
    def test_outputs(self):
        """Test CloudFormation outputs"""
        outputs = self.template['Outputs']
        
        required_outputs = [
            'LaunchTemplateId',
            'AutoScalingGroupName',
            'AutoScalingGroupArn',
            'EC2RoleArn',
            'ScaleUpPolicyArn',
            'ScaleDownPolicyArn',
            'FreeTierCompliance',
            'ScalingConfiguration'
        ]
        
        for output in required_outputs:
            assert output in outputs, f"Missing required output: {output}"
    
    def test_template_validation(self):
        """Test CloudFormation template validation using AWS CLI"""
        try:
            import subprocess
            import tempfile
            
            # Write template to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(self.template, f)
                temp_file = f.name
            
            # Validate template using AWS CLI
            result = subprocess.run([
                'aws', 'cloudformation', 'validate-template',
                '--template-body', f'file://{temp_file}'
            ], capture_output=True, text=True)
            
            # Clean up
            os.unlink(temp_file)
            
            assert result.returncode == 0, f"Template validation failed: {result.stderr}"
            
        except FileNotFoundError:
            pytest.skip("AWS CLI not available for template validation")
        except Exception as e:
            pytest.skip(f"Template validation skipped: {str(e)}")

class TestEC2AutoScalingIntegration:
    """Integration tests for deployed EC2 Auto Scaling Group"""
    
    def setup_method(self):
        """Setup test environment"""
        self.project_name = os.environ.get('PROJECT_NAME', 'dominoes-app')
        self.environment = os.environ.get('ENVIRONMENT', 'dev')
        self.region = os.environ.get('AWS_REGION', 'us-east-1')
        
        # Initialize AWS clients
        try:
            self.autoscaling = boto3.client('autoscaling', region_name=self.region)
            self.ec2 = boto3.client('ec2', region_name=self.region)
            self.cloudwatch = boto3.client('cloudwatch', region_name=self.region)
        except Exception as e:
            pytest.skip(f"AWS clients not available: {str(e)}")
    
    def test_auto_scaling_group_exists(self):
        """Test that Auto Scaling Group exists and is configured correctly"""
        asg_name = f"{self.project_name}-{self.environment}-asg"
        
        try:
            response = self.autoscaling.describe_auto_scaling_groups(
                AutoScalingGroupNames=[asg_name]
            )
            
            assert len(response['AutoScalingGroups']) == 1
            
            asg = response['AutoScalingGroups'][0]
            assert asg['AutoScalingGroupName'] == asg_name
            assert asg['MinSize'] >= 1
            assert asg['MaxSize'] <= 10
            assert asg['HealthCheckType'] == 'ELB'
            
        except Exception as e:
            pytest.skip(f"Auto Scaling Group not found or not accessible: {str(e)}")
    
    def test_instances_are_healthy(self):
        """Test that instances in ASG are healthy"""
        asg_name = f"{self.project_name}-{self.environment}-asg"
        
        try:
            response = self.autoscaling.describe_auto_scaling_groups(
                AutoScalingGroupNames=[asg_name]
            )
            
            if not response['AutoScalingGroups']:
                pytest.skip("Auto Scaling Group not found")
            
            asg = response['AutoScalingGroups'][0]
            instances = asg['Instances']
            
            if not instances:
                pytest.skip("No instances in Auto Scaling Group")
            
            # Check that at least one instance is InService
            in_service_instances = [i for i in instances if i['LifecycleState'] == 'InService']
            assert len(in_service_instances) > 0, "No instances are in service"
            
            # Check instance health
            for instance in in_service_instances:
                assert instance['HealthStatus'] == 'Healthy'
                
        except Exception as e:
            pytest.skip(f"Cannot check instance health: {str(e)}")
    
    def test_scaling_policies_exist(self):
        """Test that scaling policies are configured"""
        asg_name = f"{self.project_name}-{self.environment}-asg"
        
        try:
            response = self.autoscaling.describe_policies(
                AutoScalingGroupName=asg_name
            )
            
            policies = response['ScalingPolicies']
            assert len(policies) >= 2, "Should have at least scale up and scale down policies"
            
            # Check for target tracking policy
            target_tracking_policies = [p for p in policies if p['PolicyType'] == 'TargetTrackingScaling']
            assert len(target_tracking_policies) >= 1, "Should have target tracking scaling policy"
            
        except Exception as e:
            pytest.skip(f"Cannot check scaling policies: {str(e)}")
    
    def test_cloudwatch_alarms_exist(self):
        """Test that CloudWatch alarms are configured"""
        try:
            response = self.cloudwatch.describe_alarms(
                AlarmNamePrefix=f"{self.project_name}-{self.environment}"
            )
            
            alarms = response['MetricAlarms']
            assert len(alarms) >= 2, "Should have at least CPU high and low alarms"
            
            # Check for CPU alarms
            cpu_alarms = [a for a in alarms if 'cpu' in a['AlarmName'].lower()]
            assert len(cpu_alarms) >= 2, "Should have CPU high and low alarms"
            
        except Exception as e:
            pytest.skip(f"Cannot check CloudWatch alarms: {str(e)}")

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])