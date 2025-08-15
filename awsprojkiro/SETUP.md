# Setup Guide - AWS Scalable Web Application

This guide walks you through setting up your development environment and AWS account for deploying the scalable web application.

## Prerequisites Checklist

### AWS Account Requirements
- [ ] Active AWS account with root access
- [ ] Free tier eligibility (account less than 12 months old)
- [ ] Valid payment method attached (required even for free tier)
- [ ] Email address for CloudWatch alerts
- [ ] Basic understanding of AWS services (EC2, ALB, RDS, CloudFormation)

### Local Development Environment
- [ ] Python 3.9 or higher
- [ ] AWS CLI version 2.x
- [ ] Git for version control
- [ ] Text editor or IDE
- [ ] Terminal/command line access

### Optional Tools
- [ ] jq for JSON processing
- [ ] yamllint for YAML validation
- [ ] Docker (for local testing)
- [ ] Postman or curl for API testing

## Step 1: AWS Account Setup

### 1.1 Create AWS Account
If you don't have an AWS account:
1. Go to [aws.amazon.com](https://aws.amazon.com)
2. Click "Create an AWS Account"
3. Follow the registration process
4. Verify your email and phone number
5. Add a valid payment method

### 1.2 Enable Billing Alerts
```bash
# Enable billing alerts (one-time setup)
aws configure set region us-east-1
aws cloudwatch put-metric-alarm \
  --alarm-name "BillingAlert" \
  --alarm-description "Alert when charges exceed $10" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 86400 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=Currency,Value=USD
```

### 1.3 Create IAM User (Recommended)
Instead of using root credentials, create an IAM user:

1. **Create IAM User**:
   ```bash
   aws iam create-user --user-name dominoes-app-developer
   ```

2. **Attach Policies**:
   ```bash
   # For development (broad permissions)
   aws iam attach-user-policy --user-name dominoes-app-developer \
     --policy-arn arn:aws:iam::aws:policy/PowerUserAccess
   
   # For production (minimal permissions)
   aws iam attach-user-policy --user-name dominoes-app-developer \
     --policy-arn arn:aws:iam::aws:policy/CloudFormationFullAccess
   ```

3. **Create Access Keys**:
   ```bash
   aws iam create-access-key --user-name dominoes-app-developer
   ```

## Step 2: Local Environment Setup

### 2.1 Install Python
**Windows**:
```powershell
# Download from python.org or use chocolatey
choco install python

# Verify installation
python --version
pip --version
```

**macOS**:
```bash
# Using Homebrew
brew install python@3.9

# Verify installation
python3 --version
pip3 --version
```

**Linux (Ubuntu/Debian)**:
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv

# Verify installation
python3 --version
pip3 --version
```

### 2.2 Install AWS CLI
**Windows**:
```powershell
# Download MSI installer from AWS or use chocolatey
choco install awscli

# Verify installation
aws --version
```

**macOS**:
```bash
# Using Homebrew
brew install awscli

# Or download installer
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /
```

**Linux**:
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Verify installation
aws --version
```

### 2.3 Configure AWS CLI
```bash
# Configure with your credentials
aws configure

# You'll be prompted for:
# AWS Access Key ID: [Your access key]
# AWS Secret Access Key: [Your secret key]
# Default region name: us-east-1
# Default output format: json

# Verify configuration
aws sts get-caller-identity
```

### 2.4 Install Optional Tools
**jq (JSON processor)**:
```bash
# Windows (chocolatey)
choco install jq

# macOS
brew install jq

# Linux
sudo apt install jq
```

**yamllint (YAML validator)**:
```bash
pip install yamllint
```

## Step 3: Project Setup

### 3.1 Clone Repository
```bash
git clone <repository-url>
cd aws-scalable-web-app
```

### 3.2 Create Python Virtual Environment
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 3.3 Set Environment Variables
Create a `.env` file in the project root:
```bash
# .env file
export ALERT_EMAIL="your-email@example.com"
export ENVIRONMENT="dev"
export AWS_REGION="us-east-1"
export PROJECT_NAME="dominoes-app"
export FLASK_DEBUG="true"
```

Load environment variables:
```bash
# Load environment variables
source .env

# Or set them directly
export ALERT_EMAIL="your-email@example.com"
export ENVIRONMENT="dev"
```

### 3.4 Validate Setup
```bash
# Test AWS connectivity
aws sts get-caller-identity

# Test Python environment
python -c "import flask, boto3; print('Dependencies OK')"

# Validate configuration
python3 scripts/validate-config.py infrastructure/parameters/dev.json

# Run local tests
python -m pytest tests/test_app.py -v
```

## Step 4: AWS Service Limits Check

### 4.1 Check Current Limits
```bash
# Check VPC limits
aws ec2 describe-account-attributes --attribute-names supported-platforms

# Check EC2 limits
aws service-quotas get-service-quota --service-code ec2 --quota-code L-1216C47A

# Check RDS limits
aws service-quotas get-service-quota --service-code rds --quota-code L-7B6409FD
```

### 4.2 Request Limit Increases (if needed)
```bash
# Request EC2 instance limit increase
aws service-quotas request-service-quota-increase \
  --service-code ec2 \
  --quota-code L-1216C47A \
  --desired-value 10
```

## Step 5: Initial Deployment Test

### 5.1 Deploy Development Environment
```bash
# Set environment variables
export ALERT_EMAIL="your-email@example.com"
export ENVIRONMENT="dev"

# Run deployment
./scripts/deploy.sh

# Monitor deployment
python3 scripts/monitor-deployment.py --project-name dominoes-app --environment dev
```

### 5.2 Verify Deployment
```bash
# Check stack status
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE \
  --query 'StackSummaries[?contains(StackName, `dominoes-app-dev`)].[StackName,StackStatus]' --output table

# Get application URL
ALB_DNS=$(aws cloudformation describe-stacks --stack-name dominoes-app-dev-alb \
  --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerDNS`].OutputValue' --output text)
