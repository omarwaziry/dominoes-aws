#!/bin/bash

# Main deployment script for the dominoes application
# This script orchestrates the complete deployment process with parameter validation and rollback support

set -e

# Configuration
PROJECT_NAME=${PROJECT_NAME:-"dominoes-app"}
ENVIRONMENT=${ENVIRONMENT:-"dev"}
AWS_REGION=${AWS_REGION:-"us-east-1"}
ALERT_EMAIL=${ALERT_EMAIL:-""}
AWS_PROFILE=${AWS_PROFILE:-""}
PARAMETER_FILE=${PARAMETER_FILE:-""}
DISABLE_ROLLBACK=${DISABLE_ROLLBACK:-"false"}
SKIP_PACKAGING=${SKIP_PACKAGING:-"false"}
DRY_RUN=${DRY_RUN:-"false"}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Dominoes Application Deployment ===${NC}"

# Show configuration
show_configuration() {
    echo -e "${BLUE}Deployment Configuration:${NC}"
    echo "Project Name: ${PROJECT_NAME}"
    echo "Environment: ${ENVIRONMENT}"
    echo "AWS Region: ${AWS_REGION}"
    echo "Alert Email: ${ALERT_EMAIL}"
    echo "AWS Profile: ${AWS_PROFILE:-"default"}"
    echo "Parameter File: ${PARAMETER_FILE:-"infrastructure/parameters/${ENVIRONMENT}.json"}"
    echo "Disable Rollback: ${DISABLE_ROLLBACK}"
    echo "Skip Packaging: ${SKIP_PACKAGING}"
    echo "Dry Run: ${DRY_RUN}"
    echo ""
}

