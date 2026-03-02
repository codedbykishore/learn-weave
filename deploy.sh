#!/bin/bash

# GCP Quick Deployment Script for LearnWeave
# This script deploys your application to Google Cloud Run with Firestore

set -e  # Exit on error

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-sticky-net-485205}"
REGION="${GOOGLE_CLOUD_REGION:-us-central1}"

echo "🚀 Deploying LearnWeave to Google Cloud"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo ""

# Check gcloud authentication
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ Not authenticated with gcloud. Run: gcloud auth login"
    exit 1
fi

# Set project
gcloud config set project "$PROJECT_ID"

# Enable required APIs
echo "📋 Enabling required APIs..."
gcloud services enable \
    run.googleapis.com \
    firestore.googleapis.com \
    storage.googleapis.com \
    artifactregistry.googleapis.com \
    cloudscheduler.googleapis.com \
    secretmanager.googleapis.com \
    --quiet

# Create Firestore database if needed
echo "🔥 Setting up Firestore..."
if ! gcloud firestore databases describe --database="(default)" &>/dev/null; then
    echo "Creating Firestore database in Native mode..."
    gcloud firestore databases create --location="$REGION" --type=firestore-native
else
    echo "Firestore database already exists"
fi

# Create Cloud Storage buckets
echo "🗄️  Creating Storage buckets..."
BUCKET_IMAGES="${PROJECT_ID}-images"
BUCKET_UPLOADS="${PROJECT_ID}-uploads"
BUCKET_EXPORTS="${PROJECT_ID}-exports"

for bucket in "$BUCKET_IMAGES" "$BUCKET_UPLOADS" "$BUCKET_EXPORTS"; do
    if ! gsutil ls "gs://$bucket" &>/dev/null; then
        gsutil mb -l "$REGION" "gs://$bucket"
        echo "Created bucket: $bucket"
    else
        echo "Bucket already exists: $bucket"
    fi
done

# Make images bucket public
gsutil iam ch allUsers:objectViewer "gs://$BUCKET_IMAGES" || true

# Create Artifact Registry repository
echo "📦 Setting up Artifact Registry..."
REPO_NAME="learnweave"
if ! gcloud artifacts repositories describe "$REPO_NAME" --location="$REGION" &>/dev/null; then
    gcloud artifacts repositories create "$REPO_NAME" \
        --repository-format=docker \
        --location="$REGION" \
        --description="LearnWeave containers"
else
    echo "Repository already exists"
fi

# Configure Docker for Artifact Registry
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# Build and push backend image
echo "🐳 Building backend image..."
cd backend
IMAGE_BACKEND="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/backend:latest"
sudo docker build -f Dockerfile.production -t "$IMAGE_BACKEND" .
sudo docker push "$IMAGE_BACKEND"
cd ..

# Get OAuth credentials from user
echo ""
echo "⚠️  IMPORTANT: OAuth Configuration"
echo "You need to provide production OAuth credentials."
echo "Visit: https://console.cloud.google.com/apis/credentials"
echo ""
read -p "Enter Google OAuth Client ID: " GOOGLE_CLIENT_ID
read -sp "Enter Google OAuth Client Secret: " GOOGLE_CLIENT_SECRET
echo ""

# Store secrets in Secret Manager
echo "🔐 Storing secrets..."
echo -n "$GOOGLE_CLIENT_ID" | gcloud secrets create google-client-id --data-file=- --replication-policy=automatic || \
    echo -n "$GOOGLE_CLIENT_ID" | gcloud secrets versions add google-client-id --data-file=-

echo -n "$GOOGLE_CLIENT_SECRET" | gcloud secrets create google-client-secret --data-file=- --replication-policy=automatic || \
    echo -n "$GOOGLE_CLIENT_SECRET" | gcloud secrets versions add google-client-secret --data-file=-

# Generate JWT secret if not exists
JWT_SECRET=$(openssl rand -base64 32)
echo -n "$JWT_SECRET" | gcloud secrets create jwt-secret-key --data-file=- --replication-policy=automatic || true

