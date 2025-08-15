# Deployment Guide

This guide covers the deployment automation scripts and procedures for the AWS Scalable Web Application.

## Overview

The deployment system provides:
- **Parameter validation** for free tier compliance and best practices
- **Environment-specific configurations** (dev, staging, prod)
- **Automated rollback** on deployment failures
- **Real-time monitoring** of deployment progress
- **Stack update procedures** with change detection

## Files Structure

```
scripts/
├── deploy.sh                 # Main deployment orchestration script
├── package-app.sh            # Application packaging and S3 upload
├── validate-config.py        # Parameter validation utility
└── monitor-deployment.py     # Deployment monitoring utility

infrastructure/
├── deploy.py                 # CloudFormation deployment script
└── parameters/               # Environment-specific parameter files
    ├── dev.json             # Development environment parameters
    ├── staging.json         # Staging environment parameters
    └── prod.json            # Production environment parameters
```

## Quick Start

### 1. Set Required Environment Variables

```bash
export ALERT_EMAIL="your-email@example.com"
export ENVIRONMENT="dev"  # or staging, prod
export AWS_REGION="us-east-1"
export AWS_PROFILE="your-profile"  # optional
```

### 2. Deploy Application

```bash
# Deploy to development
./scripts/deploy.sh

# Deploy to staging
ENVIRONMENT=staging ./scripts/deploy.sh

# Deploy with custom parameter file
PARAMETER_FILE=my-custom-params.json ./scripts/deploy.sh
```

### 3. Monitor Deployment

```bash
# Monitor all stacks for a project
python3 scripts/monitor-deployment.py --project-name dominoes-app --environment dev

# Monitor specific stack
python3 scripts/monitor-deployment.py --stack-name dominoes-app-dev-vpc

# Get deployment summary
python3 scripts/monitor-deployment.py --summary --project-name dominoes-app --environment dev
```

## Parameter Files

Parameter files define environment-specific configurations. They are located in `infrastructure/parameters/`.

### Example Parameter File Structure

```json
{
  "ProjectName": "dominoes-app",
  "Environment": "dev",
  "InstanceType": "t2.micro",
  "MinInstances": 1,
  "MaxInstances": 2,
  "DesiredInstances": 1,
  "EnableRDS": false,
  "DBInstanceClass": "db.t3.micro",
  "DBAllocatedStorage": 20,
  "AlertEmail": "",
  "HealthCheckPath": "/health",
  "HealthCheckIntervalSeconds": 30,
  "HealthyThresholdCount": 2,
  "UnhealthyThresholdCount": 3,
  "ScaleUpCooldown": 300,
  "ScaleDownCooldown": 300,
  "CPUTargetValue": 70.0,
  "EnableDetailedMonitoring": false,
  "LogRetentionDays": 7,
  "BackupRetentionPeriod": 1,
  "MultiAZ": false,
  "DeletionProtection": false,
  "Tags": {
    "Project": "dominoes-app",
    "Environment": "dev",
    "Owner": "developer",
    "CostCenter": "development",
    "Application": "dominoes-game"
  }
}
```

### Environment Differences

| Parameter | Dev | Staging | Prod |
|-----------|-----|---------|------|
| MinInstances | 1 | 2 | 2 |
| MaxInstances | 2 | 3 | 3 |
| EnableRDS | false | true | true |
| MultiAZ | false | true | true |
| DetailedMonitoring | false | true | true |
| LogRetentionDays | 7 | 14 | 30 |
| BackupRetentionPeriod | 1 | 7 | 30 |
| DeletionProtection | false | false | true |

## Deployment Commands

### Main Deployment Script (`scripts/deploy.sh`)

```bash
# Basic deployment
./scripts/deploy.sh

# Deploy with options
ENVIRONMENT=staging \
PARAMETER_FILE=custom-params.json \
DISABLE_ROLLBACK=true \
./scripts/deploy.sh

# Rollback a specific stack
./scripts/deploy.sh rollback dominoes-app-dev-vpc

# Cleanup all resources
./scripts/deploy.sh cleanup

# Dry run (show what would be done)
DRY_RUN=true ./scripts/deploy.sh
```

