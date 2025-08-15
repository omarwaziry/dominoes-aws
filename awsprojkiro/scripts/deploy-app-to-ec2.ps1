# Deploy application to EC2 instances in Auto Scaling Group
# PowerShell version for Windows environments

param(
    [Parameter(Position=0)]
    [ValidateSet("deploy", "package", "instances")]
    [string]$Action = "deploy",
    
    [string]$ProjectName = $env:PROJECT_NAME ?? "dominoes-app",
    [string]$Environment = $env:ENVIRONMENT ?? "dev",
    [string]$AwsRegion = $env:AWS_REGION ?? "us-east-1"
)

$S3Bucket = "$ProjectName-$Environment-app-bucket"

# Logging functions
function Write-Log {
    param([string]$Message)
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] WARNING: $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ERROR: $Message" -ForegroundColor Red
}

# Check prerequisites
function Test-Prerequisites {
    Write-Log "Checking prerequisites..."
    
    # Check AWS CLI
    if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
        Write-Error "AWS CLI is not installed"
        exit 1
    }
    
    # Check AWS credentials
    try {
        aws sts get-caller-identity | Out-Null
    }
    catch {
        Write-Error "AWS credentials not configured"
        exit 1
    }
    
    Write-Log "Prerequisites check passed"
}

# Package application
function New-ApplicationPackage {
    Write-Log "Packaging application..."
    
    # Create temporary directory
    $TempDir = New-TemporaryFile | ForEach-Object { Remove-Item $_; New-Item -ItemType Directory -Path $_ }
    $PackageDir = Join-Path $TempDir "dominoes-app"
    
    # Create package directory structure
    New-Item -ItemType Directory -Path $PackageDir -Force | Out-Null
    
    # Copy application files
    Copy-Item -Path "app" -Destination $PackageDir -Recurse -Force
    Copy-Item -Path "static" -Destination $PackageDir -Recurse -Force
    Copy-Item -Path "templates" -Destination $PackageDir -Recurse -Force
    Copy-Item -Path "wsgi.py" -Destination $PackageDir -Force
    Copy-Item -Path "requirements.txt" -Destination $PackageDir -Force
    
    # Create deployment metadata
    $DeploymentInfo = @{
        deployment_time = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        git_commit = try { git rev-parse HEAD } catch { "unknown" }
        git_branch = try { git rev-parse --abbrev-ref HEAD } catch { "unknown" }
        version = "1.0.0"
        environment = $Environment
    } | ConvertTo-Json -Depth 2
    
    $DeploymentInfo | Out-File -FilePath (Join-Path $PackageDir "deployment-info.json") -Encoding UTF8
    
    # Create deployment script for EC2 instances
    $DeployScript = @'
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
'@
    
    $DeployScript | Out-File -FilePath (Join-Path $PackageDir "deploy-on-instance.sh") -Encoding UTF8
    
    # Create zip package
    $PackageFile = Join-Path $TempDir "dominoes-app-$(Get-Date -Format 'yyyyMMdd-HHmmss').zip"
    Compress-Archive -Path (Join-Path $PackageDir "*") -DestinationPath $PackageFile -Force
    
    return $PackageFile
}

# Upload package to S3
function Publish-ToS3 {
    param([string]$PackageFile)
    
    $S3Key = "deployments/$(Split-Path $PackageFile -Leaf)"
    
    Write-Log "Uploading package to S3..."
    
    # Create bucket if it doesn't exist
    try {
        aws s3 ls "s3://$S3Bucket" | Out-Null
    }
    catch {
        Write-Log "Creating S3 bucket: $S3Bucket"
        aws s3 mb "s3://$S3Bucket" --region $AwsRegion
        
        # Enable versioning
        aws s3api put-bucket-versioning --bucket $S3Bucket --versioning-configuration Status=Enabled
    }
    
    # Upload package
    aws s3 cp $PackageFile "s3://$S3Bucket/$S3Key"
    
    # Update latest symlink
    aws s3 cp "s3://$S3Bucket/$S3Key" "s3://$S3Bucket/deployments/latest.zip"
    
    return "s3://$S3Bucket/$S3Key"
}

