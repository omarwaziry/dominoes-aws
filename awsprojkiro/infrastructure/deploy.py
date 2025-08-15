#!/usr/bin/env python3
"""
Deployment script for the scalable dominoes web application with cost monitoring.
Supports parameter validation, stack updates, and rollback procedures.
"""

import argparse
import boto3
import json
import time
import sys
import os
from typing import Dict, List, Optional, Tuple
import yaml
from datetime import datetime, timedelta

class DominoesAppDeployer:
    """Deploy the dominoes application with cost monitoring, parameter validation, and rollback support"""
    
    def __init__(self, region: str = 'us-east-1', profile: Optional[str] = None):
        self.region = region
        self.session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        self.cloudformation = self.session.client('cloudformation', region_name=region)
        self.s3 = self.session.client('s3', region_name=region)
        self.deployment_history = []
    
    def load_parameters_from_file(self, parameter_file: str) -> Dict:
        """Load parameters from JSON file"""
        try:
            with open(parameter_file, 'r') as f:
                params = json.load(f)
            print(f"Loaded parameters from {parameter_file}")
            return params
        except FileNotFoundError:
            print(f"Parameter file {parameter_file} not found")
            return {}
        except json.JSONDecodeError as e:
            print(f"Error parsing parameter file {parameter_file}: {e}")
            return {}
    
    def validate_parameters(self, parameters: Dict, environment: str) -> Tuple[bool, List[str]]:
        """Validate deployment parameters for free tier compliance and best practices"""
        errors = []
        warnings = []
        
        # Required parameters
        required_params = ['ProjectName', 'Environment', 'InstanceType', 'AlertEmail']
        for param in required_params:
            if not parameters.get(param):
                errors.append(f"Required parameter '{param}' is missing or empty")
        
        # Free tier compliance checks
        instance_type = parameters.get('InstanceType', '')
        if instance_type not in ['t2.micro', 't3.micro']:
            errors.append(f"Instance type '{instance_type}' is not free tier eligible. Use t2.micro or t3.micro")
        
        max_instances = parameters.get('MaxInstances', 0)
        if max_instances > 3:
            warnings.append(f"MaxInstances ({max_instances}) may exceed free tier limits")
        
        db_instance_class = parameters.get('DBInstanceClass', '')
        if parameters.get('EnableRDS') and db_instance_class not in ['db.t2.micro', 'db.t3.micro']:
            errors.append(f"RDS instance class '{db_instance_class}' is not free tier eligible")
        
        db_storage = parameters.get('DBAllocatedStorage', 0)
        if parameters.get('EnableRDS') and db_storage > 20:
            warnings.append(f"RDS storage ({db_storage}GB) exceeds free tier limit of 20GB")
        
        # Environment-specific validations
        if environment == 'prod':
            if not parameters.get('MultiAZ', False):
                warnings.append("Production environment should use Multi-AZ for high availability")
            if parameters.get('BackupRetentionPeriod', 0) < 7:
                warnings.append("Production environment should have backup retention >= 7 days")
            if not parameters.get('DeletionProtection', False):
                warnings.append("Production environment should enable deletion protection")
        
        # Email validation
        alert_email = parameters.get('AlertEmail', '')
        if alert_email and '@' not in alert_email:
            errors.append("AlertEmail must be a valid email address")
        
        # Print warnings
        for warning in warnings:
            print(f"WARNING: {warning}")
        
        return len(errors) == 0, errors
    
    def create_deployment_backup(self, stack_name: str) -> Optional[Dict]:
        """Create a backup of current stack state before deployment"""
        try:
            response = self.cloudformation.describe_stacks(StackName=stack_name)
            stack = response['Stacks'][0]
            
            backup = {
                'timestamp': datetime.utcnow().isoformat(),
                'stack_name': stack_name,
                'stack_status': stack['StackStatus'],
                'parameters': {p['ParameterKey']: p['ParameterValue'] for p in stack.get('Parameters', [])},
                'tags': {t['Key']: t['Value'] for t in stack.get('Tags', [])},
                'outputs': {o['OutputKey']: o['OutputValue'] for o in stack.get('Outputs', [])}
            }
            
            self.deployment_history.append(backup)
            print(f"Created deployment backup for {stack_name}")
            return backup
            
        except self.cloudformation.exceptions.ClientError:
            print(f"Stack {stack_name} does not exist, no backup needed")
            return None
        except Exception as e:
            print(f"Error creating backup for {stack_name}: {e}")
            return None
    
    def rollback_stack(self, stack_name: str) -> bool:
        """Rollback stack to previous version"""
        try:
            print(f"Initiating rollback for stack: {stack_name}")
            
            # Check if stack is in a rollback-able state
            response = self.cloudformation.describe_stacks(StackName=stack_name)
            stack = response['Stacks'][0]
            stack_status = stack['StackStatus']
            
            rollback_states = [
                'UPDATE_FAILED', 'UPDATE_ROLLBACK_FAILED', 'CREATE_FAILED',
                'UPDATE_COMPLETE', 'CREATE_COMPLETE'
            ]
            
            if stack_status not in rollback_states:
                print(f"Stack {stack_name} is in state {stack_status}, cannot rollback")
                return False
            
            # Cancel update if in progress
            if 'IN_PROGRESS' in stack_status:
                print("Canceling in-progress update...")
                self.cloudformation.cancel_update_stack(StackName=stack_name)
                
                # Wait for cancellation
                waiter = self.cloudformation.get_waiter('stack_update_rollback_complete')
                waiter.wait(StackName=stack_name, WaiterConfig={'Delay': 30, 'MaxAttempts': 60})
            
            # Perform rollback
            if stack_status in ['UPDATE_FAILED', 'UPDATE_ROLLBACK_FAILED']:
                self.cloudformation.continue_update_rollback(StackName=stack_name)
                waiter = self.cloudformation.get_waiter('stack_update_rollback_complete')
            else:
                # For successful stacks, we need to update with previous parameters
                backup = self.get_latest_backup(stack_name)
                if not backup:
                    print(f"No backup found for {stack_name}, cannot rollback")
                    return False
                
                print("Rolling back to previous configuration...")
                # This would require storing the previous template as well
                print("Manual rollback required - redeploy with previous parameters")
                return False
            
            waiter.wait(StackName=stack_name, WaiterConfig={'Delay': 30, 'MaxAttempts': 60})
            print(f"Stack {stack_name} rolled back successfully")
            return True
            
        except Exception as e:
            print(f"Error rolling back stack {stack_name}: {e}")
            return False
    
    def get_latest_backup(self, stack_name: str) -> Optional[Dict]:
        """Get the latest backup for a stack"""
        stack_backups = [b for b in self.deployment_history if b['stack_name'] == stack_name]
        return stack_backups[-1] if stack_backups else None
    
    def monitor_stack_events(self, stack_name: str, start_time: datetime) -> None:
        """Monitor and display stack events during deployment"""
        try:
            paginator = self.cloudformation.get_paginator('describe_stack_events')
            
            for page in paginator.paginate(StackName=stack_name):
                events = page['StackEvents']
                
                # Filter events after start time
                recent_events = [
                    event for event in events 
                    if event['Timestamp'].replace(tzinfo=None) > start_time
                ]
                
                for event in reversed(recent_events):  # Show oldest first
                    timestamp = event['Timestamp'].strftime('%H:%M:%S')
                    resource_type = event.get('ResourceType', 'Unknown')
                    logical_id = event.get('LogicalResourceId', 'Unknown')
                    status = event.get('ResourceStatus', 'Unknown')
                    reason = event.get('ResourceStatusReason', '')
                    
                    print(f"[{timestamp}] {resource_type} {logical_id}: {status}")
                    if reason and 'FAILED' in status:
                        print(f"  Reason: {reason}")
                        
        except Exception as e:
            print(f"Error monitoring stack events: {e}")
        
    def deploy_stack(self, stack_name: str, template_path: str, parameters: Dict, 
                    capabilities: List[str] = None, tags: Dict = None, 
                    enable_rollback: bool = True) -> bool:
        """Deploy a CloudFormation stack with validation and rollback support"""
        start_time = datetime.utcnow()
        
        try:
            # Validate template exists
            if not os.path.exists(template_path):
                print(f"Template file {template_path} not found")
                return False
            
            with open(template_path, 'r') as f:
                template_body = f.read()
            
            # Validate template
            try:
                self.cloudformation.validate_template(TemplateBody=template_body)
                print(f"Template {template_path} validated successfully")
            except Exception as e:
                print(f"Template validation failed: {e}")
                return False
            
            # Convert parameters to CloudFormation format
            cf_parameters = [
                {'ParameterKey': k, 'ParameterValue': str(v)} 
                for k, v in parameters.items() if v is not None and v != ""
            ]
            
            # Convert tags to CloudFormation format
            cf_tags = [
                {'Key': k, 'Value': v} 
                for k, v in (tags or {}).items()
            ]
            
            # Check if stack exists
            try:
                self.cloudformation.describe_stacks(StackName=stack_name)
                stack_exists = True
                
                # Create backup before update
                if enable_rollback:
                    self.create_deployment_backup(stack_name)
                    
            except self.cloudformation.exceptions.ClientError:
                stack_exists = False
            
            try:
                if stack_exists:
                    print(f"Updating stack: {stack_name}")
                    
                    # Check for changes
                    try:
                        change_set_name = f"{stack_name}-changeset-{int(time.time())}"
                        self.cloudformation.create_change_set(
                            StackName=stack_name,
                            TemplateBody=template_body,
                            Parameters=cf_parameters,
                            Capabilities=capabilities or [],
                            Tags=cf_tags,
                            ChangeSetName=change_set_name
                        )
                        
                        # Wait for change set creation
                        time.sleep(10)
                        
                        # Describe changes
                        changes = self.cloudformation.describe_change_set(
                            StackName=stack_name,
                            ChangeSetName=change_set_name
                        )
                        
                        if changes['Status'] == 'FAILED':
                            if 'No updates are to be performed' in changes.get('StatusReason', ''):
                                print("No changes detected, skipping update")
                                self.cloudformation.delete_change_set(
                                    StackName=stack_name,
                                    ChangeSetName=change_set_name
                                )
                                return True
                            else:
                                print(f"Change set creation failed: {changes.get('StatusReason')}")
                                return False
                        
                        # Show changes
                        print("Planned changes:")
                        for change in changes.get('Changes', []):
                            resource_change = change['ResourceChange']
                            print(f"  {resource_change['Action']} {resource_change['ResourceType']} {resource_change['LogicalResourceId']}")
                        
                        # Execute change set
                        self.cloudformation.execute_change_set(
                            StackName=stack_name,
                            ChangeSetName=change_set_name
                        )
                        
                        operation = 'UPDATE'
                        waiter_name = 'stack_update_complete'
                        
                    except self.cloudformation.exceptions.ClientError as e:
                        if 'No updates are to be performed' in str(e):
                            print("No changes detected, skipping update")
                            return True
                        else:
                            raise e
                else:
                    print(f"Creating stack: {stack_name}")
                    self.cloudformation.create_stack(
                        StackName=stack_name,
                        TemplateBody=template_body,
                        Parameters=cf_parameters,
                        Capabilities=capabilities or [],
                        Tags=cf_tags,
                        EnableTerminationProtection=parameters.get('DeletionProtection', False)
                    )
                    operation = 'CREATE'
                    waiter_name = 'stack_create_complete'
                
                # Monitor stack events in background
                print(f"Waiting for stack {operation.lower()} to complete...")
                print("Stack events:")
                
                waiter = self.cloudformation.get_waiter(waiter_name)
                waiter.wait(
                    StackName=stack_name,
                    WaiterConfig={'Delay': 30, 'MaxAttempts': 120}
                )
                
                print(f"Stack {stack_name} {operation.lower()}d successfully")
                return True
                
            except Exception as e:
                print(f"Stack deployment failed: {e}")
                
                # Attempt rollback if enabled and this was an update
                if enable_rollback and stack_exists:
                    print("Attempting automatic rollback...")
                    if self.rollback_stack(stack_name):
                        print("Rollback completed successfully")
                    else:
                        print("Rollback failed - manual intervention required")
                
                return False
            
        except Exception as e:
            print(f"Error deploying stack {stack_name}: {e}")
            return False
    
    def get_stack_outputs(self, stack_name: str) -> Dict:
        """Get stack outputs"""
        try:
            response = self.cloudformation.describe_stacks(StackName=stack_name)
            stack = response['Stacks'][0]
            
            outputs = {}
            for output in stack.get('Outputs', []):
                outputs[output['OutputKey']] = output['OutputValue']
            
            return outputs
            
        except Exception as e:
            print(f"Error getting stack outputs for {stack_name}: {e}")
            return {}
    
    def deploy_full_application(self, project_name: str, environment: str, 
                               alert_email: str, parameter_file: Optional[str] = None,
                               enable_rollback: bool = True) -> bool:
        """Deploy the complete application stack using parameter files"""
        
        # Load parameters from file if provided
        if parameter_file:
            params = self.load_parameters_from_file(parameter_file)
            if not params:
                return False
        else:
            # Try to load default parameter file for environment
            default_param_file = f"infrastructure/parameters/{environment}.json"
            params = self.load_parameters_from_file(default_param_file)
            if not params:
                print(f"No parameter file found, using defaults")
                params = {}
        
        # Override with command line parameters
        if alert_email:
            params['AlertEmail'] = alert_email
        
        # Set defaults
        params.setdefault('ProjectName', project_name)
        params.setdefault('Environment', environment)
        
        # Validate parameters
        is_valid, errors = self.validate_parameters(params, environment)
        if not is_valid:
            print("Parameter validation failed:")
            for error in errors:
                print(f"  ERROR: {error}")
            return False
        
        # Extract configuration
        enable_rds = params.get('EnableRDS', False)
        
        common_tags = params.get('Tags', {})
        common_tags.update({
            'Project': project_name,
            'Environment': environment,
            'ManagedBy': 'CloudFormation',
            'Application': 'DominoesGame',
            'DeployedAt': datetime.utcnow().isoformat()
        })
        
        # 1. Deploy VPC and networking
        print("=== Deploying VPC and Networking ===")
        vpc_params = {
            'ProjectName': params['ProjectName'],
            'Environment': params['Environment']
        }
        
        if not self.deploy_stack(
            f"{project_name}-{environment}-vpc",
            "infrastructure/vpc-network.yaml",
            vpc_params,
            tags=common_tags,
            enable_rollback=enable_rollback
        ):
            return False
        
        vpc_outputs = self.get_stack_outputs(f"{project_name}-{environment}-vpc")
        
        # 2. Deploy Application Load Balancer
        print("=== Deploying Application Load Balancer ===")
        alb_params = {
            'ProjectName': params['ProjectName'],
            'Environment': params['Environment'],
            'VPCId': vpc_outputs.get('VPCId'),
            'PublicSubnet1Id': vpc_outputs.get('PublicSubnet1Id'),
            'PublicSubnet2Id': vpc_outputs.get('PublicSubnet2Id'),
            'ALBSecurityGroupId': vpc_outputs.get('ALBSecurityGroupId'),
            'HealthCheckPath': params.get('HealthCheckPath', '/health'),
            'HealthCheckIntervalSeconds': params.get('HealthCheckIntervalSeconds', 30),
            'HealthyThresholdCount': params.get('HealthyThresholdCount', 2),
            'UnhealthyThresholdCount': params.get('UnhealthyThresholdCount', 3)
        }
        
        if not self.deploy_stack(
            f"{project_name}-{environment}-alb",
            "infrastructure/alb.yaml",
            alb_params,
            tags=common_tags,
            enable_rollback=enable_rollback
        ):
            return False
        
        alb_outputs = self.get_stack_outputs(f"{project_name}-{environment}-alb")
        
        # 3. Deploy RDS (if enabled)
        if enable_rds:
            print("=== Deploying RDS Database ===")
            rds_params = {
                'ProjectName': params['ProjectName'],
                'Environment': params['Environment'],
                'VPCId': vpc_outputs.get('VPCId'),
                'DatabaseSubnetGroupName': vpc_outputs.get('DatabaseSubnetGroupName'),
                'RDSSecurityGroupId': vpc_outputs.get('RDSSecurityGroupId'),
                'DBInstanceClass': params.get('DBInstanceClass', 'db.t3.micro'),
                'DBAllocatedStorage': params.get('DBAllocatedStorage', 20),
                'MultiAZ': params.get('MultiAZ', False),
                'BackupRetentionPeriod': params.get('BackupRetentionPeriod', 7),
                'DeletionProtection': params.get('DeletionProtection', False),
                'DBPassword': 'ChangeMe123!'  # Should be passed securely or use Secrets Manager
            }
            
            if not self.deploy_stack(
                f"{project_name}-{environment}-rds",
                "infrastructure/rds.yaml",
                rds_params,
                tags=common_tags,
                enable_rollback=enable_rollback
            ):
                return False
        
        # 4. Deploy EC2 and Auto Scaling
        print("=== Deploying EC2 and Auto Scaling ===")
        ec2_params = {
            'ProjectName': params['ProjectName'],
            'Environment': params['Environment'],
            'VPCId': vpc_outputs.get('VPCId'),
            'PrivateSubnet1Id': vpc_outputs.get('PrivateSubnet1Id'),
            'PrivateSubnet2Id': vpc_outputs.get('PrivateSubnet2Id'),
            'EC2SecurityGroupId': vpc_outputs.get('EC2SecurityGroupId'),
            'TargetGroupArn': alb_outputs.get('TargetGroupArn'),
            'InstanceType': params.get('InstanceType', 't2.micro'),
            'MinInstances': params.get('MinInstances', 2),
            'MaxInstances': params.get('MaxInstances', 3),
            'DesiredInstances': params.get('DesiredInstances', 2),
            'ScaleUpCooldown': params.get('ScaleUpCooldown', 300),
            'ScaleDownCooldown': params.get('ScaleDownCooldown', 300),
            'CPUTargetValue': params.get('CPUTargetValue', 70.0),
            'EnableDetailedMonitoring': params.get('EnableDetailedMonitoring', False)
        }
        
        if not self.deploy_stack(
            f"{project_name}-{environment}-ec2",
            "infrastructure/ec2-autoscaling.yaml",
            ec2_params,
            capabilities=['CAPABILITY_NAMED_IAM'],
            tags=common_tags,
            enable_rollback=enable_rollback
        ):
            return False
        
        ec2_outputs = self.get_stack_outputs(f"{project_name}-{environment}-ec2")
        
        # 5. Deploy Monitoring
        print("=== Deploying Monitoring ===")
        monitoring_params = {
            'ProjectName': params['ProjectName'],
            'Environment': params['Environment'],
            'AlertEmail': params['AlertEmail'],
            'LoadBalancerFullName': alb_outputs.get('LoadBalancerArn', '').split('/')[-1],
            'TargetGroupFullName': alb_outputs.get('TargetGroupFullName'),
            'AutoScalingGroupName': ec2_outputs.get('AutoScalingGroupName'),
            'LogRetentionDays': params.get('LogRetentionDays', 7)
        }
        
        if not self.deploy_stack(
            f"{project_name}-{environment}-monitoring",
            "infrastructure/monitoring.yaml",
            monitoring_params,
            capabilities=['CAPABILITY_NAMED_IAM'],
            tags=common_tags,
            enable_rollback=enable_rollback
        ):
            return False
        
        # 6. Deploy Cost Monitoring
        print("=== Deploying Cost Monitoring ===")
        cost_params = {
            'ProjectName': params['ProjectName'],
            'Environment': params['Environment'],
            'AlertEmail': params['AlertEmail']
        }
        
        if not self.deploy_stack(
            f"{project_name}-{environment}-cost",
            "infrastructure/cost-monitoring.yaml",
            cost_params,
            capabilities=['CAPABILITY_NAMED_IAM'],
            tags=common_tags,
            enable_rollback=enable_rollback
        ):
            return False
        
        # Print deployment summary
        print("\n=== Deployment Summary ===")
        print(f"Application URL: {alb_outputs.get('ApplicationURL')}")
        print(f"Dashboard URL: {self.get_stack_outputs(f'{project_name}-{environment}-monitoring').get('DashboardURL')}")
        print(f"Cost Dashboard URL: {self.get_stack_outputs(f'{project_name}-{environment}-cost').get('CostDashboardURL')}")
        print(f"Alert Email: {alert_email}")
        
        return True
    
    def cleanup_stacks(self, project_name: str, environment: str) -> bool:
        """Clean up all stacks for the project"""
        stacks = [
            f"{project_name}-{environment}-cost",
            f"{project_name}-{environment}-monitoring",
            f"{project_name}-{environment}-ec2",
            f"{project_name}-{environment}-rds",
            f"{project_name}-{environment}-alb",
            f"{project_name}-{environment}-vpc"
        ]
        
        for stack_name in stacks:
            try:
                print(f"Deleting stack: {stack_name}")
                self.cloudformation.delete_stack(StackName=stack_name)
                
                waiter = self.cloudformation.get_waiter('stack_delete_complete')
                waiter.wait(
                    StackName=stack_name,
                    WaiterConfig={'Delay': 30, 'MaxAttempts': 120}
                )
                print(f"Stack {stack_name} deleted successfully")
                
            except self.cloudformation.exceptions.ClientError as e:
                if 'does not exist' in str(e):
                    print(f"Stack {stack_name} does not exist, skipping")
                else:
                    print(f"Error deleting stack {stack_name}: {e}")
                    return False
            except Exception as e:
                print(f"Error deleting stack {stack_name}: {e}")
                return False
        
        return True
    
    def validate_free_tier_compliance(self, project_name: str, environment: str) -> bool:
        """Validate that the deployment stays within free tier limits"""
        print("=== Validating Free Tier Compliance ===")
        
        # Check EC2 instances
        ec2 = self.session.client('ec2', region_name=self.region)
        instances = ec2.describe_instances(
            Filters=[
                {'Name': 'tag:Project', 'Values': [project_name]},
                {'Name': 'tag:Environment', 'Values': [environment]},
                {'Name': 'instance-state-name', 'Values': ['running', 'pending']}
            ]
        )
        
        instance_count = 0
        non_free_tier_instances = []
        
        for reservation in instances['Reservations']:
            for instance in reservation['Instances']:
                instance_count += 1
                instance_type = instance['InstanceType']
                if instance_type not in ['t2.micro', 't3.micro']:
                    non_free_tier_instances.append(instance_type)
        
        print(f"EC2 Instances: {instance_count} (Max recommended: 3 for free tier)")
        if non_free_tier_instances:
            print(f"WARNING: Non-free-tier instances found: {non_free_tier_instances}")
        
        # Check EBS volumes
        volumes = ec2.describe_volumes(
            Filters=[
                {'Name': 'tag:Project', 'Values': [project_name]},
                {'Name': 'tag:Environment', 'Values': [environment]}
            ]
        )
        
        total_ebs_size = sum(vol['Size'] for vol in volumes['Volumes'])
        print(f"EBS Storage: {total_ebs_size} GB (Free tier limit: 30 GB)")
        
        if total_ebs_size > 30:
            print("WARNING: EBS storage exceeds free tier limit")
        
        # Check RDS instances
        rds = self.session.client('rds', region_name=self.region)
        try:
            db_instances = rds.describe_db_instances()
            rds_count = 0
            non_free_tier_rds = []
            
            for instance in db_instances['DBInstances']:
                # Check if instance belongs to this project
                tags = rds.list_tags_for_resource(
                    ResourceName=instance['DBInstanceArn']
                )['TagList']
                
                project_tag = next((tag for tag in tags if tag['Key'] == 'Project'), None)
                if project_tag and project_tag['Value'] == project_name:
                    rds_count += 1
                    if instance['DBInstanceClass'] not in ['db.t2.micro', 'db.t3.micro']:
                        non_free_tier_rds.append(instance['DBInstanceClass'])
            
            print(f"RDS Instances: {rds_count} (Free tier limit: 1)")
            if non_free_tier_rds:
                print(f"WARNING: Non-free-tier RDS instances found: {non_free_tier_rds}")
                
        except Exception as e:
            print(f"Could not check RDS instances: {e}")
        
        return True

