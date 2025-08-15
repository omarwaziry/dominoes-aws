#!/usr/bin/env python3
"""
Setup script for test environment
Discovers AWS resources and sets environment variables for testing
"""

import boto3
import os
import sys
import json
from botocore.exceptions import ClientError, NoCredentialsError

def discover_aws_resources(region='us-east-1', project_name='dominoes-app'):
    """Discover AWS resources for testing"""
    print(f"Discovering AWS resources in region {region}...")
    
    try:
        # Initialize clients
        ec2_client = boto3.client('ec2', region_name=region)
        elbv2_client = boto3.client('elbv2', region_name=region)
        autoscaling_client = boto3.client('autoscaling', region_name=region)
        cloudformation_client = boto3.client('cloudformation', region_name=region)
        
        resources = {}
        
        # Discover VPC
        print("  Discovering VPC...")
        vpcs = ec2_client.describe_vpcs(
            Filters=[
                {'Name': 'tag:Name', 'Values': [f'{project_name}-*']},
                {'Name': 'state', 'Values': ['available']}
            ]
        )
        
        if vpcs['Vpcs']:
            vpc = vpcs['Vpcs'][0]
            resources['VPC_ID'] = vpc['VpcId']
            print(f"    Found VPC: {vpc['VpcId']}")
        else:
            print("    No VPC found with project name tag")
        
        # Discover Auto Scaling Group
        print("  Discovering Auto Scaling Group...")
        asgs = autoscaling_client.describe_auto_scaling_groups()
        
        for asg in asgs['AutoScalingGroups']:
            asg_name = asg['AutoScalingGroupName']
            if project_name in asg_name.lower():
                resources['ASG_NAME'] = asg_name
                print(f"    Found ASG: {asg_name}")
                break
        else:
            print("    No Auto Scaling Group found")
        
        # Discover Load Balancer
        print("  Discovering Application Load Balancer...")
        albs = elbv2_client.describe_load_balancers()
        
        for alb in albs['LoadBalancers']:
            alb_name = alb['LoadBalancerName']
            if project_name in alb_name.lower():
                resources['ALB_ARN'] = alb['LoadBalancerArn']
                resources['ALB_DNS_NAME'] = alb['DNSName']
                print(f"    Found ALB: {alb_name}")
                print(f"    DNS Name: {alb['DNSName']}")
                
                # Get target groups
                target_groups = elbv2_client.describe_target_groups(
                    LoadBalancerArn=alb['LoadBalancerArn']
                )
                
                if target_groups['TargetGroups']:
                    tg = target_groups['TargetGroups'][0]
                    resources['TARGET_GROUP_ARN'] = tg['TargetGroupArn']
                    print(f"    Found Target Group: {tg['TargetGroupName']}")
                
                break
        else:
            print("    No Application Load Balancer found")
        
        # Try to discover resources via CloudFormation stacks
        print("  Discovering CloudFormation stacks...")
        try:
            stacks = cloudformation_client.describe_stacks()
            
            for stack in stacks['Stacks']:
                stack_name = stack['StackName']
                if project_name in stack_name.lower() and stack['StackStatus'] in ['CREATE_COMPLETE', 'UPDATE_COMPLETE']:
                    print(f"    Found stack: {stack_name}")
                    
                    # Get stack outputs
                    outputs = stack.get('Outputs', [])
                    for output in outputs:
                        output_key = output['OutputKey']
                        output_value = output['OutputValue']
                        
                        # Map common output keys to environment variables
                        key_mapping = {
                            'VPCId': 'VPC_ID',
                            'VPC': 'VPC_ID',
                            'AutoScalingGroupName': 'ASG_NAME',
                            'ASGName': 'ASG_NAME',
                            'LoadBalancerArn': 'ALB_ARN',
                            'ALBArn': 'ALB_ARN',
                            'LoadBalancerDNSName': 'ALB_DNS_NAME',
                            'ALBDNSName': 'ALB_DNS_NAME',
                            'TargetGroupArn': 'TARGET_GROUP_ARN'
                        }
                        
                        if output_key in key_mapping:
                            env_key = key_mapping[output_key]
                            resources[env_key] = output_value
                            print(f"      {output_key}: {output_value}")
        
        except ClientError as e:
            print(f"    CloudFormation discovery failed: {e}")
        
        return resources
        
    except (ClientError, NoCredentialsError) as e:
        print(f"Error discovering AWS resources: {e}")
        return {}