### Python Deployment Script (`infrastructure/deploy.py`)

```bash
# Deploy with parameter file
python3 infrastructure/deploy.py deploy \
  --project-name dominoes-app \
  --environment dev \
  --alert-email admin@example.com \
  --parameter-file infrastructure/parameters/dev.json

# Rollback specific stack
python3 infrastructure/deploy.py rollback \
  --stack-name dominoes-app-dev-vpc

# Cleanup all stacks
python3 infrastructure/deploy.py cleanup \
  --project-name dominoes-app \
  --environment dev

# Validate free tier compliance
python3 infrastructure/deploy.py validate \
  --project-name dominoes-app \
  --environment dev
```

## Parameter Validation

### Validate Configuration Files

```bash
# Validate a parameter file
python3 scripts/validate-config.py infrastructure/parameters/dev.json

# Strict validation (warnings as errors)
python3 scripts/validate-config.py --strict infrastructure/parameters/prod.json

# Quiet mode (only show issues)
python3 scripts/validate-config.py --quiet infrastructure/parameters/staging.json
```

### Validation Rules

The validator checks for:

1. **Required Parameters**: All mandatory parameters are present
2. **Free Tier Compliance**: Instance types and limits within free tier
3. **Environment Best Practices**: Appropriate settings for each environment
4. **Security Settings**: Proper health check and security configurations
5. **Monitoring Settings**: Reasonable alerting and logging configurations

## Rollback Procedures

### Automatic Rollback

Automatic rollback is enabled by default and triggers when:
- Stack update fails
- Template validation fails
- Resource creation fails

### Manual Rollback

```bash
# Rollback specific stack
./scripts/deploy.sh rollback dominoes-app-dev-ec2

# Or using Python script
python3 infrastructure/deploy.py rollback --stack-name dominoes-app-dev-ec2
```

### Rollback Limitations

- Only works for stacks in failed or completed states
- Requires previous deployment backup
- Cannot rollback stack creation (only updates)

## Monitoring and Troubleshooting

### Real-time Monitoring

```bash
# Monitor all stacks
python3 scripts/monitor-deployment.py \
  --project-name dominoes-app \
  --environment dev \
  --timeout 60

# Monitor with JSON output
python3 scripts/monitor-deployment.py \
  --summary \
  --json \
  --project-name dominoes-app \
  --environment dev
```

### Common Issues

1. **Parameter Validation Failures**
   - Check parameter file syntax with `jq`
   - Validate against schema using validation script
   - Ensure all required parameters are present

2. **Free Tier Limit Exceeded**
   - Review instance types and counts
   - Check EBS storage allocation
   - Validate RDS configuration

3. **Stack Update Failures**
   - Check CloudFormation events in AWS Console
   - Review resource dependencies
   - Verify IAM permissions

4. **Rollback Failures**
   - Check stack status in AWS Console
   - Manually fix resource conflicts
   - Use AWS Console for manual rollback

### Debugging

```bash
# Enable debug output
set -x
./scripts/deploy.sh

# Check AWS CLI configuration
aws sts get-caller-identity

# Validate CloudFormation templates
aws cloudformation validate-template --template-body file://infrastructure/vpc-network.yaml
```

## Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `PROJECT_NAME` | Project identifier | dominoes-app | No |
| `ENVIRONMENT` | Environment name | dev | No |
| `AWS_REGION` | AWS region | us-east-1 | No |
| `ALERT_EMAIL` | Email for alerts | - | Yes |
| `AWS_PROFILE` | AWS profile | default | No |
| `PARAMETER_FILE` | Custom parameter file | - | No |
| `DISABLE_ROLLBACK` | Disable auto rollback | false | No |
| `SKIP_PACKAGING` | Skip app packaging | false | No |
| `DRY_RUN` | Show actions only | false | No |

## Best Practices

### Development
- Use minimal resources (1 instance, no RDS)
- Disable detailed monitoring
- Short log retention periods
- No deletion protection

### Staging
- Mirror production configuration
- Enable RDS with Multi-AZ
- Moderate backup retention
- Enable detailed monitoring

