# Cloud Storage Configuration Examples

## Overview
The WBDG scraper can be configured to store documents in various cloud storage backends. This document provides practical examples for each supported platform.

## AWS S3 Configuration

### Environment Setup
```bash
export WBDG_STORAGE_TYPE=s3
export WBDG_STORAGE_BUCKET=wbdg-documents
export WBDG_STORAGE_PREFIX=ufc-pdfs/
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1
```

### IAM Policy Example
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::wbdg-documents",
                "arn:aws:s3:::wbdg-documents/*"
            ]
        }
    ]
}
```

### Docker Deployment
```bash
docker run --rm \
    -e WBDG_STORAGE_TYPE=s3 \
    -e WBDG_STORAGE_BUCKET=wbdg-documents \
    -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
    -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
    -e AWS_DEFAULT_REGION=us-east-1 \
    wbdg-scraper
```

### Terraform Configuration
```hcl
resource "aws_s3_bucket" "wbdg_documents" {
  bucket = "wbdg-documents"
}

resource "aws_s3_bucket_versioning" "wbdg_versioning" {
  bucket = aws_s3_bucket.wbdg_documents.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_iam_user" "wbdg_scraper" {
  name = "wbdg-scraper"
}

resource "aws_iam_policy" "wbdg_policy" {
  name = "WBDGScraperPolicy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.wbdg_documents.arn,
          "${aws_s3_bucket.wbdg_documents.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_user_policy_attachment" "wbdg_attachment" {
  user       = aws_iam_user.wbdg_scraper.name
  policy_arn = aws_iam_policy.wbdg_policy.arn
}
```

## Azure Blob Storage Configuration

### Environment Setup
```bash
export WBDG_STORAGE_TYPE=azure
export AZURE_STORAGE_ACCOUNT=wbdgdocuments
export AZURE_STORAGE_KEY=...
export AZURE_CONTAINER_NAME=ufc-pdfs
```

### Azure CLI Setup
```bash
# Create storage account
az storage account create \
    --name wbdgdocuments \
    --resource-group myResourceGroup \
    --location eastus \
    --sku Standard_LRS

# Create container
az storage container create \
    --name ufc-pdfs \
    --account-name wbdgdocuments
```

### Docker Deployment
```bash
docker run --rm \
    -e WBDG_STORAGE_TYPE=azure \
    -e AZURE_STORAGE_ACCOUNT=wbdgdocuments \
    -e AZURE_STORAGE_KEY=$AZURE_STORAGE_KEY \
    -e AZURE_CONTAINER_NAME=ufc-pdfs \
    wbdg-scraper
```

### Azure Resource Manager Template
```json
{
    "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
    "contentVersion": "1.0.0.0",
    "parameters": {
        "storageAccountName": {
            "type": "string",
            "defaultValue": "wbdgdocuments"
        }
    },
    "resources": [
        {
            "type": "Microsoft.Storage/storageAccounts",
            "apiVersion": "2021-04-01",
            "name": "[parameters('storageAccountName')]",
            "location": "[resourceGroup().location]",
            "sku": {
                "name": "Standard_LRS"
            },
            "kind": "StorageV2",
            "properties": {
                "accessTier": "Hot"
            },
            "resources": [
                {
                    "type": "blobServices/containers",
                    "apiVersion": "2021-04-01",
                    "name": "default/ufc-pdfs",
                    "dependsOn": [
                        "[parameters('storageAccountName')]"
                    ]
                }
            ]
        }
    ]
}
```

## Google Cloud Storage Configuration

### Environment Setup
```bash
export WBDG_STORAGE_TYPE=gcs
export WBDG_STORAGE_BUCKET=wbdg-documents
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
export GCS_PROJECT_ID=my-project-id
```

### Service Account Setup
```bash
# Create service account
gcloud iam service-accounts create wbdg-scraper \
    --display-name="WBDG Scraper Service Account"

# Create bucket
gsutil mb gs://wbdg-documents

# Grant permissions
gsutil iam ch serviceAccount:wbdg-scraper@my-project-id.iam.gserviceaccount.com:objectAdmin gs://wbdg-documents

# Create key
gcloud iam service-accounts keys create ~/wbdg-scraper-key.json \
    --iam-account=wbdg-scraper@my-project-id.iam.gserviceaccount.com
```

### Docker Deployment
```bash
docker run --rm \
    -v ~/wbdg-scraper-key.json:/tmp/key.json \
    -e WBDG_STORAGE_TYPE=gcs \
    -e WBDG_STORAGE_BUCKET=wbdg-documents \
    -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/key.json \
    -e GCS_PROJECT_ID=my-project-id \
    wbdg-scraper
```

### Terraform Configuration
```hcl
resource "google_storage_bucket" "wbdg_documents" {
  name     = "wbdg-documents"
  location = "US"
  
  versioning {
    enabled = true
  }
  
  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }
}

