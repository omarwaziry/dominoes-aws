#!/usr/bin/env python3
"""
Deployment monitoring script that tracks CloudFormation stack status
and provides real-time updates during deployment.
"""

import boto3
import time
import sys
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

class DeploymentMonitor:
    """Monitor CloudFormation deployment progress"""
    
    def __init__(self, region: str = 'us-east-1', profile: Optional[str] = None):
        self.region = region
        self.session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        self.cloudformation = self.session.client('cloudformation', region_name=region)
        self.seen_events = set()
    
    def get_stack_status(self, stack_name: str) -> Optional[Dict]:
        """Get current stack status"""
        try:
            response = self.cloudformation.describe_stacks(StackName=stack_name)
            return response['Stacks'][0] if response['Stacks'] else None
        except self.cloudformation.exceptions.ClientError:
            return None
    
    def get_stack_events(self, stack_name: str, since: Optional[datetime] = None) -> List[Dict]:
        """Get stack events since a specific time"""
        try:
            paginator = self.cloudformation.get_paginator('describe_stack_events')
            events = []
            
            for page in paginator.paginate(StackName=stack_name):
                for event in page['StackEvents']:
                    event_time = event['Timestamp'].replace(tzinfo=None)
                    
                    # Filter by time if specified
                    if since and event_time <= since:
                        continue
                    
                    # Skip events we've already seen
                    event_id = f"{event['LogicalResourceId']}-{event['Timestamp']}-{event.get('ResourceStatus', '')}"
                    if event_id in self.seen_events:
                        continue
                    
                    self.seen_events.add(event_id)
                    events.append(event)
            
            # Sort by timestamp (oldest first)
            events.sort(key=lambda x: x['Timestamp'])
            return events
            
        except Exception as e:
            print(f"Error getting stack events: {e}")
            return []
    
    def format_event(self, event: Dict) -> str:
        """Format a stack event for display"""
        timestamp = event['Timestamp'].strftime('%H:%M:%S')
        resource_type = event.get('ResourceType', 'Unknown')
        logical_id = event.get('LogicalResourceId', 'Unknown')
        status = event.get('ResourceStatus', 'Unknown')
        reason = event.get('ResourceStatusReason', '')
        
        # Color coding for status
        if 'COMPLETE' in status:
            status_color = '\033[0;32m'  # Green
        elif 'FAILED' in status:
            status_color = '\033[0;31m'  # Red
        elif 'IN_PROGRESS' in status:
            status_color = '\033[0;33m'  # Yellow
        else:
            status_color = '\033[0m'     # Default
        
        reset_color = '\033[0m'
        
        line = f"[{timestamp}] {resource_type} {logical_id}: {status_color}{status}{reset_color}"
        
        if reason and ('FAILED' in status or 'ROLLBACK' in status):
            line += f"\n  Reason: {reason}"
        
        return line
    
    def monitor_stack(self, stack_name: str, timeout_minutes: int = 60) -> bool:
        """Monitor a stack deployment until completion"""
        print(f"Monitoring stack: {stack_name}")
        print(f"Timeout: {timeout_minutes} minutes")
        print("-" * 80)
        
        start_time = datetime.utcnow()
        timeout_time = start_time + timedelta(minutes=timeout_minutes)
        
        last_status = None
        
        while datetime.utcnow() < timeout_time:
            stack = self.get_stack_status(stack_name)
            
            if not stack:
                print(f"Stack {stack_name} not found")
                return False
            
            current_status = stack['StackStatus']
            
            # Show status change
            if current_status != last_status:
                print(f"\nStack Status: {current_status}")
                last_status = current_status
            
            # Get and display new events
            events = self.get_stack_events(stack_name, start_time)
            for event in events:
                print(self.format_event(event))
            
            # Check if deployment is complete
            if current_status.endswith('_COMPLETE'):
                if 'ROLLBACK' in current_status:
                    print(f"\n❌ Stack deployment failed and rolled back: {current_status}")
                    return False
                else:
                    print(f"\n✅ Stack deployment completed successfully: {current_status}")
                    return True
            elif current_status.endswith('_FAILED'):
                print(f"\n❌ Stack deployment failed: {current_status}")
                return False
            
            # Wait before next check
            time.sleep(10)
        
        print(f"\n⏰ Monitoring timeout reached ({timeout_minutes} minutes)")
        print(f"Final status: {last_status}")
        return False
    
    def monitor_multiple_stacks(self, stack_names: List[str], timeout_minutes: int = 60) -> Dict[str, bool]:
        """Monitor multiple stacks simultaneously"""
        print(f"Monitoring {len(stack_names)} stacks:")
        for stack_name in stack_names:
            print(f"  - {stack_name}")
        print(f"Timeout: {timeout_minutes} minutes")
        print("=" * 80)
        
        start_time = datetime.utcnow()
        timeout_time = start_time + timedelta(minutes=timeout_minutes)
        
        results = {}
        completed_stacks = set()
        last_statuses = {}
        
        while datetime.utcnow() < timeout_time and len(completed_stacks) < len(stack_names):
            for stack_name in stack_names:
                if stack_name in completed_stacks:
                    continue
                
                stack = self.get_stack_status(stack_name)
                if not stack:
                    print(f"Stack {stack_name} not found")
                    results[stack_name] = False
                    completed_stacks.add(stack_name)
                    continue
                
                current_status = stack['StackStatus']
                
                # Show status change
                if current_status != last_statuses.get(stack_name):
                    print(f"\n[{stack_name}] Status: {current_status}")
                    last_statuses[stack_name] = current_status
                
                # Get and display new events
                events = self.get_stack_events(stack_name, start_time)
                for event in events:
                    print(f"[{stack_name}] {self.format_event(event)}")
                
                # Check if deployment is complete
                if current_status.endswith('_COMPLETE'):
                    if 'ROLLBACK' in current_status:
                        print(f"\n❌ [{stack_name}] Deployment failed and rolled back: {current_status}")
                        results[stack_name] = False
                    else:
                        print(f"\n✅ [{stack_name}] Deployment completed successfully: {current_status}")
                        results[stack_name] = True
                    completed_stacks.add(stack_name)
                elif current_status.endswith('_FAILED'):
                    print(f"\n❌ [{stack_name}] Deployment failed: {current_status}")
                    results[stack_name] = False
                    completed_stacks.add(stack_name)
            
            # Wait before next check
            if len(completed_stacks) < len(stack_names):
                time.sleep(10)
        
        # Handle timeout
        for stack_name in stack_names:
            if stack_name not in results:
                print(f"\n⏰ [{stack_name}] Monitoring timeout reached")
                results[stack_name] = False
        
        return results
    
    def get_deployment_summary(self, project_name: str, environment: str) -> Dict:
        """Get summary of all stacks for a deployment"""
        stack_prefixes = [
            f"{project_name}-{environment}-vpc",
            f"{project_name}-{environment}-alb",
            f"{project_name}-{environment}-rds",
            f"{project_name}-{environment}-ec2",
            f"{project_name}-{environment}-monitoring",
            f"{project_name}-{environment}-cost"
        ]
        
        summary = {
            'project': project_name,
            'environment': environment,
            'stacks': {},
            'overall_status': 'UNKNOWN'
        }
        
        all_complete = True
        any_failed = False
        
        for stack_name in stack_prefixes:
            stack = self.get_stack_status(stack_name)
            if stack:
                status = stack['StackStatus']
                summary['stacks'][stack_name] = {
                    'status': status,
                    'creation_time': stack.get('CreationTime'),
                    'last_updated': stack.get('LastUpdatedTime'),
                    'outputs': {o['OutputKey']: o['OutputValue'] for o in stack.get('Outputs', [])}
                }
                
                if not status.endswith('_COMPLETE') or 'ROLLBACK' in status:
                    all_complete = False
                if 'FAILED' in status:
                    any_failed = True
            else:
                summary['stacks'][stack_name] = {'status': 'NOT_FOUND'}
                all_complete = False
        
        if any_failed:
            summary['overall_status'] = 'FAILED'
        elif all_complete:
            summary['overall_status'] = 'COMPLETE'
        else:
            summary['overall_status'] = 'IN_PROGRESS'
        
        return summary