### Production
- Enable all high availability features
- Long backup retention periods
- Enable deletion protection
- Comprehensive monitoring and alerting

### Cost Optimization
- Use t2.micro/t3.micro instances only
- Limit Auto Scaling Group size
- Monitor free tier usage
- Set up billing alerts

## Cost Monitoring Procedures

### Free Tier Usage Tracking

#### 1. Set Up Billing Alerts
```bash
# Create billing alarm for $5 threshold
aws cloudwatch put-metric-alarm \
  --alarm-name "BillingAlert-5USD" \
  --alarm-description "Alert when charges exceed $5" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 86400 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=Currency,Value=USD \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:billing-alerts

# Create billing alarm for $10 threshold
aws cloudwatch put-metric-alarm \
  --alarm-name "BillingAlert-10USD" \
  --alarm-description "Alert when charges exceed $10" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 86400 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=Currency,Value=USD \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:billing-alerts
```

#### 2. Monitor Free Tier Usage
```bash
# Check EC2 free tier usage
aws support describe-trusted-advisor-checks --language en --query 'checks[?name==`EC2 Reserved Instance Optimization`]'

# Monitor EBS usage
aws ec2 describe-volumes --query 'Volumes[*].[VolumeId,Size,State]' --output table

# Check ALB data processing
aws logs filter-log-events \
  --log-group-name /aws/applicationloadbalancer/app/dominoes-app-alb \
  --start-time $(date -d '1 month ago' +%s)000 \
  --query 'events[*].message' | grep -o '"received_bytes":[0-9]*' | awk -F: '{sum+=$2} END {print "Total bytes: " sum}'
```

#### 3. Daily Cost Monitoring Script
```bash
#!/bin/bash
# scripts/check-daily-costs.sh

# Get current month costs
CURRENT_MONTH=$(date +%Y-%m-01)
NEXT_MONTH=$(date -d "next month" +%Y-%m-01)

aws ce get-cost-and-usage \
  --time-period Start=$CURRENT_MONTH,End=$NEXT_MONTH \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE \
  --query 'ResultsByTime[0].Groups[*].[Keys[0],Metrics.BlendedCost.Amount]' \
  --output table

# Check free tier usage
python3 app/cost_optimizer.py --check-free-tier --alert-threshold 80
```

#### 4. Resource Usage Validation
```bash
# Validate instance types are free tier eligible
aws ec2 describe-instances \
  --query 'Reservations[*].Instances[*].[InstanceId,InstanceType,State.Name]' \
  --output table | grep -v "t2.micro\|t3.micro" && echo "WARNING: Non-free-tier instances found!"

# Check EBS volume sizes
aws ec2 describe-volumes \
  --query 'Volumes[*].[VolumeId,Size,VolumeType]' \
  --output table | awk '{if($2>30) print "WARNING: Volume " $1 " exceeds free tier limit: " $2 "GB"}'

# Validate RDS instance class
aws rds describe-db-instances \
  --query 'DBInstances[*].[DBInstanceIdentifier,DBInstanceClass,AllocatedStorage]' \
  --output table | grep -v "db.t3.micro" && echo "WARNING: Non-free-tier RDS instance found!"
```

### Cost Optimization Recommendations

#### 1. Instance Right-Sizing
```bash
# Check CPU utilization for right-sizing
aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --start-time $(date -d '7 days ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 3600 \
  --statistics Average,Maximum \
  --dimensions Name=AutoScalingGroupName,Value=dominoes-app-dev-asg

# Recommend instance type changes
python3 app/cost_optimizer.py --analyze-usage --recommend-sizing
```

#### 2. Storage Optimization
```bash
# Check EBS volume utilization
aws ec2 describe-volumes \
  --query 'Volumes[*].[VolumeId,Size,State,Attachments[0].InstanceId]' \
  --output table

# Identify unused volumes
aws ec2 describe-volumes \
  --filters Name=status,Values=available \
  --query 'Volumes[*].[VolumeId,Size,CreateTime]' \
  --output table
```