# Get EC2 instances in Auto Scaling Group
function Get-ASGInstances {
    Write-Log "Getting EC2 instances from Auto Scaling Group..."
    
    $ASGName = "$ProjectName-$Environment-asg"
    
    $Instances = aws autoscaling describe-auto-scaling-groups `
        --auto-scaling-group-names $ASGName `
        --query 'AutoScalingGroups[0].Instances[?LifecycleState==`InService`].InstanceId' `
        --output text
    
    return $Instances -split '\s+'
}

# Deploy to EC2 instances
function Deploy-ToInstances {
    param(
        [string]$S3Url,
        [string[]]$Instances
    )
    
    if (-not $Instances -or $Instances.Count -eq 0) {
        Write-Warning "No instances found in Auto Scaling Group"
        return $false
    }
    
    Write-Log "Deploying to instances: $($Instances -join ', ')"
    
    foreach ($InstanceId in $Instances) {
        Write-Log "Deploying to instance: $InstanceId"
        
        # Create deployment command
        $DeployCommand = @"
cd /tmp && \
sudo rm -rf dominoes-app-deployment && \
aws s3 cp '$S3Url' deployment.zip && \
unzip -q deployment.zip && \
mv dominoes-app dominoes-app-deployment && \
chmod +x dominoes-app-deployment/deploy-on-instance.sh && \
./dominoes-app-deployment/deploy-on-instance.sh
"@
        
        # Execute deployment via SSM
        $CommandId = aws ssm send-command `
            --instance-ids $InstanceId `
            --document-name "AWS-RunShellScript" `
            --parameters "commands=[$DeployCommand]" `
            --query 'Command.CommandId' `
            --output text
        
        Write-Log "Deployment command sent to $InstanceId (Command ID: $CommandId)"
        
        # Wait for command completion
        $Status = "InProgress"
        $Attempts = 0
        $MaxAttempts = 30
        
        while ($Status -eq "InProgress" -and $Attempts -lt $MaxAttempts) {
            Start-Sleep -Seconds 10
            try {
                $Status = aws ssm get-command-invocation `
                    --command-id $CommandId `
                    --instance-id $InstanceId `
                    --query 'Status' `
                    --output text 2>$null
            }
            catch {
                $Status = "InProgress"
            }
            
            $Attempts++
            Write-Host "." -NoNewline
        }
        Write-Host
        
        if ($Status -eq "Success") {
            Write-Log "✅ Deployment successful on instance $InstanceId"
        }
        else {
            Write-Error "❌ Deployment failed on instance $InstanceId (Status: $Status)"
            
            # Get command output for debugging
            aws ssm get-command-invocation `
                --command-id $CommandId `
                --instance-id $InstanceId `
                --query 'StandardOutputContent' `
                --output text
        }
    }
    
    return $true
}

# Main deployment function
function Start-Deployment {
    Write-Log "Starting deployment process..."
    
    Test-Prerequisites
    
    # Package application
    $PackageFile = New-ApplicationPackage
    Write-Log "Application packaged: $PackageFile"
    
    # Upload to S3
    $S3Url = Publish-ToS3 -PackageFile $PackageFile
    Write-Log "Package uploaded to: $S3Url"
    
    # Get instances
    $Instances = Get-ASGInstances
    
    if (-not $Instances -or $Instances.Count -eq 0) {
        Write-Error "No instances found in Auto Scaling Group"
        exit 1
    }
    
    # Deploy to instances
    $Success = Deploy-ToInstances -S3Url $S3Url -Instances $Instances
    
    # Cleanup
    Remove-Item -Path (Split-Path $PackageFile -Parent) -Recurse -Force
    
    if ($Success) {
        Write-Log "🎉 Deployment process completed!"
    }
    else {
        Write-Error "Deployment process failed!"
        exit 1
    }
}

# Handle script actions
switch ($Action) {
    "deploy" {
        Start-Deployment
    }
    "package" {
        Test-Prerequisites
        $PackageFile = New-ApplicationPackage
        Write-Log "Application packaged: $PackageFile"
    }
    "instances" {
        $Instances = Get-ASGInstances
        Write-Host "Instances in ASG: $($Instances -join ', ')"
    }
    default {
        Write-Host "Usage: .\deploy-app-to-ec2.ps1 [deploy|package|instances]"
        Write-Host "  deploy    - Full deployment (default)"
        Write-Host "  package   - Package application only"
        Write-Host "  instances - List ASG instances"
        exit 1
    }
}