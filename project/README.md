# Profile and private document upload demo

The app is split into four containers:

1. Profile-entry frontend (Nginx static site)
2. Document-upload frontend (Nginx static site)
3. Flask API backend
4. PostgreSQL database

Uploaded file bytes go to a **private AWS S3 bucket**. PostgreSQL stores the profile and document metadata (S3 object key, content type, timestamps, status). No document download endpoint is exposed. The backend accepts JPG, PNG, and PDF files up to 5 MB, checks their file signatures, uses generated S3 object keys, and requests S3 server-side encryption.

## AWS setup

1. Create an S3 bucket in your desired AWS region. Turn on **Block all public access**, bucket versioning if required by your retention policy, and default encryption.
2. Grant the backend workload only `s3:PutObject` and `s3:DeleteObject` on the bucket's `profile-documents/*` prefix. Delete permission is used to clean up an S3 object if its database transaction fails.
3. Configure credentials using an AWS profile for local Docker Compose, or workload identity (for example, EKS Pod Identity / IRSA) in Kubernetes. Do not put AWS credentials in frontend files, images, or committed manifests.

The application does not store or extract the Aadhaar number, original filename, or document bytes in PostgreSQL.

## Run with Docker Compose on Windows

Install Docker Desktop and configure an AWS CLI profile with access to the private bucket. From PowerShell in this folder:

```powershell
Copy-Item .env.example .env
notepad .env
```

Set `S3_BUCKET` to your bucket and replace `POSTGRES_PASSWORD` with a strong local password. Then run:

```powershell
docker compose up --build
```

Open <http://localhost:8080>. Keep Docker Desktop and the Compose services running while you use the app. Stop services with `Ctrl+C`, then `docker compose down`; the PostgreSQL data volume remains. `docker compose down -v` deletes the database volume.

Compose mounts the local AWS CLI files read-only from `%USERPROFILE%\.aws`. Set `AWS_PROFILE` in `.env` if the profile is not named `default`. The machine or container must be able to reach AWS and the configured bucket.

## Build the images

Run from this folder after Docker Desktop is running:

```powershell
docker build -f backend.Dockerfile -t profile-api:latest .
docker build -f frontend\profile\Dockerfile -t profile-ui:latest frontend\profile
docker build -f frontend\upload\Dockerfile -t upload-ui:latest frontend\upload
```

The fourth image is the upstream `postgres:16-alpine` image, pulled by Compose or Kubernetes; AWS S3 is an external managed service, not a container.

## Deploy to Kubernetes

These manifests expect an existing cluster, an NGINX Ingress Controller, a default StorageClass for the PostgreSQL volume, and AWS workload identity configured for the `profile-api` service account.

1. Set the bucket and region in `k8s\namespace.yaml`. For EKS, annotate the `profile-api` service account with the IAM role for the limited S3 permissions above.
2. Create the namespace and a database Secret. Replace the placeholder password with a strong generated value; do not commit the Secret:

```powershell
kubectl apply -f k8s\namespace.yaml
kubectl create secret generic profile-db-credentials -n profile-app --from-literal=username=profile_app --from-literal=password='<replace-with-a-strong-password>'
```

3. Build and make the three application images available to every cluster node. For a local Docker Desktop cluster, use the same local Docker daemon. For a remote cluster, push to your private registry and update the image names in `k8s\backend.yaml` and `k8s\frontends.yaml`.
4. Apply the remaining resources:

```powershell
kubectl apply -f k8s\database.yaml
kubectl apply -f k8s\backend.yaml
kubectl apply -f k8s\frontends.yaml
kubectl apply -f k8s\ingress.yaml
kubectl get pods,services,ingress -n profile-app
```

Configure DNS (or a local hosts entry) for `profile.example.test` to reach the ingress controller, then open `http://profile.example.test`. The sample ingress has no TLS configuration; set up HTTPS before any deployment beyond isolated development.

PostgreSQL uses a StatefulSet and persistent volume claim. Back up the database and test restore procedures before using persistent data.

## Local API tests

Tests use an in-memory SQLite database and a fake S3 client; they do not contact AWS or need PostgreSQL:

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## Important privacy and security limitations

This is a deployment prototype, **not a production identity-document system**. It has no user authentication or authorization, and the sample ingress has no TLS. A profile ID is not a secure access credential. Use dummy documents only. Before handling real identity documents, confirm lawful purpose/retention requirements and add authentication, per-user authorization, HTTPS, audit logging, retention/deletion controls, encrypted database storage/backups, monitoring, and a security/privacy review. Apply encryption-at-rest and backup policies to the database volume. Keep the S3 bucket private and use workload identity instead of long-lived AWS keys.