# Deploy backend to Cloud Run
echo "🚀 Deploying backend to Cloud Run..."
gcloud run deploy learnweave-backend \
    --image="$IMAGE_BACKEND" \
    --platform=managed \
    --region="$REGION" \
    --allow-unauthenticated \
    --memory=2Gi \
    --cpu=2 \
    --timeout=300 \
    --min-instances=0 \
    --max-instances=10 \
    --set-env-vars="USE_FIRESTORE=true,\
USE_CLOUD_STORAGE=true,\
GOOGLE_CLOUD_PROJECT=$PROJECT_ID,\
GOOGLE_CLOUD_LOCATION=$REGION,\
GOOGLE_GENAI_USE_VERTEXAI=true,\
FIRESTORE_DATABASE=(default),\
GCS_BUCKET_IMAGES=$BUCKET_IMAGES,\
GCS_BUCKET_UPLOADS=$BUCKET_UPLOADS,\
GCS_BUCKET_EXPORTS=$BUCKET_EXPORTS,\
CORS_ORIGINS=*" \
    --set-secrets="GOOGLE_CLIENT_ID=google-client-id:latest,\
GOOGLE_CLIENT_SECRET=google-client-secret:latest,\
SECRET_KEY=jwt-secret-key:latest"

# Get backend URL
BACKEND_URL=$(gcloud run services describe learnweave-backend --region="$REGION" --format='value(status.url)')
echo ""
echo "✅ Backend deployed: $BACKEND_URL"

# Build and push frontend image
echo "🐳 Building frontend image..."
cd frontend
IMAGE_FRONTEND="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/frontend:latest"
sudo docker build \
    -f Dockerfile.production \
    --build-arg VITE_API_URL="$BACKEND_URL" \
    -t "$IMAGE_FRONTEND" .
sudo docker push "$IMAGE_FRONTEND"
cd ..

# Deploy frontend to Cloud Run
echo "🚀 Deploying frontend to Cloud Run..."
gcloud run deploy learnweave-frontend \
    --image="$IMAGE_FRONTEND" \
    --platform=managed \
    --region="$REGION" \
    --allow-unauthenticated \
    --memory=512Mi \
    --cpu=1 \
    --min-instances=0 \
    --max-instances=5

FRONTEND_URL=$(gcloud run services describe learnweave-frontend --region="$REGION" --format='value(status.url)')
echo ""
echo "✅ Frontend deployed: $FRONTEND_URL"

# Update CORS in backend
echo "🔄 Updating backend CORS..."
gcloud run services update learnweave-backend \
    --region="$REGION" \
    --update-env-vars="CORS_ORIGINS=$FRONTEND_URL,https://learnweave.ai,https://www.learnweave.ai,\
FRONTEND_BASE_URL=$FRONTEND_URL,\
CLOUD_RUN_SERVICE_URL=$BACKEND_URL"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 Deployment Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Backend:  $BACKEND_URL"
echo "Frontend: $FRONTEND_URL"
echo ""
echo "⚠️  NEXT STEPS:"
echo "1. Update OAuth redirect URIs in Google Console:"
echo "   - Add: ${BACKEND_URL}/api/auth/google/callback"
echo "   - Visit: https://console.cloud.google.com/apis/credentials"
echo ""
echo "2. Test your application:"
echo "   - Open: $FRONTEND_URL"
echo "   - Try OAuth login"
echo ""
echo "3. Set up custom domain (optional):"
echo "   - Map domain to Cloud Run services"
echo "   - Update OAuth URIs to use custom domain"
echo ""
echo "📊 Monitor your services:"
echo "   gcloud run services list --region=$REGION"
echo ""
echo "📝 View logs:"
echo "   gcloud run services logs read learnweave-backend --region=$REGION"
echo "   gcloud run services logs read learnweave-frontend --region=$REGION"
echo ""
