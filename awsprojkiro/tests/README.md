# Comprehensive Testing Suite

This directory contains a comprehensive testing suite for the AWS scalable web application. The test suite validates all aspects of the infrastructure, application, and security configuration.

## Test Categories

### 1. Integration Tests (`integration/`)
- **Load Balancer Integration**: Tests ALB health checks, traffic distribution, and session stickiness
- **Application Endpoints**: Validates that all application endpoints are accessible through the load balancer
- **Target Health**: Monitors target group health and failover behavior

### 2. Load Testing (`load_testing/`)
- **Auto Scaling Validation**: Tests that ASG scales up and down based on CPU utilization
- **Performance Under Load**: Validates application performance during scaling events
- **Scaling Policy Configuration**: Verifies CloudWatch alarms and scaling policies

### 3. Infrastructure Tests (`infrastructure/`)
- **CloudFormation Validation**: Validates all CloudFormation templates using AWS API
- **Resource Dependencies**: Checks that resource references are correct
- **Free Tier Compliance**: Ensures templates comply with AWS free tier limits
- **Security Best Practices**: Validates security configurations in templates

### 4. Security Tests (`security/`)
- **Security Group Rules**: Validates ingress/egress rules follow least privilege
- **IAM Role Permissions**: Checks that IAM roles have minimal required permissions
- **Network ACL Configuration**: Validates network-level security controls
- **Encryption Configuration**: Verifies encryption in transit and at rest

## Quick Start

### 1. Validate Test Environment
```bash
python tests/validate_tests.py
```

### 2. Set Up Test Environment (Auto-discover AWS resources)
```bash
python tests/setup_test_environment.py
```

### 3. Run All Tests
```bash
python tests/run_comprehensive_tests.py
```

### 4. Run Specific Test Suite
```bash
# Integration tests only
python tests/run_comprehensive_tests.py --suite integration

# Load tests only
python tests/run_comprehensive_tests.py --suite load

# Infrastructure tests only
python tests/run_comprehensive_tests.py --suite infrastructure

# Security tests only
python tests/run_comprehensive_tests.py --suite security
```

### 5. Skip AWS Tests (for local development)
```bash
python tests/run_comprehensive_tests.py --skip-aws
```

## Environment Configuration

The test suite uses environment variables for configuration. You can set these manually or use the setup script to auto-discover them.

### Required Environment Variables
- `AWS_REGION`: AWS region (default: us-east-1)

### Optional Environment Variables (for AWS tests)
- `VPC_ID`: VPC ID where resources are deployed
- `ASG_NAME`: Auto Scaling Group name
- `ALB_ARN`: Application Load Balancer ARN
- `ALB_DNS_NAME`: ALB DNS name for HTTP requests
- `TARGET_GROUP_ARN`: Target Group ARN

### Test Configuration Variables
- `TEST_TIMEOUT`: Test timeout in seconds (default: 300)
- `LOAD_TEST_DURATION`: Load test duration in seconds (default: 300)
- `REQUESTS_PER_SECOND`: Load test request rate (default: 10)
- `SKIP_AWS_TESTS`: Skip tests requiring AWS credentials (default: false)

## Manual Environment Setup

If auto-discovery doesn't work, you can manually set environment variables:

```bash
export AWS_REGION=us-east-1
export VPC_ID=vpc-xxxxxxxxx
export ASG_NAME=dominoes-app-asg
export ALB_ARN=arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/dominoes-app-alb/xxxxxxxxx
export ALB_DNS_NAME=dominoes-app-alb-xxxxxxxxx.us-east-1.elb.amazonaws.com
export TARGET_GROUP_ARN=arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/dominoes-app-tg/xxxxxxxxx
```

## Test Files

### Integration Tests
- `integration/test_load_balancer.py`: Load balancer and traffic distribution tests

### Load Testing
- `load_testing/test_auto_scaling.py`: Auto scaling behavior validation

### Infrastructure Tests
- `infrastructure/test_cloudformation_validation.py`: CloudFormation template validation

### Security Tests
- `security/test_security_configuration.py`: Security configuration validation

### Utilities
- `test_config.py`: Test configuration management
- `setup_test_environment.py`: Environment setup and resource discovery
- `run_comprehensive_tests.py`: Main test runner
- `validate_tests.py`: Test suite validation

## Test Requirements

### Python Dependencies
```bash
pip install boto3 botocore requests pyyaml
```

### AWS Permissions
The test suite requires the following AWS permissions:
- `ec2:Describe*`
- `elasticloadbalancing:Describe*`
- `autoscaling:Describe*`
- `cloudwatch:GetMetricStatistics`
- `cloudwatch:DescribeAlarms`
- `iam:GetRole`
- `iam:GetPolicy`
- `iam:ListAttachedRolePolicies`
- `iam:ListRolePolicies`
- `cloudformation:ValidateTemplate`
- `cloudformation:DescribeStacks`
- `rds:DescribeDBInstances` (if RDS is deployed)

## Test Execution Flow

1. **Environment Validation**: Checks AWS credentials and configuration
2. **Resource Discovery**: Finds deployed AWS resources
3. **Integration Tests**: Validates load balancer and application endpoints
4. **Load Tests**: Generates load and validates auto scaling
5. **Infrastructure Tests**: Validates CloudFormation templates
6. **Security Tests**: Validates security configurations
7. **Report Generation**: Provides comprehensive test results

## Troubleshooting

### Common Issues

1. **AWS Credentials Not Found**
   - Ensure AWS credentials are configured (`aws configure`)
   - Or use IAM roles if running on EC2

2. **Resources Not Found**
   - Run the setup script: `python tests/setup_test_environment.py`
   - Or manually set environment variables

3. **Tests Timing Out**
   - Increase `TEST_TIMEOUT` environment variable
   - Check that AWS resources are healthy

4. **Load Tests Failing**
   - Ensure Auto Scaling Group has proper scaling policies
   - Check CloudWatch alarms are configured
   - Verify instances can handle the load

### Debug Mode
Run tests with verbose output:
```bash
python tests/run_comprehensive_tests.py --verbose
```

### Skip Problematic Tests
Skip AWS tests if credentials are not available:
```bash
python tests/run_comprehensive_tests.py --skip-aws
```

## Contributing

When adding new tests:

1. Follow the existing test structure
2. Add proper docstrings and comments
3. Include error handling for AWS API calls
4. Use the test configuration system
5. Add tests to the appropriate category
6. Update this README if needed

## Test Coverage

The test suite covers:
- ✅ Load balancer health checks and traffic distribution
- ✅ Auto scaling behavior under load
- ✅ CloudFormation template validation
- ✅ Security group and IAM role configuration
- ✅ Network security controls
- ✅ Free tier compliance
- ✅ Infrastructure best practices
- ✅ Application endpoint availability
- ✅ Database security (if RDS deployed)
- ✅ Encryption configuration

This comprehensive test suite ensures that the AWS scalable web application meets all requirements for reliability, security, and cost optimization.