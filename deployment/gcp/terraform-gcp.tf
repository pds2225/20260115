# HS Code Export Analyzer - GCP Terraform Configuration

terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "your-terraform-state-bucket"
    prefix = "hs-code-analyzer"
  }
}

# Variables
variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "asia-northeast3"
}

variable "environment" {
  description = "Environment (dev/staging/prod)"
  type        = string
  default     = "staging"
}

# Provider
provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "cloudrun.googleapis.com",
    "redis.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
    "monitoring.googleapis.com",
  ])

  service            = each.value
  disable_on_destroy = false
}

# VPC Network
resource "google_compute_network" "vpc" {
  name                    = "${var.environment}-hs-code-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = "${var.environment}-hs-code-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.vpc.id

  private_ip_google_access = true
}

# VPC Access Connector (for Cloud Run to access Redis)
resource "google_vpc_access_connector" "connector" {
  name          = "${var.environment}-hs-code-connector"
  region        = var.region
  network       = google_compute_network.vpc.name
  ip_cidr_range = "10.8.0.0/28"

  depends_on = [google_project_service.required_apis]
}

# Redis (Memorystore)
resource "google_redis_instance" "cache" {
  name           = "${var.environment}-hs-code-redis"
  tier           = var.environment == "prod" ? "STANDARD_HA" : "BASIC"
  memory_size_gb = var.environment == "prod" ? 5 : 1
  region         = var.region

  authorized_network = google_compute_network.vpc.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"

  redis_version = "REDIS_7_0"
  display_name  = "HS Code Analyzer Cache"

  depends_on = [google_project_service.required_apis]
}

# Secret Manager for sensitive data
resource "google_secret_manager_secret" "api_secret_key" {
  secret_id = "${var.environment}-api-secret-key"

  replication {
    automatic = true
  }

  depends_on = [google_project_service.required_apis]
}

# Cloud Storage Bucket for data
resource "google_storage_bucket" "data" {
  name          = "${var.project_id}-${var.environment}-hs-code-data"
  location      = var.region
  force_destroy = var.environment != "prod"

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }
}

# Service Account for Cloud Run
resource "google_service_account" "cloud_run_sa" {
  account_id   = "${var.environment}-hs-code-run-sa"
  display_name = "Cloud Run Service Account for HS Code Analyzer"
}

# IAM roles for Service Account
resource "google_project_iam_member" "cloud_run_sa_roles" {
  for_each = toset([
    "roles/secretmanager.secretAccessor",
    "roles/storage.objectViewer",
    "roles/redis.editor",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# Cloud Run Service
resource "google_cloud_run_service" "api" {
  name     = "${var.environment}-hs-code-api"
  location = var.region

  template {
    spec {
      service_account_name = google_service_account.cloud_run_sa.email

      containers {
        image = "gcr.io/${var.project_id}/hs-code-analyzer:${var.environment}"

        ports {
          container_port = 8000
        }

        resources {
          limits = {
            cpu    = var.environment == "prod" ? "2" : "1"
            memory = var.environment == "prod" ? "2Gi" : "1Gi"
          }
        }

        env {
          name  = "ENVIRONMENT"
          value = var.environment
        }

        env {
          name  = "REDIS_HOST"
          value = google_redis_instance.cache.host
        }

        env {
          name  = "REDIS_PORT"
          value = tostring(google_redis_instance.cache.port)
        }

        env {
          name  = "GCS_BUCKET"
          value = google_storage_bucket.data.name
        }
      }

      container_concurrency = 80
      timeout_seconds       = 300
    }

    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale"      = var.environment == "prod" ? "2" : "1"
        "autoscaling.knative.dev/maxScale"      = var.environment == "prod" ? "10" : "5"
        "run.googleapis.com/vpc-access-connector" = google_vpc_access_connector.connector.id
        "run.googleapis.com/vpc-access-egress"   = "private-ranges-only"
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [google_project_service.required_apis]
}

# Allow unauthenticated access (adjust for production)
resource "google_cloud_run_service_iam_member" "allow_unauthenticated" {
  count = var.environment != "prod" ? 1 : 0

  service  = google_cloud_run_service.api.name
  location = google_cloud_run_service.api.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Cloud Monitoring Alert Policy
resource "google_monitoring_alert_policy" "high_error_rate" {
  display_name = "${var.environment} HS Code API - High Error Rate"
  combiner     = "OR"

  conditions {
    display_name = "Error rate > 5%"

    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${google_cloud_run_service.api.name}\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 5

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = []

  depends_on = [google_project_service.required_apis]
}

# Outputs
output "cloud_run_url" {
  description = "Cloud Run service URL"
  value       = google_cloud_run_service.api.status[0].url
}

output "redis_host" {
  description = "Redis host"
  value       = google_redis_instance.cache.host
  sensitive   = true
}

output "redis_port" {
  description = "Redis port"
  value       = google_redis_instance.cache.port
}

output "gcs_bucket" {
  description = "GCS bucket name"
  value       = google_storage_bucket.data.name
}

output "service_account_email" {
  description = "Service account email"
  value       = google_service_account.cloud_run_sa.email
}