#### 3. Network Cost Optimization
```bash
# Monitor data transfer costs
aws logs filter-log-events \
  --log-group-name /aws/applicationloadbalancer/app/dominoes-app-alb \
  --start-time $(date -d '1 day ago' +%s)000 \
  --query 'events[*].message' | python3 -c "
import sys, json, re
total_bytes = 0
for line in sys.stdin:
    matches = re.findall(r'\"received_bytes\":(\d+)', line)
    total_bytes += sum(int(m) for m in matches)
print(f'Total data processed: {total_bytes/1024/1024:.2f} MB')
"
```

### Automated Cost Monitoring

#### 1. CloudWatch Custom Metrics
```bash
# Create custom metric for free tier usage
aws cloudwatch put-metric-data \
  --namespace "AWS/FreeTier" \
  --metric-data MetricName=EC2Usage,Value=75,Unit=Percent,Dimensions=Name=Service,Value=EC2

# Set up alarm for free tier usage
aws cloudwatch put-metric-alarm \
  --alarm-name "FreeTierUsage-EC2" \
  --alarm-description "Alert when EC2 free tier usage exceeds 80%" \
  --metric-name EC2Usage \
  --namespace AWS/FreeTier \
  --statistic Maximum \
  --period 3600 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:cost-alerts
```

#### 2. Daily Cost Report
```bash
# Create daily cost report script
cat > scripts/daily-cost-report.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y-%m-%d)
REPORT_FILE="cost-report-$DATE.json"

# Get yesterday's costs
aws ce get-cost-and-usage \
  --time-period Start=$(date -d 'yesterday' +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE > $REPORT_FILE

# Send email report if costs exceed threshold
TOTAL_COST=$(jq -r '.ResultsByTime[0].Total.BlendedCost.Amount' $REPORT_FILE)
if (( $(echo "$TOTAL_COST > 1.0" | bc -l) )); then
  aws sns publish \
    --topic-arn arn:aws:sns:us-east-1:123456789012:cost-alerts \
    --message "Daily cost alert: $TOTAL_COST USD" \
    --subject "AWS Cost Alert - $DATE"
fi
EOF

chmod +x scripts/daily-cost-report.sh
```

### Free Tier Compliance Checklist

#### EC2 Compliance
- [ ] Instance types: Only t2.micro or t3.micro
- [ ] Total instances: ≤ 750 hours/month across all instances
- [ ] EBS storage: ≤ 30GB total across all volumes
- [ ] Data transfer: ≤ 15GB/month outbound

#### RDS Compliance (if enabled)
- [ ] Instance class: db.t3.micro only
- [ ] Storage: ≤ 20GB allocated storage
- [ ] Backup storage: ≤ 20GB backup storage
- [ ] Runtime: ≤ 750 hours/month

#### Load Balancer Compliance
- [ ] ALB data processing: ≤ 15GB/month
- [ ] ALB hours: ≤ 750 hours/month
- [ ] Rule evaluations: ≤ 1M/month

#### Monitoring Compliance
- [ ] CloudWatch metrics: ≤ 10 custom metrics
- [ ] CloudWatch API requests: ≤ 1M/month
- [ ] CloudWatch logs: ≤ 5GB ingestion/month
- [ ] SNS notifications: ≤ 1M/month

## Security Considerations

1. **Parameter Files**: Don't commit sensitive data (passwords, keys)
2. **IAM Roles**: Use least privilege principle
3. **Security Groups**: Restrict access to necessary ports only
4. **Encryption**: Enable encryption for EBS and RDS
5. **Secrets**: Use AWS Secrets Manager for sensitive data

## Troubleshooting Guide

### Common Error Messages

1. **"Parameter validation failed"**
   - Run validation script to identify issues
   - Check parameter file syntax
   - Verify required parameters are present

2. **"Stack does not exist"**
   - Check stack name spelling
   - Verify AWS region
   - Ensure stack was created successfully

3. **"No updates are to be performed"**
   - No changes detected in template or parameters
   - This is normal and not an error

4. **"Insufficient permissions"**
   - Check IAM user/role permissions
   - Verify AWS profile configuration
   - Ensure CloudFormation permissions are granted