# Validate prerequisites
validate_prerequisites() {
    echo -e "${BLUE}Validating prerequisites...${NC}"
    
    # Check required tools
    local missing_tools=()
    
    if ! command -v aws &> /dev/null; then
        missing_tools+=("aws-cli")
    fi
    
    if ! command -v python3 &> /dev/null; then
        missing_tools+=("python3")
    fi
    
    if ! command -v jq &> /dev/null; then
        missing_tools+=("jq")
    fi
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        echo -e "${RED}Error: Missing required tools: ${missing_tools[*]}${NC}"
        echo "Please install the missing tools and try again."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity ${AWS_PROFILE:+--profile $AWS_PROFILE} &> /dev/null; then
        echo -e "${RED}Error: AWS credentials not configured or invalid${NC}"
        echo "Please configure AWS credentials using 'aws configure' or set AWS_PROFILE"
        exit 1
    fi
    
    # Check alert email
    if [ -z "${ALERT_EMAIL}" ]; then
        echo -e "${RED}Error: ALERT_EMAIL is required${NC}"
        echo "Please set ALERT_EMAIL environment variable or pass --alert-email"
        exit 1
    fi
    
    # Validate email format
    if [[ ! "${ALERT_EMAIL}" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
        echo -e "${RED}Error: Invalid email format: ${ALERT_EMAIL}${NC}"
        exit 1
    fi
    
    # Check parameter file exists if specified
    if [ -n "${PARAMETER_FILE}" ] && [ ! -f "${PARAMETER_FILE}" ]; then
        echo -e "${RED}Error: Parameter file not found: ${PARAMETER_FILE}${NC}"
        exit 1
    fi
    
    # Check default parameter file exists
    DEFAULT_PARAM_FILE="infrastructure/parameters/${ENVIRONMENT}.json"
    if [ -z "${PARAMETER_FILE}" ] && [ ! -f "${DEFAULT_PARAM_FILE}" ]; then
        echo -e "${YELLOW}Warning: Default parameter file not found: ${DEFAULT_PARAM_FILE}${NC}"
        echo "Will use built-in defaults"
    fi
    
    echo -e "${GREEN}✓ Prerequisites validated${NC}"
}

# Validate parameters
validate_parameters() {
    echo -e "${BLUE}Validating deployment parameters...${NC}"
    
    local param_file="${PARAMETER_FILE:-infrastructure/parameters/${ENVIRONMENT}.json}"
    
    if [ -f "${param_file}" ]; then
        # Validate JSON syntax
        if ! jq empty "${param_file}" 2>/dev/null; then
            echo -e "${RED}Error: Invalid JSON in parameter file: ${param_file}${NC}"
            exit 1
        fi
        
        # Check required parameters
        local required_params=("ProjectName" "Environment" "InstanceType")
        for param in "${required_params[@]}"; do
            if ! jq -e ".${param}" "${param_file}" &> /dev/null; then
                echo -e "${RED}Error: Required parameter '${param}' missing from ${param_file}${NC}"
                exit 1
            fi
        done
        
        # Validate free tier compliance
        local instance_type=$(jq -r '.InstanceType // "t2.micro"' "${param_file}")
        if [[ ! "${instance_type}" =~ ^(t2\.micro|t3\.micro)$ ]]; then
            echo -e "${RED}Error: Instance type '${instance_type}' is not free tier eligible${NC}"
            echo "Use t2.micro or t3.micro for free tier compliance"
            exit 1
        fi
        
        local max_instances=$(jq -r '.MaxInstances // 3' "${param_file}")
        if [ "${max_instances}" -gt 3 ]; then
            echo -e "${YELLOW}Warning: MaxInstances (${max_instances}) may exceed free tier limits${NC}"
        fi
        
        # Validate RDS settings if enabled
        local enable_rds=$(jq -r '.EnableRDS // false' "${param_file}")
        if [ "${enable_rds}" = "true" ]; then
            local db_instance_class=$(jq -r '.DBInstanceClass // "db.t3.micro"' "${param_file}")
            if [[ ! "${db_instance_class}" =~ ^(db\.t2\.micro|db\.t3\.micro)$ ]]; then
                echo -e "${RED}Error: RDS instance class '${db_instance_class}' is not free tier eligible${NC}"
                exit 1
            fi
            
            local db_storage=$(jq -r '.DBAllocatedStorage // 20' "${param_file}")
            if [ "${db_storage}" -gt 20 ]; then
                echo -e "${YELLOW}Warning: RDS storage (${db_storage}GB) exceeds free tier limit of 20GB${NC}"
            fi
        fi
        
        echo -e "${GREEN}✓ Parameters validated${NC}"
    else
        echo -e "${YELLOW}No parameter file found, using defaults${NC}"
    fi
}

# Package application
package_application() {
    if [ "${SKIP_PACKAGING}" = "true" ]; then
        echo -e "${YELLOW}Skipping application packaging${NC}"
        return 0
    fi
    
    echo -e "${BLUE}Packaging application...${NC}"
    
    # Set environment variables for packaging script
    export PROJECT_NAME
    export ENVIRONMENT
    export AWS_REGION
    export AWS_PROFILE
    
    # Run packaging script
    if ! ./scripts/package-app.sh; then
        echo -e "${RED}Error: Application packaging failed${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✓ Application packaged successfully${NC}"
}

# Deploy infrastructure
deploy_infrastructure() {
    echo -e "${BLUE}Deploying infrastructure...${NC}"
    
    local deploy_args=(
        "deploy"
        "--project-name" "${PROJECT_NAME}"
        "--environment" "${ENVIRONMENT}"
        "--region" "${AWS_REGION}"
        "--alert-email" "${ALERT_EMAIL}"
    )
    
    if [ -n "${AWS_PROFILE}" ]; then
        deploy_args+=("--profile" "${AWS_PROFILE}")
    fi
    
    if [ -n "${PARAMETER_FILE}" ]; then
        deploy_args+=("--parameter-file" "${PARAMETER_FILE}")
    fi
    
    if [ "${DISABLE_ROLLBACK}" = "true" ]; then
        deploy_args+=("--disable-rollback")
    fi
    
    if [ "${DRY_RUN}" = "true" ]; then
        echo -e "${YELLOW}DRY RUN: Would execute: python3 infrastructure/deploy.py ${deploy_args[*]}${NC}"
        return 0
    fi
    
    # Run deployment
    if ! python3 infrastructure/deploy.py "${deploy_args[@]}"; then
        echo -e "${RED}Error: Infrastructure deployment failed${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✓ Infrastructure deployed successfully${NC}"
}

# Validate deployment
validate_deployment() {
    echo -e "${BLUE}Validating deployment...${NC}"
    
    local validate_args=(
        "validate"
        "--project-name" "${PROJECT_NAME}"
        "--environment" "${ENVIRONMENT}"
        "--region" "${AWS_REGION}"
    )
    
    if [ -n "${AWS_PROFILE}" ]; then
        validate_args+=("--profile" "${AWS_PROFILE}")
    fi
    
    if [ "${DRY_RUN}" = "true" ]; then
        echo -e "${YELLOW}DRY RUN: Would execute: python3 infrastructure/deploy.py ${validate_args[*]}${NC}"
        return 0
    fi
    
    # Run validation
    if ! python3 infrastructure/deploy.py "${validate_args[@]}"; then
        echo -e "${YELLOW}Warning: Deployment validation found issues${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✓ Deployment validated successfully${NC}"
}

# Rollback deployment
rollback_deployment() {
    local stack_name="$1"
    
    if [ -z "${stack_name}" ]; then
        echo -e "${RED}Error: Stack name is required for rollback${NC}"
        return 1
    fi
    
    echo -e "${BLUE}Rolling back stack: ${stack_name}${NC}"
    
    local rollback_args=(
        "rollback"
        "--stack-name" "${stack_name}"
        "--region" "${AWS_REGION}"
    )
    
    if [ -n "${AWS_PROFILE}" ]; then
        rollback_args+=("--profile" "${AWS_PROFILE}")
    fi
    
    if [ "${DRY_RUN}" = "true" ]; then
        echo -e "${YELLOW}DRY RUN: Would execute: python3 infrastructure/deploy.py ${rollback_args[*]}${NC}"
        return 0
    fi
    
    # Run rollback
    if ! python3 infrastructure/deploy.py "${rollback_args[@]}"; then
        echo -e "${RED}Error: Rollback failed for ${stack_name}${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✓ Rollback completed for ${stack_name}${NC}"
}

# Cleanup deployment
cleanup_deployment() {
    echo -e "${BLUE}Cleaning up deployment...${NC}"
    
    local cleanup_args=(
        "cleanup"
        "--project-name" "${PROJECT_NAME}"
        "--environment" "${ENVIRONMENT}"
        "--region" "${AWS_REGION}"
    )
    
    if [ -n "${AWS_PROFILE}" ]; then
        cleanup_args+=("--profile" "${AWS_PROFILE}")
    fi
    
    if [ "${DRY_RUN}" = "true" ]; then
        echo -e "${YELLOW}DRY RUN: Would execute: python3 infrastructure/deploy.py ${cleanup_args[*]}${NC}"
        return 0
    fi
    
    # Confirm cleanup
    echo -e "${YELLOW}This will delete all resources for ${PROJECT_NAME}-${ENVIRONMENT}${NC}"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cleanup cancelled"
        return 0
    fi
    
    # Run cleanup
    if ! python3 infrastructure/deploy.py "${cleanup_args[@]}"; then
        echo -e "${RED}Error: Cleanup failed${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✓ Cleanup completed successfully${NC}"
}

# Show usage
show_usage() {
    cat << EOF
Usage: $0 [ACTION] [OPTIONS]

Actions:
    deploy      Deploy the application (default)
    rollback    Rollback a specific stack
    cleanup     Clean up all resources
    validate    Validate deployment

Environment Variables:
    PROJECT_NAME        Project name (default: dominoes-app)
    ENVIRONMENT         Environment (default: dev)
    AWS_REGION          AWS region (default: us-east-1)
    ALERT_EMAIL         Email for alerts (required)
    AWS_PROFILE         AWS profile to use
    PARAMETER_FILE      Path to parameter file
    DISABLE_ROLLBACK    Disable automatic rollback (default: false)
    SKIP_PACKAGING      Skip application packaging (default: false)
    DRY_RUN            Show what would be done (default: false)

Examples:
    # Deploy to dev environment
    ALERT_EMAIL=admin@example.com ./scripts/deploy.sh

    # Deploy to staging with custom parameters
    ENVIRONMENT=staging PARAMETER_FILE=my-params.json ./scripts/deploy.sh

    # Rollback a specific stack
    ./scripts/deploy.sh rollback --stack-name dominoes-app-dev-vpc

    # Cleanup all resources
    ./scripts/deploy.sh cleanup

    # Dry run deployment
    DRY_RUN=true ./scripts/deploy.sh

EOF
}

# Main execution
main() {
    local action="${1:-deploy}"
    
    case "${action}" in
        deploy)
            show_configuration
            validate_prerequisites
            validate_parameters
            package_application
            deploy_infrastructure
            validate_deployment
            
            echo ""
            echo -e "${GREEN}=== Deployment Complete ===${NC}"
            echo -e "${GREEN}Environment: ${ENVIRONMENT}${NC}"
            echo -e "${GREEN}Region: ${AWS_REGION}${NC}"
            echo -e "${GREEN}Alert Email: ${ALERT_EMAIL}${NC}"
            echo ""
            echo -e "${YELLOW}Next steps:${NC}"
            echo "1. Check AWS Console for stack status"
            echo "2. Test application endpoints"
            echo "3. Monitor CloudWatch dashboards"
            echo "4. Review cost monitoring alerts"
            ;;
        rollback)
            if [ -z "$2" ]; then
                echo -e "${RED}Error: Stack name required for rollback${NC}"
                echo "Usage: $0 rollback <stack-name>"
                exit 1
            fi
            rollback_deployment "$2"
            ;;
        cleanup)
            cleanup_deployment
            ;;
        validate)
            show_configuration
            validate_prerequisites
            validate_deployment
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            echo -e "${RED}Error: Unknown action '${action}'${NC}"
            show_usage
            exit 1
            ;;
    esac
}

# Handle script arguments
if [ "$1" = "rollback" ] && [ -n "$2" ]; then
    main "$1" "$2"
else
    main "$1"
fi