resource "google_service_account" "wbdg_scraper" {
  account_id   = "wbdg-scraper"
  display_name = "WBDG Scraper Service Account"
}

resource "google_storage_bucket_iam_member" "wbdg_object_admin" {
  bucket = google_storage_bucket.wbdg_documents.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.wbdg_scraper.email}"
}

resource "google_service_account_key" "wbdg_scraper_key" {
  service_account_id = google_service_account.wbdg_scraper.name
}
```

## Kubernetes Deployment Examples

### AWS EKS with S3
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: wbdg-scraper
spec:
  schedule: "0 6 * * *"  # Daily at 6 AM
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: wbdg-scraper
          containers:
          - name: wbdg-scraper
            image: wbdg-scraper:latest
            env:
            - name: WBDG_STORAGE_TYPE
              value: "s3"
            - name: WBDG_STORAGE_BUCKET
              value: "wbdg-documents"
            - name: AWS_DEFAULT_REGION
              value: "us-east-1"
            volumeMounts:
            - name: metadata-volume
              mountPath: /app/output/metadata
          volumes:
          - name: metadata-volume
            persistentVolumeClaim:
              claimName: wbdg-metadata-pvc
          restartPolicy: OnFailure
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: wbdg-metadata-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
```

### Azure AKS with Blob Storage
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: wbdg-scraper
spec:
  schedule: "0 6 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: wbdg-scraper
            image: wbdg-scraper:latest
            env:
            - name: WBDG_STORAGE_TYPE
              value: "azure"
            - name: AZURE_STORAGE_ACCOUNT
              valueFrom:
                secretKeyRef:
                  name: azure-storage-secret
                  key: account
            - name: AZURE_STORAGE_KEY
              valueFrom:
                secretKeyRef:
                  name: azure-storage-secret
                  key: key
            - name: AZURE_CONTAINER_NAME
              value: "ufc-pdfs"
          restartPolicy: OnFailure
---
apiVersion: v1
kind: Secret
metadata:
  name: azure-storage-secret
type: Opaque
data:
  account: <base64-encoded-account-name>
  key: <base64-encoded-storage-key>
```

### Google GKE with Cloud Storage
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: wbdg-scraper
spec:
  schedule: "0 6 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: wbdg-scraper-ksa
          containers:
          - name: wbdg-scraper
            image: wbdg-scraper:latest
            env:
            - name: WBDG_STORAGE_TYPE
              value: "gcs"
            - name: WBDG_STORAGE_BUCKET
              value: "wbdg-documents"
            - name: GCS_PROJECT_ID
              value: "my-project-id"
          restartPolicy: OnFailure
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: wbdg-scraper-ksa
  annotations:
    iam.gke.io/gcp-service-account: wbdg-scraper@my-project-id.iam.gserviceaccount.com
```

## Cost Optimization Strategies

### Storage Classes
- **AWS S3**: Use Intelligent Tiering for automatic cost optimization
- **Azure Blob**: Use Hot tier for frequently accessed, Cool for archives
- **GCS**: Use Standard for active data, Nearline/Coldline for archives

### Lifecycle Policies
```bash
# AWS S3 Lifecycle Policy
{
  "Rules": [
    {
      "ID": "WBDGArchive",
      "Status": "Enabled",
      "Transitions": [
        {
          "Days": 30,
          "StorageClass": "STANDARD_IA"
        },
        {
          "Days": 90,
          "StorageClass": "GLACIER"
        }
      ]
    }
  ]
}
```

### Monitoring and Alerts
- Set up billing alerts for storage costs
- Monitor download patterns and adjust retention policies
- Use compression for large PDF collections
- Implement deduplication to avoid storing identical files

## Performance Tuning

### Network Optimization
- Use regional storage closest to scraper deployment
- Configure appropriate bandwidth limits
- Implement connection pooling for high-throughput scenarios

### Concurrent Uploads
- Increase `WBDG_CONCURRENT_DOWNLOADS` for faster processing
- Monitor storage service rate limits
- Implement exponential backoff for throttling

### Caching Strategies
- Use CDN (CloudFront, Azure CDN, Cloud CDN) for frequently accessed documents
- Implement local caching for development environments
- Consider edge locations for global access patterns