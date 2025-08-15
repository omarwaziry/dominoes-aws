#!/bin/bash

# Package application for deployment
# This script creates a deployment package and uploads it to S3

set -e

# Configuration
PROJECT_NAME=${PROJECT_NAME:-"dominoes-app"}
ENVIRONMENT=${ENVIRONMENT:-"dev"}
AWS_REGION=${AWS_REGION:-"us-east-1"}
S3_BUCKET=${S3_BUCKET:-"${PROJECT_NAME}-${ENVIRONMENT}-deployment-bucket"}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Packaging Dominoes Application ===${NC}"

# Check if required tools are installed
check_dependencies() {
    echo "Checking dependencies..."
    
    if ! command -v aws &> /dev/null; then
        echo -e "${RED}Error: AWS CLI is not installed${NC}"
        exit 1
    fi
    
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Error: Python 3 is not installed${NC}"
        exit 1
    fi
    
    if ! command -v zip &> /dev/null; then
        echo -e "${RED}Error: zip is not installed${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ All dependencies are installed${NC}"
}

# Create deployment directory
create_deployment_package() {
    echo "Creating deployment package..."
    
    # Clean up previous builds
    rm -rf dist/
    mkdir -p dist/
    
    # Copy application files
    echo "Copying application files..."
    cp -r app/ dist/
    cp -r static/ dist/
    cp -r templates/ dist/
    cp wsgi.py dist/
    cp requirements.txt dist/
    
    # Copy infrastructure files
    mkdir -p dist/infrastructure/
    cp infrastructure/*.yaml dist/infrastructure/
    
    # Create version file
    echo "Creating version file..."
    cat > dist/version.json << EOF
{
    "version": "$(date +%Y%m%d-%H%M%S)",
    "commit": "$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')",
    "build_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "project": "${PROJECT_NAME}",
    "environment": "${ENVIRONMENT}"
}
EOF
    
    # Create deployment configuration
    echo "Creating deployment configuration..."
    cat > dist/deploy-config.json << EOF
{
    "project_name": "${PROJECT_NAME}",
    "environment": "${ENVIRONMENT}",
    "region": "${AWS_REGION}",
    "instance_type": "t2.micro",
    "min_instances": 2,
    "max_instances": 3,
    "health_check_path": "/health",
    "application_port": 80
}
EOF
    
    echo -e "${GREEN}✓ Deployment package created${NC}"
}

# Install dependencies
install_dependencies() {
    echo "Installing Python dependencies..."
    
    cd dist/
    
    # Create virtual environment for clean dependency installation
    python3 -m venv venv
    source venv/bin/activate
    
    # Install dependencies
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # Copy installed packages to deployment
    cp -r venv/lib/python*/site-packages/* .
    
    # Clean up virtual environment
    rm -rf venv/
    
    cd ..
    
    echo -e "${GREEN}✓ Dependencies installed${NC}"
}

# Create application archive
create_archive() {
    echo "Creating application archive..."
    
    cd dist/
    
    # Create the zip file
    zip -r "../${PROJECT_NAME}-${ENVIRONMENT}-$(date +%Y%m%d-%H%M%S).zip" . -x "*.pyc" "*/__pycache__/*"
    
    cd ..
    
    ARCHIVE_NAME="${PROJECT_NAME}-${ENVIRONMENT}-$(date +%Y%m%d-%H%M%S).zip"
    echo -e "${GREEN}✓ Archive created: ${ARCHIVE_NAME}${NC}"
}

# Create S3 bucket if it doesn't exist
create_s3_bucket() {
    echo "Checking S3 bucket..."
    
    if aws s3 ls "s3://${S3_BUCKET}" 2>&1 | grep -q 'NoSuchBucket'; then
        echo "Creating S3 bucket: ${S3_BUCKET}"
        
        if [ "${AWS_REGION}" = "us-east-1" ]; then
            aws s3 mb "s3://${S3_BUCKET}"
        else
            aws s3 mb "s3://${S3_BUCKET}" --region "${AWS_REGION}"
        fi
        
        # Enable versioning
        aws s3api put-bucket-versioning \
            --bucket "${S3_BUCKET}" \
            --versioning-configuration Status=Enabled
        
        # Add bucket policy for deployment access
        cat > bucket-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowEC2Access",
            "Effect": "Allow",
            "Principal": {
                "Service": "ec2.amazonaws.com"
            },
            "Action": [
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::${S3_BUCKET}",
                "arn:aws:s3:::${S3_BUCKET}/*"
            ]
        }
    ]
}
EOF
        
        aws s3api put-bucket-policy \
            --bucket "${S3_BUCKET}" \
            --policy file://bucket-policy.json
        
        rm bucket-policy.json
        
        echo -e "${GREEN}✓ S3 bucket created and configured${NC}"
    else
        echo -e "${GREEN}✓ S3 bucket already exists${NC}"
    fi
}

# Upload to S3
upload_to_s3() {
    echo "Uploading to S3..."
    
    ARCHIVE_NAME=$(ls ${PROJECT_NAME}-${ENVIRONMENT}-*.zip | head -n 1)
    S3_KEY="deployments/${ARCHIVE_NAME}"
    
    aws s3 cp "${ARCHIVE_NAME}" "s3://${S3_BUCKET}/${S3_KEY}"
    
    # Create latest symlink
    aws s3 cp "s3://${S3_BUCKET}/${S3_KEY}" "s3://${S3_BUCKET}/deployments/latest.zip"
    
    echo -e "${GREEN}✓ Uploaded to s3://${S3_BUCKET}/${S3_KEY}${NC}"
    echo -e "${GREEN}✓ Latest version available at s3://${S3_BUCKET}/deployments/latest.zip${NC}"
}

# Create deployment manifest
create_deployment_manifest() {
    echo "Creating deployment manifest..."
    
    ARCHIVE_NAME=$(ls ${PROJECT_NAME}-${ENVIRONMENT}-*.zip | head -n 1)
    
    cat > deployment-manifest.json << EOF
{
    "deployment_id": "$(uuidgen)",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "project": "${PROJECT_NAME}",
    "environment": "${ENVIRONMENT}",
    "region": "${AWS_REGION}",
    "archive": {
        "name": "${ARCHIVE_NAME}",
        "s3_bucket": "${S3_BUCKET}",
        "s3_key": "deployments/${ARCHIVE_NAME}",
        "size": "$(stat -f%z "${ARCHIVE_NAME}" 2>/dev/null || stat -c%s "${ARCHIVE_NAME}")"
    },
    "configuration": {
        "instance_type": "t2.micro",
        "min_instances": 2,
        "max_instances": 3,
        "health_check_path": "/health"
    },
    "git": {
        "commit": "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')",
        "branch": "$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')",
        "tag": "$(git describe --tags --exact-match 2>/dev/null || echo 'none')"
    }
}
EOF
    
    # Upload manifest to S3
    aws s3 cp deployment-manifest.json "s3://${S3_BUCKET}/manifests/$(date +%Y%m%d-%H%M%S)-manifest.json"
    aws s3 cp deployment-manifest.json "s3://${S3_BUCKET}/manifests/latest-manifest.json"
    
    echo -e "${GREEN}✓ Deployment manifest created and uploaded${NC}"
}

# Validate package
validate_package() {
    echo "Validating package..."
    
    ARCHIVE_NAME=$(ls ${PROJECT_NAME}-${ENVIRONMENT}-*.zip | head -n 1)
    
    # Check if archive contains required files
    REQUIRED_FILES=("wsgi.py" "requirements.txt" "app/" "static/" "templates/")
    
    for file in "${REQUIRED_FILES[@]}"; do
        if ! unzip -l "${ARCHIVE_NAME}" | grep -q "${file}"; then
            echo -e "${RED}Error: Required file/directory ${file} not found in archive${NC}"
            exit 1
        fi
    done
    
    # Check archive size (should be reasonable for free tier)
    ARCHIVE_SIZE=$(stat -f%z "${ARCHIVE_NAME}" 2>/dev/null || stat -c%s "${ARCHIVE_NAME}")
    MAX_SIZE=$((50 * 1024 * 1024))  # 50MB
    
    if [ "${ARCHIVE_SIZE}" -gt "${MAX_SIZE}" ]; then
        echo -e "${YELLOW}Warning: Archive size (${ARCHIVE_SIZE} bytes) is larger than recommended${NC}"
    fi
    
    echo -e "${GREEN}✓ Package validation passed${NC}"
}

# Main execution
main() {
    echo -e "${GREEN}Starting deployment package creation...${NC}"
    echo "Project: ${PROJECT_NAME}"
    echo "Environment: ${ENVIRONMENT}"
    echo "Region: ${AWS_REGION}"
    echo "S3 Bucket: ${S3_BUCKET}"
    echo ""
    
    check_dependencies
    create_deployment_package
    install_dependencies
    create_archive
    validate_package
    create_s3_bucket
    upload_to_s3
    create_deployment_manifest
    
    echo ""
    echo -e "${GREEN}=== Packaging Complete ===${NC}"
    echo -e "${GREEN}Archive: $(ls ${PROJECT_NAME}-${ENVIRONMENT}-*.zip | head -n 1)${NC}"
    echo -e "${GREEN}S3 Location: s3://${S3_BUCKET}/deployments/latest.zip${NC}"
    echo -e "${GREEN}Manifest: s3://${S3_BUCKET}/manifests/latest-manifest.json${NC}"
    
    # Clean up
    rm -rf dist/
    
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo "1. Run the deployment script: ./scripts/deploy.sh"
    echo "2. Monitor the deployment in AWS Console"
    echo "3. Test the application health endpoint"
}

# Run main function
main "$@"