### Getting Help

1. Check CloudFormation events in AWS Console
2. Review CloudWatch logs for application issues
3. Use monitoring script for real-time status
4. Validate configuration with validation script
5. Check AWS service health dashboard

## Comprehensive Troubleshooting Guide

### Deployment Issues

#### 1. CloudFormation Stack Creation Failures

**Symptom**: Stack creation fails with resource creation errors
```bash
# Check stack events for detailed error messages
aws cloudformation describe-stack-events --stack-name dominoes-app-dev-vpc \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
  --output table

# Check stack resources status
aws cloudformation describe-stack-resources --stack-name dominoes-app-dev-vpc \
  --query 'StackResources[?ResourceStatus!=`CREATE_COMPLETE`]' \
  --output table
```

**Common Causes & Solutions**:
- **Insufficient IAM permissions**: Add required permissions to deployment role
- **Resource limits exceeded**: Check service quotas in AWS Console
- **Invalid parameter values**: Validate parameters with validation script
- **Dependency conflicts**: Review resource dependencies in template

#### 2. Parameter Validation Failures

**Symptom**: Validation script reports parameter errors
```bash
# Run validation with detailed output
python3 scripts/validate-config.py --verbose infrastructure/parameters/dev.json

# Check specific parameter issues
python3 scripts/validate-config.py --check-free-tier --strict infrastructure/parameters/dev.json
```

**Common Issues**:
- **Missing required parameters**: Add all required parameters to parameter file
- **Invalid instance types**: Use only t2.micro or t3.micro for free tier
- **Exceeding free tier limits**: Reduce instance counts or storage sizes
- **Invalid email format**: Ensure ALERT_EMAIL is valid email address

#### 3. Template Validation Errors

**Symptom**: CloudFormation template validation fails
```bash
# Validate all templates
for template in infrastructure/*.yaml; do
  echo "Validating $template"
  aws cloudformation validate-template --template-body file://$template
done

# Check template syntax
yamllint infrastructure/*.yaml
```

**Common Issues**:
- **YAML syntax errors**: Use yamllint to identify syntax issues
- **Invalid resource properties**: Check AWS documentation for correct properties
- **Circular dependencies**: Review Ref and DependsOn relationships
- **Invalid intrinsic functions**: Verify Fn:: function usage

### Application Issues

#### 1. Application Not Responding

**Symptom**: ALB health checks failing, application unreachable
```bash
# Check target group health
ALB_ARN=$(aws elbv2 describe-load-balancers --names dominoes-app-dev-alb --query 'LoadBalancers[0].LoadBalancerArn' --output text)
TG_ARN=$(aws elbv2 describe-target-groups --load-balancer-arn $ALB_ARN --query 'TargetGroups[0].TargetGroupArn' --output text)
aws elbv2 describe-target-health --target-group-arn $TG_ARN

# Check instance status
aws ec2 describe-instances --filters Name=tag:aws:autoscaling:groupName,Values=dominoes-app-dev-asg \
  --query 'Reservations[*].Instances[*].[InstanceId,State.Name,PublicIpAddress]' --output table

# Check application logs
aws logs tail /aws/ec2/dominoes-app --follow --since 1h
```

**Troubleshooting Steps**:
1. **Verify instance health**: Check EC2 instance status and system logs
2. **Check security groups**: Ensure ALB can reach instances on port 80
3. **Validate health check endpoint**: Test `/health` endpoint manually
4. **Review application logs**: Look for startup errors or crashes
5. **Check user data script**: Verify application installation and startup

#### 2. High Error Rates

**Symptom**: CloudWatch alarms triggering for high error rates
```bash
# Check ALB error metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name HTTPCode_Target_5XX_Count \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Sum \
  --dimensions Name=LoadBalancer,Value=app/dominoes-app-dev-alb/1234567890abcdef

# Check application error logs
aws logs filter-log-events \
  --log-group-name /aws/ec2/dominoes-app \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s)000
```

