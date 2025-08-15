# AWS Scalable Web Application

A highly available, auto-scaling Python web application deployed on AWS infrastructure, demonstrating enterprise-grade cloud architecture patterns while staying within AWS free tier limits.

## Overview

This project showcases a complete AWS deployment featuring:
- **High Availability**: Multi-AZ deployment with Application Load Balancer
- **Auto Scaling**: Automatic scaling based on CPU utilization
- **Cost Optimization**: Free tier compliant with cost monitoring
- **Infrastructure as Code**: CloudFormation templates for reproducible deployments
- **Comprehensive Monitoring**: CloudWatch metrics and SNS alerting
- **Security Best Practices**: IAM roles, security groups, and network isolation

## Architecture


For detailed architecture diagrams including network topology, security layers, auto scaling, monitoring, and deployment flows, see **(ARCHITECTURE.png)**.

### Key Components

- **Application Load Balancer (ALB)**: Distributes traffic across healthy instances
- **Auto Scaling Group**: Maintains 2-3 instances based on demand
- **EC2 Instances**: t2.micro instances running Python Flask application
- **CloudWatch**: Monitoring and alerting for all components
- **Optional RDS**: MySQL database with Multi-AZ deployment
- **VPC**: Custom networking with public/private subnets

## Features

### Web Application
- **Dominoes Game**: Interactive web-based dominoes game with AI opponent
- **Health Monitoring**: Comprehensive health check endpoints
- **Metrics Collection**: Application performance metrics
- **Database Integration**: Optional persistent storage with RDS

### Infrastructure
- **Auto Scaling**: CPU-based scaling (scale up >70%, scale down <30%)
- **High Availability**: Multi-AZ deployment across 2 availability zones
- **Load Balancing**: Intelligent traffic distribution with health checks
- **Cost Monitoring**: Real-time cost tracking and free tier compliance
- **Security**: Network isolation, IAM roles, and security groups

## Prerequisites

### AWS Account Setup
1. **AWS Account**: Active AWS account with free tier eligibility
2. **AWS CLI**: Installed and configured with appropriate permissions
3. **IAM Permissions**: CloudFormation, EC2, RDS, ALB, Auto Scaling, CloudWatch, SNS

### Local Development
1. **Python 3.9+**: For local development and testing
2. **AWS CLI**: Version 2.x recommended
3. **Git**: For version control
4. **jq**: For JSON processing (optional but recommended)

### Required AWS Permissions
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:*",
        "ec2:*",
        "elasticloadbalancing:*",
        "autoscaling:*",
        "rds:*",
        "cloudwatch:*",
        "sns:*",
        "iam:*",
        "s3:*"
      ],
      "Resource": "*"
    }
  ]
}
```

## Quick Start

### 1. Clone and Setup
```bash
git clone <repository-url>
cd aws-scalable-web-app
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
export ALERT_EMAIL="your-email@example.com"
export ENVIRONMENT="dev"
export AWS_REGION="us-east-1"
```

### 3. Deploy Infrastructure
```bash
# Deploy complete stack
./scripts/deploy.sh

# Monitor deployment progress
python3 scripts/monitor-deployment.py --project-name dominoes-app --environment dev
```

### 4. Access Application
Once deployed, find your ALB DNS name in the CloudFormation outputs:
```bash
aws cloudformation describe-stacks --stack-name dominoes-app-dev-alb --query 'Stacks[0].Outputs'
```

## Local Development

### Run Locally
```bash
# Install dependencies
pip install -r requirements.txt

# Run Flask application
python app.py

# Access at http://localhost:5000
```

### Run Tests
```bash
# Unit tests
python -m pytest tests/test_app.py

# Integration tests
python -m pytest tests/integration/

# Load tests
python -m pytest tests/load_testing/

# Infrastructure tests
python -m pytest tests/infrastructure/
```

## Project Structure

```
├── app/                          # Python Flask application
│   ├── main.py                   # Main application entry point
│   ├── config.py                 # Configuration management
│   ├── models.py                 # Database models
│   ├── dominoes_game.py          # Game logic
│   ├── monitoring.py             # Health checks and metrics
│   └── middleware.py             # Request/response middleware
├── infrastructure/               # CloudFormation templates
│   ├── vpc-network.yaml          # VPC and networking
│   ├── alb.yaml                  # Application Load Balancer
│   ├── ec2-autoscaling.yaml      # EC2 and Auto Scaling
│   ├── rds.yaml                  # RDS database (optional)
│   ├── monitoring.yaml           # CloudWatch and SNS
│   ├── cost-monitoring.yaml      # Cost tracking and alerts
│   └── parameters/               # Environment-specific parameters
├── scripts/                      # Deployment and utility scripts
│   ├── deploy.sh                 # Main deployment script
│   ├── package-app.sh            # Application packaging
│   ├── validate-config.py        # Configuration validation
│   └── monitor-deployment.py     # Deployment monitoring
├── tests/                        # Comprehensive test suite
│   ├── integration/              # Integration tests
│   ├── load_testing/             # Load and performance tests
│   ├── infrastructure/           # Infrastructure tests
│   └── security/                 # Security validation tests
├── static/                       # Web assets (CSS, JavaScript)
├── templates/                    # HTML templates
└── requirements.txt              # Python dependencies
```

## Configuration

### Environment Variables
| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ALERT_EMAIL` | Email for CloudWatch alerts | - | Yes |
| `ENVIRONMENT` | Deployment environment | dev | No |
| `AWS_REGION` | AWS region | us-east-1 | No |
| `PROJECT_NAME` | Project identifier | dominoes-app | No |