echo "Application URL: http://$ALB_DNS"

# Test application
curl -f http://$ALB_DNS/health
```

### 5.3 Cleanup Test Deployment
```bash
# Clean up test deployment to avoid charges
./scripts/deploy.sh cleanup

# Or manually delete stacks
aws cloudformation delete-stack --stack-name dominoes-app-dev-monitoring
aws cloudformation delete-stack --stack-name dominoes-app-dev-ec2
aws cloudformation delete-stack --stack-name dominoes-app-dev-alb
aws cloudformation delete-stack --stack-name dominoes-app-dev-vpc
```

## Step 6: Development Workflow Setup

### 6.1 IDE Configuration
**VS Code Extensions**:
- AWS Toolkit
- Python
- YAML
- CloudFormation Linter

**PyCharm Plugins**:
- AWS Toolkit
- CloudFormation
- YAML/Ansible support

### 6.2 Git Hooks Setup
```bash
# Create pre-commit hook
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
# Run tests before commit
python -m pytest tests/test_app.py
if [ $? -ne 0 ]; then
  echo "Tests failed. Commit aborted."
  exit 1
fi

# Validate CloudFormation templates
for template in infrastructure/*.yaml; do
  aws cloudformation validate-template --template-body file://$template
  if [ $? -ne 0 ]; then
    echo "Template validation failed: $template"
    exit 1
  fi
done
EOF

chmod +x .git/hooks/pre-commit
```

### 6.3 Local Development Server
```bash
# Run application locally
export FLASK_DEBUG=true
python app.py

# Access at http://localhost:5000
```

## Step 7: Monitoring and Alerting Setup

### 7.1 CloudWatch Dashboard
```bash
# Create custom dashboard
aws cloudwatch put-dashboard --dashboard-name dominoes-app-dev \
  --dashboard-body file://monitoring/dashboard-config.json
```

### 7.2 SNS Topic for Alerts
```bash
# Create SNS topic
aws sns create-topic --name dominoes-app-alerts

# Subscribe to email notifications
aws sns subscribe --topic-arn arn:aws:sns:us-east-1:123456789012:dominoes-app-alerts \
  --protocol email --notification-endpoint your-email@example.com

# Confirm subscription (check email)
```

### 7.3 Cost Monitoring
```bash
# Set up cost monitoring
python3 app/cost_optimizer.py --setup-monitoring --alert-email your-email@example.com

# Create billing alarms
aws cloudwatch put-metric-alarm \
  --alarm-name "BillingAlert-5USD" \
  --alarm-description "Alert when charges exceed $5" \
  --metric-name EstimatedCharges \
  --namespace AWS/Billing \
  --statistic Maximum \
  --period 86400 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=Currency,Value=USD
```

## Step 8: Security Configuration

### 8.1 IAM Roles and Policies
```bash
# Create EC2 instance role
aws iam create-role --role-name dominoes-app-ec2-role \
  --assume-role-policy-document file://iam/ec2-trust-policy.json

# Attach policies
aws iam attach-role-policy --role-name dominoes-app-ec2-role \
  --policy-arn arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy
```

### 8.2 Security Groups
Security groups are created automatically by CloudFormation templates, but you can review them:
```bash
# List security groups
aws ec2 describe-security-groups --filters Name=group-name,Values=dominoes-app-*
```

### 8.3 VPC Configuration
VPC and networking are handled by CloudFormation templates in `infrastructure/vpc-network.yaml`.

## Step 9: Testing Setup

### 9.1 Unit Tests
```bash
# Run unit tests
python -m pytest tests/test_app.py -v

# Run with coverage
pip install pytest-cov
python -m pytest tests/test_app.py --cov=app --cov-report=html
```

### 9.2 Integration Tests
```bash
# Run integration tests (requires deployed infrastructure)
python -m pytest tests/integration/ -v
```

### 9.3 Load Testing
```bash
# Install load testing tools
pip install locust

# Run load tests
python -m pytest tests/load_testing/test_auto_scaling.py -v
```

## Step 10: Documentation and Learning

### 10.1 AWS Documentation
- [AWS Free Tier](https://aws.amazon.com/free/)
- [CloudFormation User Guide](https://docs.aws.amazon.com/cloudformation/)
- [EC2 User Guide](https://docs.aws.amazon.com/ec2/)
- [Application Load Balancer Guide](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/)

### 10.2 Project Documentation
- `README.md` - Project overview and quick start
- `DEPLOYMENT.md` - Detailed deployment procedures
- `TROUBLESHOOTING.md` - Common issues and solutions
- `architecture/` - Architecture diagrams and design docs

## Troubleshooting Setup Issues

### Common Setup Problems

1. **AWS CLI not configured**:
   ```bash
   aws configure list
   # If empty, run: aws configure
   ```

2. **Python version issues**:
   ```bash
   python --version
   # Should be 3.9 or higher
   ```

3. **Permission denied errors**:
   ```bash
   # Check IAM permissions
   aws iam get-user-policy --user-name your-username --policy-name your-policy
   ```

4. **Region mismatch**:
   ```bash
   # Ensure consistent region usage
   aws configure get region
   echo $AWS_REGION
   ```

### Getting Help

1. **AWS Support**: For account-specific issues
2. **AWS Forums**: Community support
3. **Project Issues**: GitHub issues for project-specific problems
4. **Documentation**: Refer to AWS documentation for service-specific help

## Next Steps

After completing the setup:

1. **Deploy Development Environment**: Follow the deployment guide
2. **Explore the Application**: Test the dominoes game functionality
3. **Monitor Costs**: Set up billing alerts and monitor usage
4. **Customize Configuration**: Modify parameters for your needs
5. **Learn and Experiment**: Try different configurations and features

## Security Best Practices

1. **Never commit credentials**: Use environment variables or AWS profiles
2. **Use IAM roles**: Avoid hardcoded access keys in applications
3. **Enable MFA**: Multi-factor authentication for AWS console access
4. **Regular key rotation**: Rotate access keys periodically
5. **Least privilege**: Grant minimum required permissions

## Cost Management Tips

1. **Monitor daily**: Check costs daily during development
2. **Set up alerts**: Configure billing alarms
3. **Use free tier**: Stay within free tier limits
4. **Clean up resources**: Delete unused resources promptly
5. **Schedule resources**: Stop non-production resources when not needed

This setup guide should get you up and running with the AWS scalable web application. Follow each step carefully and refer to the troubleshooting section if you encounter issues.