**Common Causes**:
- **Database connection issues**: Check RDS connectivity and credentials
- **Memory/CPU exhaustion**: Monitor instance resources
- **Application bugs**: Review application logs for exceptions
- **Dependency failures**: Check external service connectivity

#### 3. Database Connection Issues

**Symptom**: Application cannot connect to RDS database
```bash
# Check RDS instance status
aws rds describe-db-instances --db-instance-identifier dominoes-app-dev-db \
  --query 'DBInstances[0].[DBInstanceStatus,Endpoint.Address,Endpoint.Port]' --output table

# Test database connectivity from EC2
INSTANCE_ID=$(aws ec2 describe-instances --filters Name=tag:aws:autoscaling:groupName,Values=dominoes-app-dev-asg \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)
aws ssm start-session --target $INSTANCE_ID
# In session: telnet <rds-endpoint> 3306
```

**Troubleshooting Steps**:
1. **Check RDS status**: Ensure database is available and not in maintenance
2. **Verify security groups**: Ensure EC2 instances can reach RDS on port 3306
3. **Test connectivity**: Use telnet or mysql client to test connection
4. **Check credentials**: Verify database username/password in application config
5. **Review subnet groups**: Ensure RDS is in correct subnet group

### Auto Scaling Issues

#### 1. Instances Not Scaling

**Symptom**: Auto Scaling Group not launching/terminating instances
```bash
# Check scaling activities
aws autoscaling describe-scaling-activities --auto-scaling-group-name dominoes-app-dev-asg \
  --max-items 10 --query 'Activities[*].[ActivityId,StatusCode,StatusMessage,StartTime]' --output table

# Check scaling policies
aws autoscaling describe-policies --auto-scaling-group-name dominoes-app-dev-asg

# Check CloudWatch alarms
aws cloudwatch describe-alarms --alarm-names dominoes-app-dev-cpu-high dominoes-app-dev-cpu-low
```

**Common Issues**:
- **Insufficient capacity**: Check EC2 service limits and availability zones
- **Scaling policies not triggered**: Verify CloudWatch alarm thresholds
- **Cooldown periods**: Wait for cooldown period to expire
- **Launch template issues**: Check launch template configuration

#### 2. Unhealthy Instances

**Symptom**: Auto Scaling Group terminates instances frequently
```bash
# Check instance health status
aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names dominoes-app-dev-asg \
  --query 'AutoScalingGroups[0].Instances[*].[InstanceId,HealthStatus,LifecycleState]' --output table

# Check ELB health check configuration
aws elbv2 describe-target-groups --names dominoes-app-dev-tg \
  --query 'TargetGroups[0].[HealthCheckPath,HealthCheckIntervalSeconds,HealthyThresholdCount,UnhealthyThresholdCount]'
```

**Troubleshooting Steps**:
1. **Review health check settings**: Adjust thresholds and intervals if too aggressive
2. **Check application startup time**: Ensure health check grace period is sufficient
3. **Verify health endpoint**: Test `/health` endpoint returns 200 status
4. **Monitor instance logs**: Look for application startup issues

### Monitoring and Alerting Issues

#### 1. CloudWatch Alarms Not Triggering

**Symptom**: Expected alarms not firing despite metric thresholds being breached
```bash
# Check alarm configuration
aws cloudwatch describe-alarms --alarm-names dominoes-app-dev-cpu-high \
  --query 'MetricAlarms[0].[AlarmName,StateValue,StateReason,MetricName,Threshold]'

# Check metric data
aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --start-time $(date -d '2 hours ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average \
  --dimensions Name=AutoScalingGroupName,Value=dominoes-app-dev-asg
```

**Common Issues**:
- **Incorrect metric dimensions**: Verify dimension names and values
- **Insufficient data points**: Ensure enough data points for evaluation
- **Wrong comparison operator**: Check if using correct comparison (>, <, etc.)
- **Alarm state**: Check if alarm is in ALARM, OK, or INSUFFICIENT_DATA state

#### 2. SNS Notifications Not Received

**Symptom**: CloudWatch alarms trigger but no email notifications received
```bash
# Check SNS topic and subscriptions
aws sns list-subscriptions-by-topic --topic-arn arn:aws:sns:us-east-1:123456789012:dominoes-app-alerts

# Check SNS topic policy
aws sns get-topic-attributes --topic-arn arn:aws:sns:us-east-1:123456789012:dominoes-app-alerts

# Test SNS notification
aws sns publish --topic-arn arn:aws:sns:us-east-1:123456789012:dominoes-app-alerts \
  --message "Test notification" --subject "Test Alert"
```

**Troubleshooting Steps**:
1. **Verify subscription**: Ensure email subscription is confirmed
2. **Check spam folder**: SNS emails might be filtered as spam
3. **Test topic permissions**: Verify CloudWatch can publish to SNS topic
4. **Review topic policy**: Ensure proper permissions for CloudWatch service

### Cost and Billing Issues

#### 1. Unexpected Charges

**Symptom**: AWS bill higher than expected despite free tier usage
```bash
# Check current month costs by service
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-01),End=$(date -d "next month" +%Y-%m-01) \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE

# Check free tier usage
aws support describe-trusted-advisor-checks --language en | \
  jq '.checks[] | select(.name | contains("Free Tier"))'
```

**Common Causes**:
- **Data transfer charges**: Monitor ALB data processing and EC2 data transfer
- **EBS snapshot costs**: Check for automated snapshots
- **RDS backup storage**: Monitor backup storage usage
- **CloudWatch logs**: Check log ingestion and storage costs

#### 2. Free Tier Limit Exceeded

**Symptom**: Receiving free tier usage alerts
```bash
# Check resource usage against free tier limits
python3 app/cost_optimizer.py --check-free-tier --detailed

# Review instance hours
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics UsageQuantity \
  --group-by Type=DIMENSION,Key=USAGE_TYPE \
  --filter file://free-tier-filter.json
```

**Mitigation Steps**:
1. **Reduce instance count**: Scale down Auto Scaling Group minimum size
2. **Optimize storage**: Delete unused EBS volumes and snapshots
3. **Monitor data transfer**: Reduce unnecessary data transfer
4. **Schedule resources**: Stop non-production resources when not needed

### Network and Security Issues

#### 1. Security Group Misconfigurations

**Symptom**: Cannot access application or instances cannot communicate
```bash
# Check security group rules
aws ec2 describe-security-groups --group-names dominoes-app-dev-alb-sg dominoes-app-dev-ec2-sg \
  --query 'SecurityGroups[*].[GroupName,IpPermissions[*].[IpProtocol,FromPort,ToPort,IpRanges[*].CidrIp]]'

# Test connectivity
aws ec2 describe-instances --filters Name=tag:aws:autoscaling:groupName,Values=dominoes-app-dev-asg \
  --query 'Reservations[*].Instances[*].[InstanceId,SecurityGroups[*].GroupId]'
```

**Common Issues**:
- **Missing ingress rules**: Add required ports (80, 443, 3306)
- **Incorrect CIDR blocks**: Use appropriate IP ranges
- **Circular references**: Avoid security group circular dependencies
- **Egress restrictions**: Ensure outbound rules allow necessary traffic

#### 2. VPC and Subnet Issues

**Symptom**: Instances cannot reach internet or other AWS services
```bash
# Check VPC configuration
aws ec2 describe-vpcs --filters Name=tag:Name,Values=dominoes-app-dev-vpc

# Check route tables
aws ec2 describe-route-tables --filters Name=vpc-id,Values=vpc-12345678 \
  --query 'RouteTables[*].[RouteTableId,Routes[*].[DestinationCidrBlock,GatewayId]]'

# Check NAT Gateway status
aws ec2 describe-nat-gateways --filter Name=vpc-id,Values=vpc-12345678
```

**Troubleshooting Steps**:
1. **Verify internet gateway**: Ensure IGW is attached to VPC
2. **Check route tables**: Verify routes to IGW and NAT Gateway
3. **Validate subnets**: Ensure instances are in correct subnets
4. **Test NAT Gateway**: Verify private instances can reach internet

### Performance Issues

#### 1. High Response Times