def main():
    parser = argparse.ArgumentParser(description='Deploy dominoes application with parameter validation and rollback support')
    parser.add_argument('action', choices=['deploy', 'cleanup', 'validate', 'rollback'], 
                       help='Action to perform')
    parser.add_argument('--project-name', default='dominoes-app', 
                       help='Project name')
    parser.add_argument('--environment', default='dev', 
                       help='Environment name (dev, staging, prod)')
    parser.add_argument('--region', default='us-east-1', 
                       help='AWS region')
    parser.add_argument('--profile', help='AWS profile to use')
    parser.add_argument('--alert-email', 
                       help='Email for alerts (overrides parameter file)')
    parser.add_argument('--parameter-file', 
                       help='Path to parameter file (defaults to infrastructure/parameters/{environment}.json)')
    parser.add_argument('--disable-rollback', action='store_true',
                       help='Disable automatic rollback on deployment failure')
    parser.add_argument('--stack-name', 
                       help='Specific stack name for rollback action')
    
    args = parser.parse_args()
    
    deployer = DominoesAppDeployer(region=args.region, profile=args.profile)
    
    if args.action == 'deploy':
        success = deployer.deploy_full_application(
            args.project_name, 
            args.environment, 
            args.alert_email,
            args.parameter_file,
            enable_rollback=not args.disable_rollback
        )
        if success:
            deployer.validate_free_tier_compliance(args.project_name, args.environment)
        sys.exit(0 if success else 1)
        
    elif args.action == 'cleanup':
        success = deployer.cleanup_stacks(args.project_name, args.environment)
        sys.exit(0 if success else 1)
        
    elif args.action == 'validate':
        success = deployer.validate_free_tier_compliance(args.project_name, args.environment)
        sys.exit(0 if success else 1)
        
    elif args.action == 'rollback':
        if not args.stack_name:
            print("Stack name is required for rollback action")
            sys.exit(1)
        success = deployer.rollback_stack(args.stack_name)
        sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()