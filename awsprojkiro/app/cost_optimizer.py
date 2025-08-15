"""
Cost optimization utilities for AWS free tier compliance and cost monitoring.
"""

import os
import logging
import boto3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json

logger = logging.getLogger(__name__)

class FreeTierMonitor:
    """Monitor AWS free tier usage and provide optimization recommendations"""
    
    # Free tier limits (monthly)
    FREE_TIER_LIMITS = {
        'ec2_hours': 750,           # t2.micro/t3.micro hours
        'ebs_storage_gb': 30,       # EBS storage
        'ebs_iops': 2000000,        # EBS I/O operations
        'rds_hours': 750,           # db.t2.micro/db.t3.micro hours
        'rds_storage_gb': 20,       # RDS storage
        'alb_data_gb': 15,          # ALB data processing
        'cloudwatch_metrics': 10,   # Custom metrics
        'cloudwatch_alarms': 10,    # CloudWatch alarms
        'lambda_requests': 1000000, # Lambda requests
        'lambda_compute_seconds': 400000,  # Lambda compute time
        'sns_notifications': 1000,  # SNS notifications
        'data_transfer_gb': 15      # Data transfer out
    }
    
    def __init__(self, region='us-east-1'):
        self.region = region
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        self.ec2 = boto3.client('ec2', region_name=region)
        self.rds = boto3.client('rds', region_name=region)
        self.pricing = boto3.client('pricing', region_name='us-east-1')  # Pricing API only in us-east-1
    
    def get_current_usage(self, project_name: str, environment: str) -> Dict:
        """Get current month usage for all services"""
        now = datetime.utcnow()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        usage = {
            'period': {
                'start': start_of_month.isoformat(),
                'end': now.isoformat(),
                'days_elapsed': (now - start_of_month).days + 1
            },
            'ec2': self._get_ec2_usage(project_name, environment, start_of_month, now),
            'rds': self._get_rds_usage(project_name, environment, start_of_month, now),
            'ebs': self._get_ebs_usage(project_name, environment),
            'alb': self._get_alb_usage(project_name, environment, start_of_month, now),
            'cloudwatch': self._get_cloudwatch_usage(project_name, environment),
            'estimated_costs': self._get_estimated_costs()
        }
        
        return usage
    
    def _get_ec2_usage(self, project_name: str, environment: str, start_time: datetime, end_time: datetime) -> Dict:
        """Get EC2 usage statistics"""
        try:
            # Get running instances with project tags
            instances = self.ec2.describe_instances(
                Filters=[
                    {'Name': 'tag:Project', 'Values': [project_name]},
                    {'Name': 'tag:Environment', 'Values': [environment]},
                    {'Name': 'instance-state-name', 'Values': ['running', 'stopped']}
                ]
            )
            
            total_hours = 0
            instance_count = 0
            instance_types = {}
            
            for reservation in instances['Reservations']:
                for instance in reservation['Instances']:
                    instance_count += 1
                    instance_type = instance['InstanceType']
                    instance_types[instance_type] = instance_types.get(instance_type, 0) + 1
                    
                    # Calculate hours (simplified - assumes running for full period)
                    launch_time = instance['LaunchTime'].replace(tzinfo=None)
                    if launch_time < start_time:
                        hours = (end_time - start_time).total_seconds() / 3600
                    else:
                        hours = (end_time - launch_time).total_seconds() / 3600
                    
                    total_hours += max(0, hours)
            
            usage_percentage = (total_hours / self.FREE_TIER_LIMITS['ec2_hours']) * 100
            
            return {
                'total_hours': round(total_hours, 2),
                'instance_count': instance_count,
                'instance_types': instance_types,
                'usage_percentage': round(usage_percentage, 2),
                'free_tier_limit': self.FREE_TIER_LIMITS['ec2_hours'],
                'remaining_hours': max(0, self.FREE_TIER_LIMITS['ec2_hours'] - total_hours)
            }
            
        except Exception as e:
            logger.error(f"Error getting EC2 usage: {e}")
            return {'error': str(e)}
    
    def _get_rds_usage(self, project_name: str, environment: str, start_time: datetime, end_time: datetime) -> Dict:
        """Get RDS usage statistics"""
        try:
            # Get RDS instances with project tags
            instances = self.rds.describe_db_instances()
            
            total_hours = 0
            instance_count = 0
            instance_classes = {}
            
            for instance in instances['DBInstances']:
                # Check tags
                tags = self.rds.list_tags_for_resource(
                    ResourceName=instance['DBInstanceArn']
                )['TagList']
                
                project_tag = next((tag for tag in tags if tag['Key'] == 'Project'), None)
                env_tag = next((tag for tag in tags if tag['Key'] == 'Environment'), None)
                
                if (project_tag and project_tag['Value'] == project_name and
                    env_tag and env_tag['Value'] == environment):
                    
                    instance_count += 1
                    instance_class = instance['DBInstanceClass']
                    instance_classes[instance_class] = instance_classes.get(instance_class, 0) + 1
                    
                    # Calculate hours (simplified)
                    create_time = instance['InstanceCreateTime'].replace(tzinfo=None)
                    if create_time < start_time:
                        hours = (end_time - start_time).total_seconds() / 3600
                    else:
                        hours = (end_time - create_time).total_seconds() / 3600
                    
                    total_hours += max(0, hours)
            
            usage_percentage = (total_hours / self.FREE_TIER_LIMITS['rds_hours']) * 100
            
            return {
                'total_hours': round(total_hours, 2),
                'instance_count': instance_count,
                'instance_classes': instance_classes,
                'usage_percentage': round(usage_percentage, 2),
                'free_tier_limit': self.FREE_TIER_LIMITS['rds_hours'],
                'remaining_hours': max(0, self.FREE_TIER_LIMITS['rds_hours'] - total_hours)
            }
            
        except Exception as e:
            logger.error(f"Error getting RDS usage: {e}")
            return {'error': str(e)}
    
    def _get_ebs_usage(self, project_name: str, environment: str) -> Dict:
        """Get EBS usage statistics"""
        try:
            volumes = self.ec2.describe_volumes(
                Filters=[
                    {'Name': 'tag:Project', 'Values': [project_name]},
                    {'Name': 'tag:Environment', 'Values': [environment]}
                ]
            )
            
            total_size_gb = 0
            volume_count = 0
            volume_types = {}
            
            for volume in volumes['Volumes']:
                volume_count += 1
                size_gb = volume['Size']
                volume_type = volume['VolumeType']
                
                total_size_gb += size_gb
                volume_types[volume_type] = volume_types.get(volume_type, 0) + size_gb
            
            usage_percentage = (total_size_gb / self.FREE_TIER_LIMITS['ebs_storage_gb']) * 100
            
            return {
                'total_size_gb': total_size_gb,
                'volume_count': volume_count,
                'volume_types': volume_types,
                'usage_percentage': round(usage_percentage, 2),
                'free_tier_limit': self.FREE_TIER_LIMITS['ebs_storage_gb'],
                'remaining_gb': max(0, self.FREE_TIER_LIMITS['ebs_storage_gb'] - total_size_gb)
            }
            
        except Exception as e:
            logger.error(f"Error getting EBS usage: {e}")
            return {'error': str(e)}
    
    def _get_alb_usage(self, project_name: str, environment: str, start_time: datetime, end_time: datetime) -> Dict:
        """Get ALB usage statistics"""
        try:
            # This would require querying CloudWatch metrics for ALB data processing
            # Simplified implementation
            return {
                'data_processed_gb': 0.5,  # Placeholder
                'usage_percentage': 3.3,   # (0.5/15)*100
                'free_tier_limit': self.FREE_TIER_LIMITS['alb_data_gb'],
                'remaining_gb': self.FREE_TIER_LIMITS['alb_data_gb'] - 0.5
            }
            
        except Exception as e:
            logger.error(f"Error getting ALB usage: {e}")
            return {'error': str(e)}
    
    def _get_cloudwatch_usage(self, project_name: str, environment: str) -> Dict:
        """Get CloudWatch usage statistics"""
        try:
            # Count custom metrics and alarms
            metrics = self.cloudwatch.list_metrics(
                Namespace=f'{project_name}/Application'
            )
            
            alarms = self.cloudwatch.describe_alarms(
                AlarmNamePrefix=f'{project_name}-{environment}'
            )
            
            custom_metrics = len(metrics['Metrics'])
            alarm_count = len(alarms['MetricAlarms'])
            
            return {
                'custom_metrics': custom_metrics,
                'alarms': alarm_count,
                'metrics_usage_percentage': (custom_metrics / self.FREE_TIER_LIMITS['cloudwatch_metrics']) * 100,
                'alarms_usage_percentage': (alarm_count / self.FREE_TIER_LIMITS['cloudwatch_alarms']) * 100,
                'free_tier_limits': {
                    'metrics': self.FREE_TIER_LIMITS['cloudwatch_metrics'],
                    'alarms': self.FREE_TIER_LIMITS['cloudwatch_alarms']
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting CloudWatch usage: {e}")
            return {'error': str(e)}
    
    def _get_estimated_costs(self) -> Dict:
        """Get estimated costs from CloudWatch billing metrics"""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=1)
            
            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/Billing',
                MetricName='EstimatedCharges',
                Dimensions=[
                    {'Name': 'Currency', 'Value': 'USD'}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=['Maximum']
            )
            
            if response['Datapoints']:
                latest_charge = max(response['Datapoints'], key=lambda x: x['Timestamp'])
                return {
                    'total_estimated_charges': latest_charge['Maximum'],
                    'timestamp': latest_charge['Timestamp'].isoformat()
                }
            
            return {'total_estimated_charges': 0.0}
            
        except Exception as e:
            logger.error(f"Error getting estimated costs: {e}")
            return {'error': str(e)}
    
    def get_optimization_recommendations(self, usage_data: Dict) -> List[Dict]:
        """Generate cost optimization recommendations based on usage"""
        recommendations = []
        
        # EC2 Recommendations
        if 'ec2' in usage_data and 'usage_percentage' in usage_data['ec2']:
            ec2_usage = usage_data['ec2']['usage_percentage']
            
            if ec2_usage > 90:
                recommendations.append({
                    'service': 'EC2',
                    'priority': 'HIGH',
                    'issue': f'EC2 usage at {ec2_usage:.1f}% of free tier limit',
                    'recommendation': 'Consider stopping unused instances or reducing instance count',
                    'potential_savings': 'Stay within free tier limits'
                })
            elif ec2_usage > 75:
                recommendations.append({
                    'service': 'EC2',
                    'priority': 'MEDIUM',
                    'issue': f'EC2 usage at {ec2_usage:.1f}% of free tier limit',
                    'recommendation': 'Monitor usage closely and optimize instance scheduling',
                    'potential_savings': 'Prevent free tier overage'
                })
        
        # RDS Recommendations
        if 'rds' in usage_data and 'usage_percentage' in usage_data['rds']:
            rds_usage = usage_data['rds']['usage_percentage']
            
            if rds_usage > 90:
                recommendations.append({
                    'service': 'RDS',
                    'priority': 'HIGH',
                    'issue': f'RDS usage at {rds_usage:.1f}% of free tier limit',
                    'recommendation': 'Consider stopping RDS during non-peak hours or use smaller instance',
                    'potential_savings': 'Stay within free tier limits'
                })
        
        # EBS Recommendations
        if 'ebs' in usage_data and 'usage_percentage' in usage_data['ebs']:
            ebs_usage = usage_data['ebs']['usage_percentage']
            
            if ebs_usage > 90:
                recommendations.append({
                    'service': 'EBS',
                    'priority': 'HIGH',
                    'issue': f'EBS storage at {ebs_usage:.1f}% of free tier limit',
                    'recommendation': 'Delete unused volumes or reduce volume sizes',
                    'potential_savings': 'Stay within free tier limits'
                })
        
        # General recommendations
        recommendations.extend([
            {
                'service': 'General',
                'priority': 'LOW',
                'issue': 'Cost optimization',
                'recommendation': 'Use AWS Cost Explorer to analyze spending patterns',
                'potential_savings': 'Better cost visibility'
            },
            {
                'service': 'General',
                'priority': 'LOW',
                'issue': 'Resource tagging',
                'recommendation': 'Ensure all resources are properly tagged for cost allocation',
                'potential_savings': 'Better cost tracking'
            }
        ])
        
        return recommendations
    
    def generate_cost_report(self, project_name: str, environment: str) -> Dict:
        """Generate comprehensive cost and usage report"""
        usage_data = self.get_current_usage(project_name, environment)
        recommendations = self.get_optimization_recommendations(usage_data)
        
        # Calculate overall free tier compliance
        compliance_scores = []
        
        for service in ['ec2', 'rds', 'ebs']:
            if service in usage_data and 'usage_percentage' in usage_data[service]:
                compliance_scores.append(min(100, usage_data[service]['usage_percentage']))
        
        overall_compliance = sum(compliance_scores) / len(compliance_scores) if compliance_scores else 0
        
        report = {
            'report_timestamp': datetime.utcnow().isoformat(),
            'project': project_name,
            'environment': environment,
            'usage_data': usage_data,
            'recommendations': recommendations,
            'compliance': {
                'overall_free_tier_usage_percentage': round(overall_compliance, 2),
                'status': 'GOOD' if overall_compliance < 75 else 'WARNING' if overall_compliance < 90 else 'CRITICAL',
                'high_priority_issues': len([r for r in recommendations if r['priority'] == 'HIGH'])
            },
            'summary': {
                'total_recommendations': len(recommendations),
                'services_monitored': len([k for k in usage_data.keys() if k not in ['period', 'estimated_costs']]),
                'estimated_monthly_cost': usage_data.get('estimated_costs', {}).get('total_estimated_charges', 0)
            }
        }
        
        return report

def get_cost_optimization_middleware():
    """Flask middleware for cost optimization tracking"""
    def middleware(app):
        @app.before_request
        def track_request_costs():
            # Track requests that might incur costs
            pass
        
        @app.after_request
        def log_cost_metrics(response):
            # Log metrics that help with cost optimization
            return response
    
    return middleware

# Utility functions for cost optimization
def estimate_monthly_cost(usage_data: Dict) -> float:
    """Estimate monthly cost based on current usage"""
    # Simplified cost estimation
    cost = 0.0
    
    # EC2 costs (after free tier)
    if 'ec2' in usage_data:
        excess_hours = max(0, usage_data['ec2'].get('total_hours', 0) - 750)
        cost += excess_hours * 0.0116  # t2.micro hourly rate
    
    # RDS costs (after free tier)
    if 'rds' in usage_data:
        excess_hours = max(0, usage_data['rds'].get('total_hours', 0) - 750)
        cost += excess_hours * 0.017  # db.t3.micro hourly rate
    
    # EBS costs (after free tier)
    if 'ebs' in usage_data:
        excess_gb = max(0, usage_data['ebs'].get('total_size_gb', 0) - 30)
        cost += excess_gb * 0.10  # gp2 monthly rate per GB
    
    return round(cost, 2)

def check_free_tier_compliance(usage_data: Dict) -> Tuple[bool, List[str]]:
    """Check if usage is within free tier limits"""
    violations = []
    
    if 'ec2' in usage_data and usage_data['ec2'].get('usage_percentage', 0) > 100:
        violations.append(f"EC2 usage exceeds free tier limit")
    
    if 'rds' in usage_data and usage_data['rds'].get('usage_percentage', 0) > 100:
        violations.append(f"RDS usage exceeds free tier limit")
    
    if 'ebs' in usage_data and usage_data['ebs'].get('usage_percentage', 0) > 100:
        violations.append(f"EBS storage exceeds free tier limit")
    
    return len(violations) == 0, violations