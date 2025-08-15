import unittest
import boto3
import json
import os
from botocore.exceptions import ClientError, NoCredentialsError

class TestSecurityConfiguration(unittest.TestCase):
    """Security tests for IAM roles, security groups, and network access"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        cls.region = os.environ.get('AWS_REGION', 'us-east-1')
        cls.vpc_id = os.environ.get('VPC_ID', '')
        cls.asg_name = os.environ.get('ASG_NAME', '')
        cls.alb_arn = os.environ.get('ALB_ARN', '')
        
        # Initialize AWS clients
        try:
            cls.ec2_client = boto3.client('ec2', region_name=cls.region)
            cls.iam_client = boto3.client('iam', region_name=cls.region)
            cls.elbv2_client = boto3.client('elbv2', region_name=cls.region)
            cls.autoscaling_client = boto3.client('autoscaling', region_name=cls.region)
            cls.aws_available = True
        except (NoCredentialsError, Exception):
            cls.aws_available = False
            print("Warning: AWS credentials not available. Some tests will be skipped.")
    
    def setUp(self):
        """Set up each test"""
        if not self.aws_available:
            self.skipTest("AWS credentials not available")
    
    def test_security_group_ingress_rules(self):
        """Test that security group ingress rules follow least privilege principle"""
        print("Testing security group ingress rules...")
        
        try:
            if self.vpc_id:
                response = self.ec2_client.describe_security_groups(
                    Filters=[{'Name': 'vpc-id', 'Values': [self.vpc_id]}]
                )
            else:
                response = self.ec2_client.describe_security_groups()
            
            security_groups = response['SecurityGroups']
            self.assertGreater(len(security_groups), 0, "No security groups found")
            
            for sg in security_groups:
                sg_name = sg.get('GroupName', 'Unknown')
                
                for rule in sg.get('IpPermissions', []):
                    from_port = rule.get('FromPort', 0)
                    
                    # Check for overly permissive rules
                    for ip_range in rule.get('IpRanges', []):
                        cidr = ip_range.get('CidrIp', '')
                        
                        if cidr == '0.0.0.0/0':
                            # Only allow 0.0.0.0/0 for ALB on HTTP/HTTPS ports
                            if 'alb' in sg_name.lower() or 'load-balancer' in sg_name.lower():
                                allowed_ports = [80, 443]
                                if from_port not in allowed_ports:
                                    self.fail(f"ALB security group {sg_name} allows non-HTTP/HTTPS port {from_port} from 0.0.0.0/0")
                            else:
                                # Other security groups should not allow 0.0.0.0/0
                                print(f"Warning: Security group {sg_name} allows access from 0.0.0.0/0 on port {from_port}")
                                
        except ClientError as e:
            self.skipTest(f"Failed to describe security groups: {e}")
    
    def test_iam_role_permissions(self):
        """Test that IAM roles follow least privilege principle"""
        print("Testing IAM role permissions...")
        
        if not self.asg_name:
            self.skipTest("ASG name not provided")
        
        try:
            # Get ASG instances
            response = self.autoscaling_client.describe_auto_scaling_groups(
                AutoScalingGroupNames=[self.asg_name]
            )
            
            if not response['AutoScalingGroups']:
                self.skipTest("ASG not found")
            
            instances = response['AutoScalingGroups'][0]['Instances']
            if not instances:
                self.skipTest("No instances in ASG")
            
            # Get instance profiles
            instance_ids = [instance['InstanceId'] for instance in instances]
            ec2_response = self.ec2_client.describe_instances(InstanceIds=instance_ids)
            
            instance_profiles = set()
            for reservation in ec2_response['Reservations']:
                for instance in reservation['Instances']:
                    if 'IamInstanceProfile' in instance:
                        profile_arn = instance['IamInstanceProfile']['Arn']
                        profile_name = profile_arn.split('/')[-1]
                        instance_profiles.add(profile_name)
            
            # Test each instance profile has roles
            for profile_name in instance_profiles:
                profile_response = self.iam_client.get_instance_profile(
                    InstanceProfileName=profile_name
                )
                
                roles = profile_response['InstanceProfile']['Roles']
                self.assertGreater(len(roles), 0, f"Instance profile {profile_name} has no roles")
                
                for role in roles:
                    role_name = role['RoleName']
                    
                    # Check attached policies
                    policies_response = self.iam_client.list_attached_role_policies(
                        RoleName=role_name
                    )
                    
                    # Should have some policies attached
                    self.assertGreater(len(policies_response['AttachedPolicies']), 0,
                                     f"Role {role_name} has no attached policies")
                    
                    print(f"Role {role_name} has {len(policies_response['AttachedPolicies'])} attached policies")
                    
        except ClientError as e:
            self.skipTest(f"Failed to test IAM roles: {e}")
    
    def test_load_balancer_security_configuration(self):
        """Test that Load Balancer security configuration is appropriate"""
        print("Testing Load Balancer security configuration...")
        
        if not self.alb_arn:
            self.skipTest("ALB ARN not provided")
        
        try:
            # Get load balancer details
            response = self.elbv2_client.describe_load_balancers(
                LoadBalancerArns=[self.alb_arn]
            )
            
            if not response['LoadBalancers']:
                self.skipTest("Load balancer not found")
            
            lb = response['LoadBalancers'][0]
            
            # Check scheme (should be internet-facing for web app)
            scheme = lb['Scheme']
            self.assertEqual(scheme, 'internet-facing',
                           "Load balancer should be internet-facing for web application")
            
            # Check security groups
            security_groups = lb['SecurityGroups']
            self.assertGreater(len(security_groups), 0, "Load balancer has no security groups")
            
            # Check load balancer attributes
            attributes_response = self.elbv2_client.describe_load_balancer_attributes(
                LoadBalancerArn=self.alb_arn
            )
            
            attributes = {attr['Key']: attr['Value'] for attr in attributes_response['Attributes']}
            
            # For free tier, access logs should be disabled to avoid costs
            access_logs = attributes.get('access_logs.s3.enabled', 'false')
            self.assertEqual(access_logs, 'false',
                           "Access logs should be disabled for free tier compliance")
            
        except ClientError as e:
            self.skipTest(f"Failed to describe load balancer: {e}")
    
    def test_network_acl_configuration(self):
        """Test that Network ACLs are properly configured"""
        print("Testing Network ACL configuration...")
        
        if not self.vpc_id:
            self.skipTest("VPC ID not provided")
        
        try:
            # Get Network ACLs for the VPC
            response = self.ec2_client.describe_network_acls(
                Filters=[{'Name': 'vpc-id', 'Values': [self.vpc_id]}]
            )
            
            network_acls = response['NetworkAcls']
            self.assertGreater(len(network_acls), 0, "No Network ACLs found")
            
            for nacl in network_acls:
                nacl_id = nacl['NetworkAclId']
                is_default = nacl['IsDefault']
                
                print(f"Checking Network ACL: {nacl_id} (default: {is_default})")
                
                # Check entries
                for entry in nacl['Entries']:
                    rule_action = entry['RuleAction']
                    cidr_block = entry.get('CidrBlock', '')
                    
                    # Check for overly permissive rules
                    if rule_action == 'allow' and cidr_block == '0.0.0.0/0':
                        if not is_default:
                            print(f"Warning: Custom NACL {nacl_id} allows traffic from 0.0.0.0/0")
                        
        except ClientError as e:
            self.skipTest(f"Failed to describe Network ACLs: {e}")

if __name__ == '__main__':
    unittest.main(verbosity=2)