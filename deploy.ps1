# Simple deployment script for HPD Integration
Write-Host "Starting deployment..." -ForegroundColor Green

# Check if SAM is available
try {
    sam --version | Out-Null
    Write-Host "SAM CLI found" -ForegroundColor Green
} catch {
    Write-Host "SAM CLI not found - please install SAM CLI first" -ForegroundColor Red
    exit 1
}

# Check if AWS is configured
try {
    aws sts get-caller-identity --profile webelocity | Out-Null
    Write-Host "AWS CLI configured with webelocity profile" -ForegroundColor Green
} catch {
    Write-Host "AWS CLI not configured - please run 'aws configure --profile webelocity' first" -ForegroundColor Red
    exit 1
}

# Build the application
Write-Host "Building application..." -ForegroundColor Yellow
sam build

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed" -ForegroundColor Red
    exit 1
}

Write-Host "Build successful!" -ForegroundColor Green

# Deploy with guided setup
Write-Host "Deploying application..." -ForegroundColor Yellow
Write-Host "You will be prompted to enter parameters from your .env file" -ForegroundColor Cyan
sam deploy --guided --profile webelocity

if ($LASTEXITCODE -eq 0) {
    Write-Host "Deployment completed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Check CloudFormation stack in AWS Console"
    Write-Host "2. Note the API Gateway endpoint URL from outputs"
    Write-Host "3. Test your endpoints"
} else {
    Write-Host "Deployment failed" -ForegroundColor Red
}
