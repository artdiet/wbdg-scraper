# Security Guidelines

## Token and Credential Management

### ⚠️ **CRITICAL: Never Commit Secrets**

This repository is designed to be safe for public sharing. Follow these guidelines:

### **1. Environment Variables**

```bash
# Copy the example file
cp .env.example .env

# Edit with your actual credentials
nano .env

# The .env file is in .gitignore and will NOT be committed
```

### **2. For Development**

```bash
# Load environment variables
source .env

# Or use with Docker
docker run --env-file .env wbdg-scraper
```

### **3. For Production Deployment**

#### **Docker**
```bash
# Use environment variables directly
docker run -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
           -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
           wbdg-scraper
```

#### **Kubernetes**
```yaml
# Use Kubernetes secrets
apiVersion: v1
kind: Secret
metadata:
  name: wbdg-secrets
type: Opaque
data:
  aws-access-key-id: <base64-encoded-key>
  aws-secret-access-key: <base64-encoded-secret>
```

#### **Cloud Services**
- **AWS**: Use IAM roles and instance profiles
- **Azure**: Use Managed Identity
- **GCP**: Use Workload Identity
- **All**: Use respective secret management services

### **4. Files That Are NEVER Committed**

The `.gitignore` file excludes:
- `.env` files
- `*.pem`, `*.key` files
- `service-account*.json`
- `credentials.json`
- `config.ini`
- `secrets.yaml`

### **5. Best Practices**

1. **Rotate credentials regularly**
2. **Use least-privilege access policies**
3. **Monitor access logs**
4. **Use secret scanning tools**
5. **Never hardcode credentials in source code**

### **6. Emergency Procedure**

If credentials are accidentally committed:

1. **Immediately rotate/revoke the exposed credentials**
2. **Remove from git history**: `git filter-branch` or BFG Repo-Cleaner
3. **Force push**: `git push --force-with-lease`
4. **Notify team members to re-clone**

### **7. Verification**

Before pushing to GitHub, always run:

```bash
# Check for potential secrets
git log --oneline -p | grep -i "key\|token\|password\|secret"

# Ensure .env is ignored
git status --ignored
```

## Reporting Security Issues

Report security vulnerabilities to: [your-security-contact@dtriq.com]

**Do not** open public GitHub issues for security vulnerabilities.