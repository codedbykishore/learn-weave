#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PROJECT_NAME="${PROJECT_NAME:-learnweave}"
REGION="${AWS_REGION:-us-east-1}"
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.large}"
BEDROCK_MODEL_ID="${BEDROCK_MODEL_ID:-bedrock/us.anthropic.claude-3-5-sonnet-20240620-v1:0}"

ROLE_NAME="${ROLE_NAME:-learnweave-ec2-role}"
INSTANCE_PROFILE_NAME="${INSTANCE_PROFILE_NAME:-learnweave-ec2-profile}"
SECURITY_GROUP_NAME="${SECURITY_GROUP_NAME:-learnweave-ec2-sg}"

for cmd in aws tar openssl curl; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd"
    exit 1
  fi
done

echo "Using AWS region: $REGION"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
echo "Using AWS account: $ACCOUNT_ID"

DEPLOY_BUCKET="${DEPLOY_BUCKET:-${PROJECT_NAME}-deploy-${ACCOUNT_ID}-${REGION}}"
S3_BUCKET_IMAGES="${S3_BUCKET_IMAGES:-${PROJECT_NAME}-images-${ACCOUNT_ID}-${REGION}}"
S3_BUCKET_UPLOADS="${S3_BUCKET_UPLOADS:-${PROJECT_NAME}-uploads-${ACCOUNT_ID}-${REGION}}"
S3_BUCKET_EXPORTS="${S3_BUCKET_EXPORTS:-${PROJECT_NAME}-exports-${ACCOUNT_ID}-${REGION}}"

