#!/usr/bin/env python3
"""
Configuration validation script for deployment parameters.
Validates parameter files for free tier compliance and best practices.
"""

import json
import sys
import argparse
from typing import Dict, List, Tuple
import os

class ConfigValidator:
    """Validate deployment configuration parameters"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def validate_file(self, parameter_file: str) -> Tuple[bool, List[str], List[str]]:
        """Validate a parameter file"""
        self.errors = []
        self.warnings = []
        
        if not os.path.exists(parameter_file):
            self.errors.append(f"Parameter file not found: {parameter_file}")
            return False, self.errors, self.warnings
        
        try:
            with open(parameter_file, 'r') as f:
                params = json.load(f)
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON in {parameter_file}: {e}")
            return False, self.errors, self.warnings
        except Exception as e:
            self.errors.append(f"Error reading {parameter_file}: {e}")
            return False, self.errors, self.warnings
        
        # Validate parameters
        self._validate_required_parameters(params)
        self._validate_free_tier_compliance(params)
        self._validate_environment_specific(params)
        self._validate_security_settings(params)
        self._validate_monitoring_settings(params)
        
        return len(self.errors) == 0, self.errors, self.warnings
    
    def _validate_required_parameters(self, params: Dict) -> None:
        """Validate required parameters are present"""
        required_params = [
            'ProjectName', 'Environment', 'InstanceType', 'MinInstances',
            'MaxInstances', 'DesiredInstances', 'AlertEmail'
        ]
        
        for param in required_params:
            if param not in params or params[param] is None or params[param] == "":
                self.errors.append(f"Required parameter '{param}' is missing or empty")
    
    def _validate_free_tier_compliance(self, params: Dict) -> None:
        """Validate free tier compliance"""
        # EC2 instance type
        instance_type = params.get('InstanceType', '')
        if instance_type not in ['t2.micro', 't3.micro']:
            self.errors.append(f"Instance type '{instance_type}' is not free tier eligible. Use t2.micro or t3.micro")
        
        # Instance limits
        max_instances = params.get('MaxInstances', 0)
        if max_instances > 3:
            self.warnings.append(f"MaxInstances ({max_instances}) may exceed free tier limits (recommended: ≤3)")
        
        min_instances = params.get('MinInstances', 0)
        if min_instances > 2:
            self.warnings.append(f"MinInstances ({min_instances}) may exceed free tier limits (recommended: ≤2)")
        
        # RDS validation if enabled
        if params.get('EnableRDS', False):
            db_instance_class = params.get('DBInstanceClass', '')
            if db_instance_class not in ['db.t2.micro', 'db.t3.micro']:
                self.errors.append(f"RDS instance class '{db_instance_class}' is not free tier eligible")
            
            db_storage = params.get('DBAllocatedStorage', 0)
            if db_storage > 20:
                self.warnings.append(f"RDS storage ({db_storage}GB) exceeds free tier limit of 20GB")
            
            backup_retention = params.get('BackupRetentionPeriod', 0)
            if backup_retention > 7:
                self.warnings.append(f"RDS backup retention ({backup_retention} days) may incur costs beyond free tier")
    
    def _validate_environment_specific(self, params: Dict) -> None:
        """Validate environment-specific settings"""
        environment = params.get('Environment', '').lower()
        
        if environment == 'prod':
            # Production should have higher availability
            if not params.get('MultiAZ', False):
                self.warnings.append("Production environment should use Multi-AZ for high availability")
            
            if params.get('BackupRetentionPeriod', 0) < 7:
                self.warnings.append("Production environment should have backup retention ≥ 7 days")
            
            if not params.get('DeletionProtection', False):
                self.warnings.append("Production environment should enable deletion protection")
            
            if not params.get('EnableDetailedMonitoring', False):
                self.warnings.append("Production environment should enable detailed monitoring")
            
            # Production should have more conservative scaling
            cpu_target = params.get('CPUTargetValue', 70.0)
            if cpu_target > 70.0:
                self.warnings.append(f"Production CPU target ({cpu_target}%) should be ≤ 70% for better performance")
        
        elif environment == 'dev':
            # Dev can be more aggressive to save costs
            if params.get('MultiAZ', False):
                self.warnings.append("Development environment doesn't need Multi-AZ (increases costs)")
            
            if params.get('EnableDetailedMonitoring', False):
                self.warnings.append("Development environment doesn't need detailed monitoring (increases costs)")
    
    def _validate_security_settings(self, params: Dict) -> None:
        """Validate security-related settings"""
        # Health check settings
        health_check_path = params.get('HealthCheckPath', '')
        if not health_check_path.startswith('/'):
            self.errors.append("HealthCheckPath must start with '/'")
        
        # Thresholds should be reasonable
        healthy_threshold = params.get('HealthyThresholdCount', 2)
        if healthy_threshold < 2:
            self.warnings.append("HealthyThresholdCount should be ≥ 2 for reliability")
        
        unhealthy_threshold = params.get('UnhealthyThresholdCount', 3)
        if unhealthy_threshold < 2:
            self.warnings.append("UnhealthyThresholdCount should be ≥ 2 to avoid false positives")
    
    def _validate_monitoring_settings(self, params: Dict) -> None:
        """Validate monitoring and alerting settings"""
        # Alert email validation
        alert_email = params.get('AlertEmail', '')
        if alert_email and '@' not in alert_email:
            self.errors.append("AlertEmail must be a valid email address")
        
        # Log retention
        log_retention = params.get('LogRetentionDays', 7)
        if log_retention > 30:
            self.warnings.append(f"Log retention ({log_retention} days) may increase costs")
        
        # Scaling cooldowns
        scale_up_cooldown = params.get('ScaleUpCooldown', 300)
        if scale_up_cooldown < 60:
            self.warnings.append("ScaleUpCooldown should be ≥ 60 seconds to avoid thrashing")
        
        scale_down_cooldown = params.get('ScaleDownCooldown', 300)
        if scale_down_cooldown < 300:
            self.warnings.append("ScaleDownCooldown should be ≥ 300 seconds for stability")

def main():
    parser = argparse.ArgumentParser(description='Validate deployment configuration parameters')
    parser.add_argument('parameter_file', help='Path to parameter file to validate')
    parser.add_argument('--strict', action='store_true', 
                       help='Treat warnings as errors')
    parser.add_argument('--quiet', action='store_true',
                       help='Only show errors and warnings, not success messages')
    
    args = parser.parse_args()
    
    validator = ConfigValidator()
    is_valid, errors, warnings = validator.validate_file(args.parameter_file)
    
    if not args.quiet:
        print(f"Validating: {args.parameter_file}")
        print()
    
    # Show errors
    if errors:
        print("ERRORS:")
        for error in errors:
            print(f"  ❌ {error}")
        print()
    
    # Show warnings
    if warnings:
        print("WARNINGS:")
        for warning in warnings:
            print(f"  ⚠️  {warning}")
        print()
    
    # Determine final result
    if args.strict:
        final_valid = is_valid and len(warnings) == 0
        if warnings and is_valid:
            print("❌ VALIDATION FAILED (strict mode - warnings treated as errors)")
    else:
        final_valid = is_valid
    
    if final_valid:
        if not args.quiet:
            print("✅ VALIDATION PASSED")
    else:
        print("❌ VALIDATION FAILED")
    
    # Exit with appropriate code
    sys.exit(0 if final_valid else 1)

if __name__ == '__main__':
    main()