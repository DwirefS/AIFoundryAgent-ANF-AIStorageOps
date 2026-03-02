#!/usr/bin/env bash
set -e

# End-to-End Deployment Script for AIFoundryAgent-ANF-SelfOps
# Deploys ANF via Bicep, then creates AI Foundry components via CLI

if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <subscription-id> <resource-group> <location>"
    echo "Example: $0 xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx anf-selfops-rg eastus2"
    exit 1
fi

SUB_ID=$1
RG_NAME=$2
LOCATION=$3

# Naming conventions (using random string to ensure global uniqueness)
SUFFIX=$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom | head -c 5)
AOAI_NAME="anfselfops-aoai-${SUFFIX}"
HUB_NAME="anfselfops-hub-${SUFFIX}"
PROJECT_NAME="anfselfops-project-${SUFFIX}"

az account set --subscription "$SUB_ID"

echo "======================================================"
echo "1. Creating Resource Group: $RG_NAME in $LOCATION"
echo "======================================================"
az group create --name "$RG_NAME" --location "$LOCATION" -o none

echo "======================================================"
echo "2. Deploying Base Infrastructure (VNet, ANF, Identity) via Bicep"
echo "======================================================"
az deployment group create \
    --resource-group "$RG_NAME" \
    --template-file infra/main.bicep \
    --parameters infra/parameters.json -o none

echo "======================================================"
echo "3. Creating Azure OpenAI Resource: $AOAI_NAME"
echo "======================================================"
az cognitiveservices account create \
    --name "$AOAI_NAME" \
    --resource-group "$RG_NAME" \
    --location "$LOCATION" \
    --kind OpenAI \
    --sku S0 \
    --custom-domain "$AOAI_NAME" -o none

echo "Deploying GPT-4o model..."
az cognitiveservices account deployment create \
    --name "$AOAI_NAME" \
    --resource-group "$RG_NAME" \
    --model-name gpt-4o \
    --model-version 2024-05-13 \
    --model-format OpenAI \
    --sku-name "Standard" \
    --sku-capacity 50 -o none

echo "======================================================"
echo "4. Creating AI Foundry Hub and Project"
echo "======================================================"
# Create Hub (Workspace)
az ml workspace create \
    --name "$HUB_NAME" \
    --resource-group "$RG_NAME" \
    --location "$LOCATION" \
    --kind hub -o none

# Create Project linked to the Hub
az ml workspace create \
    --name "$PROJECT_NAME" \
    --resource-group "$RG_NAME" \
    --location "$LOCATION" \
    --kind project \
    --hub-id "/subscriptions/$SUB_ID/resourceGroups/$RG_NAME/providers/Microsoft.MachineLearningServices/workspaces/$HUB_NAME" -o none

echo "======================================================"
echo "5. Connecting Azure OpenAI to AI Foundry Hub"
echo "======================================================"
AOAI_ID="/subscriptions/$SUB_ID/resourceGroups/$RG_NAME/providers/Microsoft.CognitiveServices/accounts/$AOAI_NAME"
az ml connection create \
    --type azure_open_ai \
    --name "aoai-connection" \
    --workspace-name "$HUB_NAME" \
    --resource-group "$RG_NAME" \
    --set target="$AOAI_ID" -o none

echo "======================================================"
echo "6. Outputting Recommended .env Configuration"
echo "======================================================"
cat << EOF > .env.generated
AZURE_SUBSCRIPTION_ID="$SUB_ID"
AZURE_RESOURCE_GROUP="$RG_NAME"
ANF_ACCOUNT_NAME="anf-selfops-account"
ANF_POOL_NAME="anf-selfops-pool"
AZURE_OPENAI_DEPLOYMENT="gpt-4o"
AZURE_AI_PROJECT_CONNECTION_STRING="$(az ml workspace show -n $PROJECT_NAME -g $RG_NAME --query "discoveryUrl" -o tsv)"
EOF

echo "Deployment complete! Your configuration has been saved to .env.generated"
echo "Please review the file and rename it to .env: mv .env.generated .env"