create_bucket_if_missing() {
  local bucket_name="$1"
  local exists
  exists="$(aws s3api head-bucket --bucket "$bucket_name" 2>/dev/null && echo yes || echo no)"
  if [[ "$exists" == "yes" ]]; then
    echo "Bucket already exists: $bucket_name"
    return
  fi

  if [[ "$REGION" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "$bucket_name" >/dev/null
  else
    aws s3api create-bucket \
      --bucket "$bucket_name" \
      --region "$REGION" \
      --create-bucket-configuration "LocationConstraint=$REGION" >/dev/null
  fi
  echo "Created bucket: $bucket_name"
}

echo "Ensuring S3 buckets exist..."
create_bucket_if_missing "$DEPLOY_BUCKET"
create_bucket_if_missing "$S3_BUCKET_IMAGES"
create_bucket_if_missing "$S3_BUCKET_UPLOADS"
create_bucket_if_missing "$S3_BUCKET_EXPORTS"

echo "Packaging project artifact..."
ARTIFACT_NAME="${PROJECT_NAME}-$(date +%Y%m%d-%H%M%S).tar.gz"
ARTIFACT_PATH="/tmp/$ARTIFACT_NAME"
ARTIFACT_KEY="releases/$ARTIFACT_NAME"

tar \
  --exclude='.git' \
  --exclude='frontend/node_modules' \
  --exclude='backend/.venv' \
  --exclude='backend/generated_images' \
  --exclude='logs' \
  -czf "$ARTIFACT_PATH" .

aws s3 cp "$ARTIFACT_PATH" "s3://$DEPLOY_BUCKET/$ARTIFACT_KEY" --region "$REGION" >/dev/null
echo "Uploaded artifact: s3://$DEPLOY_BUCKET/$ARTIFACT_KEY"

echo "Ensuring IAM role and instance profile..."
TRUST_POLICY_FILE="$(mktemp)"
cat > "$TRUST_POLICY_FILE" <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
JSON

if ! aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  aws iam create-role --role-name "$ROLE_NAME" --assume-role-policy-document "file://$TRUST_POLICY_FILE" >/dev/null
  echo "Created role: $ROLE_NAME"
fi

for policy_arn in \
  arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore \
  arn:aws:iam::aws:policy/AmazonS3FullAccess \
  arn:aws:iam::aws:policy/AmazonBedrockFullAccess; do
  aws iam attach-role-policy --role-name "$ROLE_NAME" --policy-arn "$policy_arn" >/dev/null || true
done

if ! aws iam get-instance-profile --instance-profile-name "$INSTANCE_PROFILE_NAME" >/dev/null 2>&1; then
  aws iam create-instance-profile --instance-profile-name "$INSTANCE_PROFILE_NAME" >/dev/null
  echo "Created instance profile: $INSTANCE_PROFILE_NAME"
fi

if ! aws iam get-instance-profile --instance-profile-name "$INSTANCE_PROFILE_NAME" \
  --query "InstanceProfile.Roles[?RoleName=='$ROLE_NAME'] | length(@)" --output text | grep -q '^1$'; then
  aws iam add-role-to-instance-profile --instance-profile-name "$INSTANCE_PROFILE_NAME" --role-name "$ROLE_NAME" >/dev/null || true
fi

echo "Waiting for IAM propagation..."
sleep 12

echo "Ensuring security group exists..."
VPC_ID="$(aws ec2 describe-vpcs --region "$REGION" --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)"
if [[ "$VPC_ID" == "None" || -z "$VPC_ID" ]]; then
  echo "No default VPC found. Please provide a VPC and subnet configuration."
  exit 1
fi

SG_ID="$(aws ec2 describe-security-groups \
  --region "$REGION" \
  --filters Name=group-name,Values="$SECURITY_GROUP_NAME" Name=vpc-id,Values="$VPC_ID" \
  --query 'SecurityGroups[0].GroupId' \
  --output text)"

if [[ "$SG_ID" == "None" || -z "$SG_ID" ]]; then
  SG_ID="$(aws ec2 create-security-group \
    --region "$REGION" \
    --group-name "$SECURITY_GROUP_NAME" \
    --description "LearnWeave EC2 security group" \
    --vpc-id "$VPC_ID" \
    --query 'GroupId' --output text)"
  echo "Created security group: $SG_ID"
fi

add_ingress_rule() {
  local port="$1"
  aws ec2 authorize-security-group-ingress \
    --region "$REGION" \
    --group-id "$SG_ID" \
    --protocol tcp \
    --port "$port" \
    --cidr 0.0.0.0/0 >/dev/null 2>&1 || true
}

add_ingress_rule 80
add_ingress_rule 443
add_ingress_rule 8000

echo "Building user-data bootstrap script..."
MYSQL_ROOT_PASSWORD="$(openssl rand -hex 18)"
DB_PASSWORD="$(openssl rand -hex 18)"
SECRET_KEY="$(openssl rand -hex 32)"
SESSION_SECRET_KEY="$(openssl rand -hex 32)"

USER_DATA_FILE="$(mktemp)"
cat > "$USER_DATA_FILE" <<EOF
#!/bin/bash
set -euxo pipefail

dnf update -y
dnf install -y docker tar curl awscli
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/download/v2.29.2/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
systemctl enable docker
systemctl start docker

mkdir -p /opt/learnweave
cd /opt/learnweave
aws s3 cp s3://$DEPLOY_BUCKET/$ARTIFACT_KEY /opt/learnweave/source.tar.gz --region $REGION
tar -xzf /opt/learnweave/source.tar.gz

TOKEN=\$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
PUBLIC_IP=\$(curl -H "X-aws-ec2-metadata-token: \$TOKEN" -s http://169.254.169.254/latest/meta-data/public-ipv4)

cat > /opt/learnweave/.env <<ENVVARS
VITE_API_URL=http://\$PUBLIC_IP:8000/api
BACKEND_BASE_URL=http://\$PUBLIC_IP:8000
FRONTEND_BASE_URL=http://\$PUBLIC_IP
CORS_ORIGINS=http://\$PUBLIC_IP,http://\$PUBLIC_IP:80,http://\$PUBLIC_IP:5173
DB_USER=learnweave_user
DB_PASSWORD=$DB_PASSWORD
DB_NAME=learnweave_db
MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD
ENVVARS

cat > /opt/learnweave/backend/.env.aws <<BACKENDENV
SECRET_KEY=$SECRET_KEY
SESSION_SECRET_KEY=$SESSION_SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES=20
REFRESH_TOKEN_EXPIRE_MINUTES=360000
SECURE_COOKIE=false

DB_USER=learnweave_user
DB_PASSWORD=$DB_PASSWORD
DB_HOST=mysql
DB_PORT=3306
DB_NAME=learnweave_db

USE_FIRESTORE=false
USE_CLOUD_STORAGE=false
USE_S3_STORAGE=true
S3_BUCKET_IMAGES=$S3_BUCKET_IMAGES
S3_BUCKET_UPLOADS=$S3_BUCKET_UPLOADS
S3_BUCKET_EXPORTS=$S3_BUCKET_EXPORTS
S3_USE_PRESIGNED_URLS=true

LLM_PROVIDER=bedrock
AWS_REGION=$REGION
BEDROCK_REGION=$REGION
BEDROCK_MODEL_ID=$BEDROCK_MODEL_ID

CHROMA_DB_URL=http://chromadb:8000
BACKEND_BASE_URL=http://\$PUBLIC_IP:8000
PUBLIC_BASE_URL=http://\$PUBLIC_IP:8000
FRONTEND_BASE_URL=http://\$PUBLIC_IP
PUBLIC_FRONTEND_URL=http://\$PUBLIC_IP
CORS_ORIGINS=http://\$PUBLIC_IP,http://\$PUBLIC_IP:80,http://\$PUBLIC_IP:5173

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
DISCORD_CLIENT_ID=
DISCORD_CLIENT_SECRET=

AGENT_DEBUG_MODE=false
BACKENDENV

cd /opt/learnweave
docker compose -f docker-compose.aws.yml --env-file .env up -d --build
EOF

AMI_ID="$(aws ssm get-parameter \
  --region "$REGION" \
  --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-6.1-x86_64 \
  --query 'Parameter.Value' --output text)"

echo "Launching EC2 instance..."
INSTANCE_ID="$(aws ec2 run-instances \
  --region "$REGION" \
  --image-id "$AMI_ID" \
  --instance-type "$INSTANCE_TYPE" \
  --iam-instance-profile Name="$INSTANCE_PROFILE_NAME" \
  --security-group-ids "$SG_ID" \
  --associate-public-ip-address \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${PROJECT_NAME}-ec2}]" \
  --user-data "file://$USER_DATA_FILE" \
  --query 'Instances[0].InstanceId' --output text)"

echo "Instance created: $INSTANCE_ID"

echo "Waiting for instance to become healthy..."
aws ec2 wait instance-running --region "$REGION" --instance-ids "$INSTANCE_ID"
aws ec2 wait instance-status-ok --region "$REGION" --instance-ids "$INSTANCE_ID"

PUBLIC_IP="$(aws ec2 describe-instances \
  --region "$REGION" \
  --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)"

echo "Instance public IP: $PUBLIC_IP"
echo "Waiting for containers to boot (this can take several minutes)..."

FRONTEND_URL="http://$PUBLIC_IP"
BACKEND_URL="http://$PUBLIC_IP:8000"

MAX_RETRIES=60
SLEEP_SECONDS=10

for i in $(seq 1 "$MAX_RETRIES"); do
  FRONTEND_CODE="$(curl -s -o /dev/null -w '%{http_code}' "$FRONTEND_URL/health" || true)"
  BACKEND_CODE="$(curl -s -o /dev/null -w '%{http_code}' "$BACKEND_URL/" || true)"
  if [[ "$FRONTEND_CODE" == "200" && "$BACKEND_CODE" == "200" ]]; then
    echo "Deployment is healthy."
    break
  fi
  echo "Health check attempt $i/$MAX_RETRIES (frontend=$FRONTEND_CODE backend=$BACKEND_CODE)"
  sleep "$SLEEP_SECONDS"
done

echo ""
echo "==========================================="
echo "LearnWeave deployed on AWS EC2"
echo "==========================================="
echo "Frontend: $FRONTEND_URL"
echo "Backend:  $BACKEND_URL"
echo "Instance: $INSTANCE_ID"
echo "Region:   $REGION"
echo "Bedrock Model: $BEDROCK_MODEL_ID"
echo "S3 Buckets:"
echo "  - $S3_BUCKET_IMAGES"
echo "  - $S3_BUCKET_UPLOADS"
echo "  - $S3_BUCKET_EXPORTS"
echo ""
echo "Note: OAuth providers are not configured in this automatic deploy."
