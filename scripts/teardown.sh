#!/usr/bin/env bash
set -e

# Teardown Script for AIFoundryAgent-ANF-SelfOps

if [ -z "$1" ]; then
    echo "Usage: $0 <resource-group>"
    echo "Example: $0 anf-selfops-rg"
    exit 1
fi

RG_NAME=$1

echo "WARNING: This will delete the resource group '$RG_NAME' and ALL resources within it."
read -p "Are you sure you want to proceed? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Teardown aborted by user."
    exit 1
fi

echo "Starting teardown of resource group: $RG_NAME..."
az group delete --name "$RG_NAME" --yes --no-wait

echo "Delete operation requested successfully."
echo "The resource group is being deleted in the background."
echo "You can check status with: az group show -n $RG_NAME"