**Symptom**: Application responding slowly, high latency metrics
```bash
# Check ALB response time metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name TargetResponseTime \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum \
  --dimensions Name=LoadBalancer,Value=app/dominoes-app-dev-alb/1234567890abcdef

# Check instance CPU and memory
aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum \
  --dimensions Name=AutoScalingGroupName,Value=dominoes-app-dev-asg
```

**Optimization Steps**:
1. **Scale up instances**: Increase Auto Scaling Group desired capacity
2. **Optimize application**: Profile and optimize slow code paths
3. **Database tuning**: Optimize database queries and connections
4. **Caching**: Implement application-level caching

#### 2. Memory Issues

**Symptom**: Instances running out of memory, application crashes
```bash
# Check memory metrics (requires CloudWatch agent)
aws cloudwatch get-metric-statistics \
  --namespace CWAgent \
  --metric-name mem_used_percent \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum \
  --dimensions Name=AutoScalingGroupName,Value=dominoes-app-dev-asg

# Check application logs for memory errors
aws logs filter-log-events \
  --log-group-name /aws/ec2/dominoes-app \
  --filter-pattern "OutOfMemory" \
  --start-time $(date -d '1 hour ago' +%s)000
```

**Solutions**:
1. **Optimize memory usage**: Profile application memory usage
2. **Increase instance size**: Consider t3.small if within budget
3. **Add swap space**: Configure swap file on instances
4. **Memory leak detection**: Use profiling tools to identify leaks

### Emergency Procedures

#### 1. Complete Service Outage

**Immediate Actions**:
```bash
# Check overall service health
aws elbv2 describe-load-balancers --names dominoes-app-dev-alb
aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names dominoes-app-dev-asg

# Force instance refresh
aws autoscaling start-instance-refresh --auto-scaling-group-name dominoes-app-dev-asg

# Scale up immediately
aws autoscaling set-desired-capacity --auto-scaling-group-name dominoes-app-dev-asg --desired-capacity 3
```

#### 2. Database Failover

**RDS Multi-AZ Failover**:
```bash
# Check RDS status
aws rds describe-db-instances --db-instance-identifier dominoes-app-dev-db

# Force failover (if needed)
aws rds reboot-db-instance --db-instance-identifier dominoes-app-dev-db --force-failover

# Monitor failover progress
aws rds describe-events --source-identifier dominoes-app-dev-db --source-type db-instance
```

#### 3. Rollback Procedures

**Stack Rollback**:
```bash
# Rollback specific stack
aws cloudformation cancel-update-stack --stack-name dominoes-app-dev-ec2

# Or continue rollback if stuck
aws cloudformation continue-update-rollback --stack-name dominoes-app-dev-ec2

# Complete rollback using script
./scripts/deploy.sh rollback dominoes-app-dev-ec2
```

This comprehensive troubleshooting guide covers the most common issues you might encounter when deploying and operating the AWS scalable web application. Always start with the most basic checks (service status, logs) before moving to more complex diagnostics.

## Examples

### Complete Development Deployment

```bash
# Set environment
export ALERT_EMAIL="dev@example.com"
export ENVIRONMENT="dev"
export AWS_REGION="us-east-1"

# Validate configuration
python3 scripts/validate-config.py infrastructure/parameters/dev.json

# Deploy application
./scripts/deploy.sh

# Monitor deployment
python3 scripts/monitor-deployment.py --project-name dominoes-app --environment dev
```

### Production Deployment with Custom Parameters

```bash
# Create custom parameter file
cp infrastructure/parameters/prod.json my-prod-params.json
# Edit my-prod-params.json as needed

# Validate custom parameters
python3 scripts/validate-config.py --strict my-prod-params.json

# Deploy with custom parameters
ENVIRONMENT=prod \
PARAMETER_FILE=my-prod-params.json \
ALERT_EMAIL="ops@example.com" \
./scripts/deploy.sh

# Get deployment summary
python3 scripts/monitor-deployment.py \
  --summary \
  --project-name dominoes-app \
  --environment prod
```

This deployment system provides comprehensive automation for deploying, monitoring, and managing the AWS scalable web application while maintaining free tier compliance and following best practices.