def main():
    parser = argparse.ArgumentParser(description='Monitor CloudFormation deployment progress')
    parser.add_argument('--stack-name', help='Single stack name to monitor')
    parser.add_argument('--project-name', default='dominoes-app', help='Project name for multi-stack monitoring')
    parser.add_argument('--environment', default='dev', help='Environment name for multi-stack monitoring')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--profile', help='AWS profile to use')
    parser.add_argument('--timeout', type=int, default=60, help='Timeout in minutes')
    parser.add_argument('--summary', action='store_true', help='Show deployment summary and exit')
    parser.add_argument('--json', action='store_true', help='Output summary in JSON format')
    
    args = parser.parse_args()
    
    monitor = DeploymentMonitor(region=args.region, profile=args.profile)
    
    if args.summary:
        summary = monitor.get_deployment_summary(args.project_name, args.environment)
        if args.json:
            print(json.dumps(summary, indent=2, default=str))
        else:
            print(f"Deployment Summary: {args.project_name}-{args.environment}")
            print(f"Overall Status: {summary['overall_status']}")
            print("\nStack Status:")
            for stack_name, info in summary['stacks'].items():
                print(f"  {stack_name}: {info['status']}")
        sys.exit(0)
    
    if args.stack_name:
        # Monitor single stack
        success = monitor.monitor_stack(args.stack_name, args.timeout)
        sys.exit(0 if success else 1)
    else:
        # Monitor all stacks for the project
        stack_names = [
            f"{args.project_name}-{args.environment}-vpc",
            f"{args.project_name}-{args.environment}-alb",
            f"{args.project_name}-{args.environment}-ec2",
            f"{args.project_name}-{args.environment}-monitoring",
            f"{args.project_name}-{args.environment}-cost"
        ]
        
        # Add RDS stack if it exists
        rds_stack = f"{args.project_name}-{args.environment}-rds"
        if monitor.get_stack_status(rds_stack):
            stack_names.insert(-2, rds_stack)  # Insert before monitoring and cost
        
        results = monitor.monitor_multiple_stacks(stack_names, args.timeout)
        
        print("\n" + "=" * 80)
        print("FINAL RESULTS:")
        all_success = True
        for stack_name, success in results.items():
            status = "✅ SUCCESS" if success else "❌ FAILED"
            print(f"  {stack_name}: {status}")
            if not success:
                all_success = False
        
        print(f"\nOverall Result: {'✅ SUCCESS' if all_success else '❌ FAILED'}")
        sys.exit(0 if all_success else 1)

if __name__ == '__main__':
    main()