def create_test_env_file(resources, filename='.env.test'):
    """Create environment file for testing"""
    print(f"\nCreating test environment file: {filename}")
    
    # Default values
    env_vars = {
        'AWS_REGION': 'us-east-1',
        'TEST_TIMEOUT': '300',
        'LOAD_TEST_DURATION': '300',
        'REQUESTS_PER_SECOND': '10',
        'APP_PORT': '80',
        'HEALTH_CHECK_PATH': '/health',
        'METRICS_PATH': '/metrics'
    }
    
    # Add discovered resources
    env_vars.update(resources)
    
    # Write environment file
    with open(filename, 'w') as f:
        f.write("# Test environment configuration\n")
        f.write("# Generated by setup_test_environment.py\n\n")
        
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    
    print(f"Environment file created with {len(env_vars)} variables")
    return filename

def load_env_file(filename='.env.test'):
    """Load environment variables from file"""
    if not os.path.exists(filename):
        print(f"Environment file {filename} not found")
        return
    
    print(f"Loading environment variables from {filename}")
    
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
                    print(f"  {key}={value}")

def validate_test_environment():
    """Validate that test environment is properly configured"""
    print("\nValidating test environment...")
    
    required_vars = ['AWS_REGION']
    optional_vars = ['VPC_ID', 'ASG_NAME', 'ALB_ARN', 'ALB_DNS_NAME', 'TARGET_GROUP_ARN']
    
    issues = []
    
    # Check required variables
    for var in required_vars:
        if not os.environ.get(var):
            issues.append(f"Required environment variable {var} not set")
    
    # Check optional variables (warn if missing)
    missing_optional = []
    for var in optional_vars:
        if not os.environ.get(var):
            missing_optional.append(var)
    
    if missing_optional:
        print(f"  Warning: Optional variables not set: {', '.join(missing_optional)}")
        print("  Some AWS tests may be skipped")
    
    # Check AWS credentials
    try:
        boto3.client('sts').get_caller_identity()
        print("  AWS credentials: OK")
    except Exception as e:
        issues.append(f"AWS credentials not available: {e}")
    
    if issues:
        print("  Issues found:")
        for issue in issues:
            print(f"    - {issue}")
        return False
    else:
        print("  Test environment validation: PASSED")
        return True

def main():
    """Main setup function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Setup test environment')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--project-name', default='dominoes-app', help='Project name for resource discovery')
    parser.add_argument('--env-file', default='.env.test', help='Environment file name')
    parser.add_argument('--load-only', action='store_true', help='Only load existing environment file')
    parser.add_argument('--validate-only', action='store_true', help='Only validate current environment')
    
    args = parser.parse_args()
    
    if args.validate_only:
        # Just validate current environment
        if validate_test_environment():
            sys.exit(0)
        else:
            sys.exit(1)
    
    if args.load_only:
        # Just load existing environment file
        load_env_file(args.env_file)
        validate_test_environment()
        return
    
    # Discover AWS resources
    resources = discover_aws_resources(args.region, args.project_name)
    
    if resources:
        # Create environment file
        env_file = create_test_env_file(resources, args.env_file)
        
        # Load the environment file
        load_env_file(env_file)
        
        # Validate environment
        if validate_test_environment():
            print(f"\nTest environment setup complete!")
            print(f"Environment file: {env_file}")
            print("You can now run the comprehensive tests:")
            print("  python tests/run_comprehensive_tests.py")
        else:
            print("\nTest environment setup completed with issues")
            sys.exit(1)
    else:
        print("\nNo AWS resources discovered. Creating minimal environment file...")
        env_file = create_test_env_file({}, args.env_file)
        print(f"Environment file created: {env_file}")
        print("You may need to manually set AWS resource identifiers")
        print("Or run tests with --skip-aws flag")

if __name__ == '__main__':
    main()