### Parameter Files
Environment-specific configurations in `infrastructure/parameters/`:
- `dev.json`: Development environment (minimal resources)
- `staging.json`: Staging environment (production-like)
- `prod.json`: Production environment (full features)

## Deployment

### Development Environment
```bash
# Quick development deployment
ENVIRONMENT=dev ALERT_EMAIL="dev@example.com" ./scripts/deploy.sh
```

### Production Environment
```bash
# Production deployment with all features
ENVIRONMENT=prod ALERT_EMAIL="ops@example.com" ./scripts/deploy.sh
```

### Custom Deployment
```bash
# Deploy with custom parameters
PARAMETER_FILE=my-custom-params.json ./scripts/deploy.sh
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions.

## Documentation

- **[SETUP.md](SETUP.md)**: Complete setup guide and prerequisites
- **[DEPLOYMENT.md](DEPLOYMENT.md)**: Detailed deployment procedures and automation
- **[ARCHITECTURE.md](ARCHITECTURE.md)**: Comprehensive architecture diagrams and visual representations
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**: Common issues and solutions

## Cost Management

### Free Tier Compliance
- **EC2**: t2.micro instances (750 hours/month free)
- **EBS**: Up to 30GB gp2 storage
- **ALB**: 15GB data processing/month
- **RDS**: db.t3.micro with 20GB storage (optional)

### Cost Monitoring
```bash
# Check current costs
python3 app/cost_optimizer.py --check-costs

# Validate free tier compliance
python3 scripts/validate-config.py --check-free-tier infrastructure/parameters/dev.json

# Set up cost alerts
aws cloudwatch put-metric-alarm --alarm-name "BillingAlert" --alarm-description "Alert when charges exceed $10"
```

## Monitoring and Alerting

### CloudWatch Metrics
- **EC2**: CPU utilization, network I/O, disk I/O
- **ALB**: Request count, response time, error rates
- **RDS**: CPU, connections, read/write IOPS (if enabled)
- **Custom**: Application-specific metrics

### SNS Alerts
- High CPU utilization (>80%)
- High error rates (>5%)
- Auto Scaling events
- Cost threshold breaches

### Health Checks
- **ALB Health Check**: `/health` endpoint every 30 seconds
- **Application Health**: Database connectivity, service status
- **Infrastructure Health**: CloudFormation stack status

## Security

### Network Security
- **VPC**: Custom VPC with public/private subnets
- **Security Groups**: Restrictive ingress/egress rules
- **NACLs**: Additional network-level security
- **NAT Gateway**: Secure internet access for private instances

### Access Control
- **IAM Roles**: Least privilege principle
- **Instance Profiles**: No hardcoded credentials
- **Security Groups**: Port-specific access control

### Data Protection
- **EBS Encryption**: Encrypted storage volumes
- **RDS Encryption**: Encrypted database (if enabled)
- **SSL/TLS**: HTTPS termination at ALB

## Troubleshooting

### Common Issues

1. **Deployment Failures**
   ```bash
   # Check CloudFormation events
   aws cloudformation describe-stack-events --stack-name dominoes-app-dev-vpc
   
   # Validate templates
   aws cloudformation validate-template --template-body file://infrastructure/vpc-network.yaml
   ```

2. **Application Not Responding**
   ```bash
   # Check instance health
   aws elbv2 describe-target-health --target-group-arn <target-group-arn>
   
   # Check application logs
   aws logs tail /aws/ec2/dominoes-app --follow
   ```

3. **Auto Scaling Issues**
   ```bash
   # Check scaling activities
   aws autoscaling describe-scaling-activities --auto-scaling-group-name dominoes-app-dev-asg
   
   # Check CloudWatch metrics
   aws cloudwatch get-metric-statistics --namespace AWS/EC2 --metric-name CPUUtilization
   ```

### Debug Mode
```bash
# Enable debug logging
export FLASK_DEBUG=true
export LOG_LEVEL=DEBUG

# Run with verbose output
set -x
./scripts/deploy.sh
```

## Testing

### Test Categories
- **Unit Tests**: Application logic and components
- **Integration Tests**: Multi-component interactions
- **Load Tests**: Performance and scaling behavior
- **Infrastructure Tests**: CloudFormation template validation
- **Security Tests**: Security configuration validation

### Run All Tests
```bash
python3 tests/run_comprehensive_tests.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run the test suite
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
1. Check the troubleshooting guide in [DEPLOYMENT.md](DEPLOYMENT.md)
2. Review CloudFormation events in AWS Console
3. Check application logs in CloudWatch
4. Validate configuration with validation scripts

## Game Instructions

### How to Play Dominoes
1. Each player starts with 7 tiles from a double-six domino set
2. The player with the highest tile (preferring doubles) goes first
3. Place tiles by matching numbers on either end of the board
4. If you can't play, draw from the boneyard
5. First player to use all tiles wins
6. If no one can play, player with lowest pip count wins

### AI Strategy
The AI opponent uses strategic gameplay:
- Prioritizes high-value tiles
- Blocks opponent moves when possible
- Manages tile distribution effectively


Enjoy your scalable dominoes game on AWS!


