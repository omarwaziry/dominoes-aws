# Troubleshooting Guide - AWS Scalable Web Application

This guide provides solutions to common issues encountered when deploying and operating the AWS scalable web application.

## Quick Diagnostic Commands

### System Health Check
```bash
# Run comprehensive health check
python3 scripts/monitor-deployment.py --project-name dominoes-app --environment dev --health-check

# Check all stack statuses
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query 'StackSummaries[?contains(StackName, `dominoes-app-dev`)].[StackName,StackStatus]' --output table

# Validate application endpoints
curl -f http://$(aws cloudformation describe-stacks --stack-name dominoes-app-dev-alb \
  --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerDNS`].OutputValue' --output text)/health
```

### Resource Validation
```bash
# Check free tier compliance
python3 scripts/validate-config.py --check-free-tier infrastructure/parameters/dev.json

# Validate all CloudFormation templates
for template in infrastructure/*.yaml; do
  echo "Validating $template"
  aws cloudformation validate-template --template-body file://$template || echo "FAILED: $template"
done

# Check current costs
python3 app/cost_optimizer.py --check-costs --alert-threshold 5.00
```

## Common Error Patterns

### 1. "Stack does not exist" Error

**Error Message**: `An error occurred (ValidationError) when calling the DescribeStacks operation: Stack with id dominoes-app-dev-vpc does not exist`

**Cause**: Stack was never created or was deleted

**Solution**:
```bash
# Check if stack exists in different region
aws cloudformation list-stacks --region us-west-2 --query 'StackSummaries[?contains(StackName, `dominoes-app`)]'

# Deploy missing stack
ENVIRONMENT=dev ./scripts/deploy.sh

# Or deploy specific stack
python3 infrastructure/deploy.py deploy --project-name dominoes-app --environment dev --stack-type vpc
```

### 2. "Parameter validation failed" Error

**Error Message**: `Parameter validation failed: Missing required parameter: AlertEmail`

**Cause**: Required parameters not set or invalid values

**Solution**:
```bash
# Set required environment variables
export ALERT_EMAIL="your-email@example.com"
export ENVIRONMENT="dev"

# Validate parameter file
python3 scripts/validate-config.py infrastructure/parameters/dev.json

# Fix parameter file and redeploy
./scripts/deploy.sh
```

### 3. "Insufficient permissions" Error

**Error Message**: `User: arn:aws:iam::123456789012:user/developer is not authorized to perform: cloudformation:CreateStack`

**Cause**: IAM user lacks required permissions

**Solution**:
```bash
# Check current permissions
aws sts get-caller-identity
aws iam get-user-policy --user-name developer --policy-name CloudFormationAccess

# Attach required policy (admin should do this)
aws iam attach-user-policy --user-name developer --policy-arn arn:aws:iam::aws:policy/PowerUserAccess
```

### 4. "Resource limit exceeded" Error

**Error Message**: `The maximum number of VPCs has been reached`

**Cause**: AWS service limits exceeded

**Solution**:
```bash
# Check current VPC usage
aws ec2 describe-vpcs --query 'length(Vpcs)'

# Request limit increase or clean up unused resources
aws ec2 describe-vpcs --query 'Vpcs[?State==`available`].[VpcId,Tags[?Key==`Name`].Value|[0]]' --output table

# Delete unused VPCs (be careful!)
aws ec2 delete-vpc --vpc-id vpc-unused123
```

## Application-Specific Issues

### 1. Health Check Failures

**Symptom**: ALB shows all targets as unhealthy

**Diagnosis**:
```bash
# Check target health
TG_ARN=$(aws elbv2 describe-target-groups --names dominoes-app-dev-tg --query 'TargetGroups[0].TargetGroupArn' --output text)
aws elbv2 describe-target-health --target-group-arn $TG_ARN

# Check health endpoint directly
INSTANCE_IP=$(aws ec2 describe-instances --filters Name=tag:aws:autoscaling:groupName,Values=dominoes-app-dev-asg \
  --query 'Reservations[0].Instances[0].PrivateIpAddress' --output text)
curl -v http://$INSTANCE_IP/health
```

**Solutions**:
1. **Fix health endpoint**: Ensure `/health` returns HTTP 200
2. **Adjust health check settings**: Increase timeout or reduce frequency
3. **Check security groups**: Ensure ALB can reach instances on port 80
4. **Review application logs**: Look for startup errors

### 2. Database Connection Issues

**Symptom**: Application logs show database connection errors

**Diagnosis**:
```bash
# Check RDS status
aws rds describe-db-instances --db-instance-identifier dominoes-app-dev-db \
  --query 'DBInstances[0].[DBInstanceStatus,Endpoint.Address]'

# Test connectivity from EC2
INSTANCE_ID=$(aws ec2 describe-instances --filters Name=tag:aws:autoscaling:groupName,Values=dominoes-app-dev-asg \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)
aws ssm start-session --target $INSTANCE_ID
# In session: telnet dominoes-app-dev-db.region.rds.amazonaws.com 3306
```

**Solutions**:
1. **Check RDS security group**: Allow port 3306 from EC2 security group
2. **Verify database credentials**: Check environment variables in application
3. **Test manual connection**: Use mysql client to test connectivity
4. **Check subnet groups**: Ensure RDS is in correct subnets

### 3. Auto Scaling Not Working

**Symptom**: Instances not scaling up/down despite CPU thresholds

**Diagnosis**:
```bash
# Check scaling activities
aws autoscaling describe-scaling-activities --auto-scaling-group-name dominoes-app-dev-asg --max-items 5

# Check CloudWatch alarms
aws cloudwatch describe-alarms --alarm-names dominoes-app-dev-cpu-high dominoes-app-dev-cpu-low

# Check current CPU metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average \
  --dimensions Name=AutoScalingGroupName,Value=dominoes-app-dev-asg
```

**Solutions**:
1. **Check alarm state**: Ensure alarms are in ALARM state when thresholds are breached
2. **Verify scaling policies**: Check if policies are attached to ASG
3. **Review cooldown periods**: Wait for cooldown to expire
4. **Test manual scaling**: Manually change desired capacity to test ASG

## Infrastructure Issues

### 1. CloudFormation Stack Stuck

**Symptom**: Stack stuck in CREATE_IN_PROGRESS or UPDATE_IN_PROGRESS

**Diagnosis**:
```bash
# Check stack events
aws cloudformation describe-stack-events --stack-name dominoes-app-dev-vpc \
  --query 'StackEvents[?ResourceStatus==`CREATE_IN_PROGRESS` || ResourceStatus==`UPDATE_IN_PROGRESS`]' \
  --output table

# Check for failed resources
aws cloudformation describe-stack-events --stack-name dominoes-app-dev-vpc \
  --query 'StackEvents[?contains(ResourceStatus, `FAILED`)].[LogicalResourceId,ResourceStatusReason]' \
  --output table
```

**Solutions**:
1. **Wait for timeout**: CloudFormation will eventually timeout and rollback
2. **Cancel update**: `aws cloudformation cancel-update-stack --stack-name dominoes-app-dev-vpc`
3. **Continue rollback**: `aws cloudformation continue-update-rollback --stack-name dominoes-app-dev-vpc`
4. **Delete and recreate**: Last resort - delete stack and redeploy

### 2. Security Group Circular Dependencies

**Symptom**: CloudFormation fails with circular dependency error

**Error**: `Circular dependency between resources: [SecurityGroupA, SecurityGroupB]`

**Solution**:
```bash
# Check security group references in templates
grep -n "Ref.*SecurityGroup" infrastructure/*.yaml

# Fix by using separate ingress rules
# Instead of referencing security groups in each other, create separate ingress rules
```

**Template Fix**:
```yaml
# Instead of this (circular):
ALBSecurityGroup:
  Properties:
    SecurityGroupIngress:
      - SourceSecurityGroupId: !Ref EC2SecurityGroup

EC2SecurityGroup:
  Properties:
    SecurityGroupIngress:
      - SourceSecurityGroupId: !Ref ALBSecurityGroup

# Use this (separate ingress rules):
ALBToEC2Ingress:
  Type: AWS::EC2::SecurityGroupIngress
  Properties:
    GroupId: !Ref EC2SecurityGroup
    SourceSecurityGroupId: !Ref ALBSecurityGroup
```

### 3. NAT Gateway Costs

**Symptom**: Unexpected NAT Gateway charges

**Diagnosis**:
```bash
# Check NAT Gateway usage
aws ec2 describe-nat-gateways --filter Name=state,Values=available \
  --query 'NatGateways[*].[NatGatewayId,State,CreateTime]' --output table

# Check data processing charges
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=USAGE_TYPE \
  --filter '{"Dimensions":{"Key":"SERVICE","Values":["Amazon Elastic Compute Cloud - Compute"]}}'
```

**Solutions**:
1. **Use VPC endpoints**: For S3 and other AWS services
2. **Minimize outbound traffic**: Reduce unnecessary internet access
3. **Consider single NAT Gateway**: Use one NAT Gateway for dev environment
4. **Schedule resources**: Stop NAT Gateway when not needed

## Cost and Billing Issues

### 1. Unexpected Free Tier Charges

**Symptom**: Charges appearing despite using free tier resources

**Diagnosis**:
```bash
# Check free tier usage
python3 app/cost_optimizer.py --check-free-tier --detailed

# Review current month costs
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=DIMENSION,Key=SERVICE

# Check specific usage types
aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-01),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics UsageQuantity \
  --group-by Type=DIMENSION,Key=USAGE_TYPE
```

**Common Causes**:
1. **Data transfer charges**: ALB data processing or EC2 data transfer
2. **EBS snapshots**: Automated snapshots beyond free tier
3. **CloudWatch logs**: Log ingestion and storage costs
4. **Multiple regions**: Resources in non-free-tier regions

### 2. Free Tier Limits Exceeded

**Symptom**: Free tier usage alerts or unexpected charges

**Solutions**:
```bash
# Scale down resources
aws autoscaling update-auto-scaling-group --auto-scaling-group-name dominoes-app-dev-asg \
  --min-size 1 --max-size 2 --desired-capacity 1

# Delete unused resources
aws ec2 describe-volumes --filters Name=status,Values=available \
  --query 'Volumes[*].[VolumeId,Size,CreateTime]' --output table
# Delete unused volumes: aws ec2 delete-volume --volume-id vol-12345678

# Stop non-essential services
aws rds stop-db-instance --db-instance-identifier dominoes-app-dev-db
```

## Performance Issues

### 1. High Response Times

**Symptom**: Application responding slowly

**Diagnosis**:
```bash
# Check ALB response times
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name TargetResponseTime \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum \
  --dimensions Name=LoadBalancer,Value=app/dominoes-app-dev-alb/1234567890abcdef

# Check instance CPU
aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --start-time $(date -d '1 hour ago' --iso-8601) \
  --end-time $(date --iso-8601) \
  --period 300 \
  --statistics Average,Maximum \
  --dimensions Name=AutoScalingGroupName,Value=dominoes-app-dev-asg
```

**Solutions**:
1. **Scale up**: Increase desired capacity temporarily
2. **Optimize application**: Profile slow endpoints
3. **Database optimization**: Check slow queries
4. **Add caching**: Implement application-level caching

### 2. Memory Issues

**Symptom**: Instances running out of memory

**Solutions**:
```bash
# Add swap space (in user data script)
#!/bin/bash
dd if=/dev/zero of=/swapfile bs=1M count=1024
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile swap swap defaults 0 0' >> /etc/fstab

# Monitor memory usage
# Install CloudWatch agent for memory metrics
```

## Emergency Procedures

### 1. Complete Service Outage

**Immediate Response**:
```bash
# Check service status
aws elbv2 describe-load-balancers --names dominoes-app-dev-alb
aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names dominoes-app-dev-asg

# Scale up immediately
aws autoscaling set-desired-capacity --auto-scaling-group-name dominoes-app-dev-asg --desired-capacity 3

# Force instance refresh
aws autoscaling start-instance-refresh --auto-scaling-group-name dominoes-app-dev-asg

# Check for AWS service issues
curl -s https://status.aws.amazon.com/ | grep -i "service is operating normally"
```

### 2. Database Emergency

**RDS Issues**:
```bash
# Check RDS status
aws rds describe-db-instances --db-instance-identifier dominoes-app-dev-db

# Force failover (Multi-AZ)
aws rds reboot-db-instance --db-instance-identifier dominoes-app-dev-db --force-failover

# Create manual snapshot
aws rds create-db-snapshot --db-instance-identifier dominoes-app-dev-db \
  --db-snapshot-identifier dominoes-app-emergency-$(date +%Y%m%d-%H%M%S)
```

### 3. Security Incident

**Suspected Compromise**:
```bash
# Immediately isolate instances
aws ec2 modify-instance-attribute --instance-id i-1234567890abcdef0 \
  --groups sg-emergency-isolation

# Stop all instances
aws autoscaling update-auto-scaling-group --auto-scaling-group-name dominoes-app-dev-asg \
  --min-size 0 --max-size 0 --desired-capacity 0

# Review CloudTrail logs
aws logs filter-log-events --log-group-name CloudTrail/dominoes-app \
  --start-time $(date -d '24 hours ago' +%s)000 \
  --filter-pattern "{ $.errorCode = \"*\" }"
```

## Prevention and Monitoring

### 1. Proactive Monitoring Setup

```bash
# Set up comprehensive monitoring
python3 scripts/setup-monitoring.py --project-name dominoes-app --environment dev

# Create custom dashboards
aws cloudwatch put-dashboard --dashboard-name dominoes-app-dev \
  --dashboard-body file://monitoring/dashboard-config.json

# Set up log aggregation
aws logs create-log-group --log-group-name /aws/ec2/dominoes-app
```

### 2. Automated Health Checks

```bash
# Create health check script
cat > scripts/health-check.sh << 'EOF'
#!/bin/bash
# Comprehensive health check
ALB_DNS=$(aws cloudformation describe-stacks --stack-name dominoes-app-dev-alb \
  --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerDNS`].OutputValue' --output text)

# Test application endpoint
if curl -f -s http://$ALB_DNS/health > /dev/null; then
  echo "✓ Application healthy"
else
  echo "✗ Application unhealthy"
  exit 1
fi

# Check database connectivity
if curl -f -s http://$ALB_DNS/db-health > /dev/null; then
  echo "✓ Database healthy"
else
  echo "✗ Database unhealthy"
  exit 1
fi
EOF

chmod +x scripts/health-check.sh

# Schedule health checks
echo "*/5 * * * * /path/to/scripts/health-check.sh" | crontab -
```

### 3. Cost Monitoring Automation

```bash
# Set up daily cost monitoring
cat > scripts/daily-cost-check.sh << 'EOF'
#!/bin/bash
COST=$(aws ce get-cost-and-usage \
  --time-period Start=$(date +%Y-%m-%d),End=$(date -d "1 day" +%Y-%m-%d) \
  --granularity DAILY \
  --metrics BlendedCost \
  --query 'ResultsByTime[0].Total.BlendedCost.Amount' --output text)

if (( $(echo "$COST > 1.0" | bc -l) )); then
  aws sns publish --topic-arn arn:aws:sns:us-east-1:123456789012:cost-alerts \
    --message "Daily cost exceeded $1: $COST USD" \
    --subject "Cost Alert - $(date +%Y-%m-%d)"
fi
EOF

chmod +x scripts/daily-cost-check.sh
```

## Getting Additional Help

### 1. AWS Support Resources
- **AWS Support Center**: For account-specific issues
- **AWS Forums**: Community support and discussions
- **AWS Documentation**: Comprehensive service documentation
- **AWS Status Page**: Check for service outages

### 2. Debugging Tools
- **AWS CLI**: Command-line interface for all AWS services
- **CloudFormation Console**: Visual stack management
- **CloudWatch Console**: Metrics and log analysis
- **AWS X-Ray**: Application performance monitoring

### 3. Log Analysis
```bash
# Centralized log analysis
aws logs start-query --log-group-name /aws/ec2/dominoes-app \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc'

# Get query results
aws logs get-query-results --query-id <query-id>
```

This troubleshooting guide should help you quickly identify and resolve common issues with the AWS scalable web application deployment.