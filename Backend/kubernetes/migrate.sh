#!/bin/bash

# Database Migration Script for Kubernetes
# Usage: ./migrate.sh [command] [options]

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

NAMESPACE=${NAMESPACE:-default}
JOB_NAME="db-migration-job"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if a job exists
job_exists() {
    kubectl get job $JOB_NAME -n $NAMESPACE >/dev/null 2>&1
}

# Function to wait for job completion
wait_for_job() {
    print_status "Waiting for migration job to complete..."
    kubectl wait --for=condition=complete job/$JOB_NAME -n $NAMESPACE --timeout=300s
    if [ $? -eq 0 ]; then
        print_status "Migration completed successfully!"
        kubectl logs job/$JOB_NAME -n $NAMESPACE
    else
        print_error "Migration failed!"
        kubectl logs job/$JOB_NAME -n $NAMESPACE
        exit 1
    fi
}

# Function to clean up old jobs
cleanup_jobs() {
    print_status "Cleaning up old migration jobs..."
    kubectl delete job $JOB_NAME -n $NAMESPACE --ignore-not-found=true
}

# Function to run migration
run_migration() {
    print_status "Starting database migration..."
    
    # Clean up any existing jobs
    cleanup_jobs
    
    # Apply the migration job using the correct path
    kubectl apply -f "$SCRIPT_DIR/migration-job.yaml" -n $NAMESPACE
    
    # Wait for completion
    wait_for_job
    
    # Clean up
    cleanup_jobs
}

# Function to check migration status
check_status() {
    print_status "Checking migration status..."
    
    # Get current revision from database
    CURRENT_REV=$(kubectl run migration-status-check --rm -i --restart=Never \
        --image=webbpulse/carmodpicker:backend-latest \
        --env="ALEMBIC_DATABASE_URL=$ALEMBIC_DATABASE_URL" \
        --command -- alembic current 2>/dev/null || echo "unknown")
    
    # Get latest revision from files
    LATEST_REV=$(kubectl run migration-latest-check --rm -i --restart=Never \
        --image=webbpulse/carmodpicker:backend-latest \
        --command -- alembic heads --verbose 2>/dev/null | head -n1 | cut -d' ' -f1 || echo "unknown")
    
    echo "Current revision: $CURRENT_REV"
    echo "Latest revision: $LATEST_REV"
    
    if [ "$CURRENT_REV" = "$LATEST_REV" ]; then
        print_status "Database is up to date!"
    else
        print_warning "Database is not up to date. Run './migrate.sh run' to update."
    fi
}

# Function to show migration history
show_history() {
    print_status "Showing migration history..."
    kubectl run migration-history --rm -i --restart=Never \
        --image=webbpulse/carmodpicker:backend-latest \
        --env="ALEMBIC_DATABASE_URL=$ALEMBIC_DATABASE_URL" \
        --command -- alembic history --verbose
}

# Function to show help
show_help() {
    echo "Database Migration Script for Kubernetes"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  run       Run database migrations"
    echo "  status    Check migration status"
    echo "  history   Show migration history"
    echo "  help      Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  NAMESPACE         Kubernetes namespace (default: default)"
    echo "  ALEMBIC_DATABASE_URL Database URL for migration status check"
    echo ""
}

# Main script logic
case "${1:-help}" in
    "run")
        run_migration
        ;;
    "status")
        check_status
        ;;
    "history")
        show_history
        ;;
    "help"|"--help"|"-h")
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac 