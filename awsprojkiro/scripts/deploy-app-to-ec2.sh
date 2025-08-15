#!/bin/bash

# Deploy application to EC2 instances in Auto Scaling Group
# This script packages the application and deploys it to running instances

set -e

# Configuration
PROJECT_NAME="${PROJECT_NAME:-dominoes-app}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
AWS_REGION="${AWS_REGION:-us-east-1}"
S3_BUCKET="${PROJECT_NAME}-${ENVIRONMENT}-app-bucket"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    if ! command -v aws &> /dev/null; then
        error "AWS CLI is not installed"
        exit 1
    fi
    
    if ! command -v zip &> /dev/null; then
        error "zip command is not available"
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        error "AWS credentials not configured"
        exit 1
    fi
    
    log "Prerequisites check passed"
}

# Package application
package_application() {
    log "Packaging application..."
    
    # Create temporary directory
    TEMP_DIR=$(mktemp -d)
    PACKAGE_DIR="$TEMP_DIR/dominoes-app"
    
    # Create package directory structure
    mkdir -p "$PACKAGE_DIR"
    
    # Copy application files
    cp -r app/ "$PACKAGE_DIR/"
    cp -r static/ "$PACKAGE_DIR/"
    cp -r templates/ "$PACKAGE_DIR/"
    cp wsgi.py "$PACKAGE_DIR/"
    cp requirements.txt "$PACKAGE_DIR/"
    
    # Create deployment metadata
    cat > "$PACKAGE_DIR/deployment-info.json" << EOF
{
    "deployment_time": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "git_commit": "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')",
    "git_branch": "$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')",
    "version": "1.0.0",
    "environment": "$ENVIRONMENT"
}
EOF
    
    # Create deployment script for EC2 instances
    cat > "$PACKAGE_DIR/deploy-on-instance.sh" << 'EOF'
#!/bin/bash
set -e

APP_DIR="/opt/dominoes-app"
BACKUP_DIR="/opt/dominoes-app-backup-$(date +%Y%m%d-%H%M%S)"

echo "Starting application deployment..."

# Create backup of current application
if [ -d "$APP_DIR" ]; then
    echo "Creating backup at $BACKUP_DIR"
    sudo cp -r "$APP_DIR" "$BACKUP_DIR"
fi

# Stop the application service
echo "Stopping dominoes-app service..."
sudo systemctl stop dominoes-app || true

# Update application files
echo "Updating application files..."
sudo cp -r /tmp/dominoes-app-deployment/* "$APP_DIR/"
sudo chown -R dominoes:dominoes "$APP_DIR"

# Install/update dependencies
echo "Installing Python dependencies..."
cd "$APP_DIR"
sudo -u dominoes pip3 install -r requirements.txt

# Start the application service
echo "Starting dominoes-app service..."
sudo systemctl start dominoes-app

# Wait for service to be ready
sleep 5

# Verify deployment
if sudo systemctl is-active --quiet dominoes-app; then
    echo "✅ Application service is running"
    
    # Test health endpoint
    if curl -f http://localhost/health > /dev/null 2>&1; then
        echo "✅ Health check passed"
        echo "🎉 Deployment completed successfully!"
        
        # Clean up old backup (keep only last 3)
        sudo find /opt -name "dominoes-app-backup-*" -type d | sort | head -n -3 | xargs sudo rm -rf
    else
        echo "❌ Health check failed"
        echo "Rolling back to previous version..."
        sudo systemctl stop dominoes-app
        sudo rm -rf "$APP_DIR"
        sudo mv "$BACKUP_DIR" "$APP_DIR"
        sudo systemctl start dominoes-app
        exit 1
    fi
else
    echo "❌ Application service failed to start"
    echo "Rolling back to previous version..."
    sudo rm -rf "$APP_DIR"
    sudo mv "$BACKUP_DIR" "$APP_DIR"
    sudo systemctl start dominoes-app
    exit 1
fi
EOF
    
    chmod +x "$PACKAGE_DIR/deploy-on-instance.sh"
    
    # Create zip package
    cd "$TEMP_DIR"
    zip -r "dominoes-app-$(date +%Y%m%d-%H%M%S).zip" dominoes-app/
    
    PACKAGE_FILE="$TEMP_DIR/dominoes-app-$(date +%Y%m%d-%H%M%S).zip"
    echo "$PACKAGE_FILE"
}

# Upload package to S3
upload_to_s3() {
    local package_file="$1"
    local s3_key="deployments/$(basename "$package_file")"
    
    log "Uploading package to S3..."
    
    # Create bucket if it doesn't exist
    if ! aws s3 ls "s3://$S3_BUCKET" &> /dev/null; then
        log "Creating S3 bucket: $S3_BUCKET"
        aws s3 mb "s3://$S3_BUCKET" --region "$AWS_REGION"
        
        # Enable versioning
        aws s3api put-bucket-versioning \
            --bucket "$S3_BUCKET" \
            --versioning-configuration Status=Enabled
    fi
    
    # Upload package
    aws s3 cp "$package_file" "s3://$S3_BUCKET/$s3_key"
    
    # Update latest symlink
    aws s3 cp "s3://$S3_BUCKET/$s3_key" "s3://$S3_BUCKET/deployments/latest.zip"
    
    echo "s3://$S3_BUCKET/$s3_key"
}

# Get EC2 instances in Auto Scaling Group
get_asg_instances() {
    log "Getting EC2 instances from Auto Scaling Group..."
    
    local asg_name="${PROJECT_NAME}-${ENVIRONMENT}-asg"
    
    aws autoscaling describe-auto-scaling-groups \
        --auto-scaling-group-names "$asg_name" \
        --query 'AutoScalingGroups[0].Instances[?LifecycleState==`InService`].InstanceId' \
        --output text
}

# Deploy to EC2 instances
deploy_to_instances() {
    local s3_url="$1"
    local instances="$2"
    
    if [ -z "$instances" ]; then
        warn "No instances found in Auto Scaling Group"
        return 1
    fi
    
    log "Deploying to instances: $instances"
    
    for instance_id in $instances; do
        log "Deploying to instance: $instance_id"
        
        # Create deployment command
        local deploy_command="
            cd /tmp && \
            sudo rm -rf dominoes-app-deployment && \
            aws s3 cp '$s3_url' deployment.zip && \
            unzip -q deployment.zip && \
            mv dominoes-app dominoes-app-deployment && \
            chmod +x dominoes-app-deployment/deploy-on-instance.sh && \
            ./dominoes-app-deployment/deploy-on-instance.sh
        "
        
        # Execute deployment via SSM
        local command_id=$(aws ssm send-command \
            --instance-ids "$instance_id" \
            --document-name "AWS-RunShellScript" \
            --parameters "commands=[\"$deploy_command\"]" \
            --query 'Command.CommandId' \
            --output text)
        
        log "Deployment command sent to $instance_id (Command ID: $command_id)"
        
        # Wait for command completion
        local status="InProgress"
        local attempts=0
        local max_attempts=30
        
        while [ "$status" = "InProgress" ] && [ $attempts -lt $max_attempts ]; do
            sleep 10
            status=$(aws ssm get-command-invocation \
                --command-id "$command_id" \
                --instance-id "$instance_id" \
                --query 'Status' \
                --output text 2>/dev/null || echo "InProgress")
            
            attempts=$((attempts + 1))
            echo -n "."
        done
        echo
        
        if [ "$status" = "Success" ]; then
            log "✅ Deployment successful on instance $instance_id"
        else
            error "❌ Deployment failed on instance $instance_id (Status: $status)"
            
            # Get command output for debugging
            aws ssm get-command-invocation \
                --command-id "$command_id" \
                --instance-id "$instance_id" \
                --query 'StandardOutputContent' \
                --output text
        fi
    done
}

# Main deployment function
main() {
    log "Starting deployment process..."
    
    check_prerequisites
    
    # Package application
    local package_file
    package_file=$(package_application)
    log "Application packaged: $package_file"
    
    # Upload to S3
    local s3_url
    s3_url=$(upload_to_s3 "$package_file")
    log "Package uploaded to: $s3_url"
    
    # Get instances
    local instances
    instances=$(get_asg_instances)
    
    if [ -z "$instances" ]; then
        error "No instances found in Auto Scaling Group"
        exit 1
    fi
    
    # Deploy to instances
    deploy_to_instances "$s3_url" "$instances"
    
    # Cleanup
    rm -rf "$(dirname "$package_file")"
    
    log "🎉 Deployment process completed!"
}

# Handle script arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "package")
        check_prerequisites
        package_file=$(package_application)
        log "Application packaged: $package_file"
        ;;
    "instances")
        instances=$(get_asg_instances)
        echo "Instances in ASG: $instances"
        ;;
    *)
        echo "Usage: $0 [deploy|package|instances]"
        echo "  deploy    - Full deployment (default)"
        echo "  package   - Package application only"
        echo "  instances - List ASG instances"
        exit 1
        ;;
esac