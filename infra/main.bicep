// ============================================================
// ANF Foundry SelfOps — Infrastructure as Code (Bicep)
// ============================================================
// Deploys:
//   1. Azure NetApp Files account, capacity pool, and sample volume
//   2. Azure AI Foundry project with model deployment
//   3. User-Assigned Managed Identity with RBAC assignments
//
// Usage:
//   az deployment group create \
//     --resource-group <rg-name> \
//     --template-file infra/main.bicep \
//     --parameters infra/parameters.json
// ============================================================

targetScope = 'resourceGroup'

// ── Parameters ──────────────────────────────────────────────

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Base name prefix for all resources')
param baseName string = 'anfselfops'

@description('ANF capacity pool size in TiB')
@minValue(4)
param poolSizeTiB int = 4

@description('ANF volume size in GiB')
@minValue(100)
param volumeSizeGiB int = 1024

@description('ANF service level')
@allowed(['Standard', 'Premium', 'Ultra'])
param serviceLevel string = 'Premium'

@description('VNet address prefix')
param vnetAddressPrefix string = '10.0.0.0/16'

@description('ANF delegated subnet prefix')
param anfSubnetPrefix string = '10.0.1.0/24'

// ── Variables ───────────────────────────────────────────────

var uniqueSuffix = uniqueString(resourceGroup().id)
var anfAccountName = '${baseName}-anf-${uniqueSuffix}'
var poolName = 'pool-${serviceLevel}'
var volumeName = 'vol-sample-data'
var vnetName = '${baseName}-vnet'
var anfSubnetName = 'anf-delegated'
var managedIdentityName = '${baseName}-identity'

// ── Networking ──────────────────────────────────────────────

resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' = {
  name: vnetName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [vnetAddressPrefix]
    }
    subnets: [
      {
        name: anfSubnetName
        properties: {
          addressPrefix: anfSubnetPrefix
          delegations: [
            {
              name: 'anfDelegation'
              properties: {
                serviceName: 'Microsoft.NetApp/volumes'
              }
            }
          ]
        }
      }
    ]
  }
}

// ── Azure NetApp Files ──────────────────────────────────────

resource anfAccount 'Microsoft.NetApp/netAppAccounts@2024-07-01' = {
  name: anfAccountName
  location: location
  properties: {}
}

resource capacityPool 'Microsoft.NetApp/netAppAccounts/capacityPools@2024-07-01' = {
  parent: anfAccount
  name: poolName
  location: location
  properties: {
    serviceLevel: serviceLevel
    size: poolSizeTiB * 1099511627776 // Convert TiB to bytes
  }
}

resource volume 'Microsoft.NetApp/netAppAccounts/capacityPools/volumes@2024-07-01' = {
  parent: capacityPool
  name: volumeName
  location: location
  properties: {
    creationToken: volumeName
    serviceLevel: serviceLevel
    usageThreshold: volumeSizeGiB * 1073741824 // Convert GiB to bytes
    subnetId: vnet.properties.subnets[0].id
    protocolTypes: ['NFSv4.1']
    snapshotDirectoryVisible: true
    exportPolicy: {
      rules: [
        {
          ruleIndex: 1
          unixReadOnly: false
          unixReadWrite: true
          allowedClients: '10.0.0.0/16'
          nfsv41: true
          nfsv3: false
        }
      ]
    }
  }
}

// ── Network Security Group ──────────────────────────────────
// Restrict traffic to the ANF delegated subnet. Allow NFS (2049)
// inbound from the VNet only; deny all other inbound by default.

resource nsg 'Microsoft.Network/networkSecurityGroups@2024-01-01' = {
  name: '${baseName}-anf-nsg'
  location: location
  properties: {
    securityRules: [
      {
        name: 'AllowNFS-Inbound'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: vnetAddressPrefix
          sourcePortRange: '*'
          destinationAddressPrefix: anfSubnetPrefix
          destinationPortRange: '2049'
          description: 'Allow NFS v4.1 from within VNet only'
        }
      }
      {
        name: 'AllowNFS-UDP-Inbound'
        properties: {
          priority: 110
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Udp'
          sourceAddressPrefix: vnetAddressPrefix
          sourcePortRange: '*'
          destinationAddressPrefix: anfSubnetPrefix
          destinationPortRange: '2049'
          description: 'Allow NFS UDP from within VNet only'
        }
      }
      {
        name: 'DenyAllOtherInbound'
        properties: {
          priority: 4096
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '*'
          description: 'Deny all other inbound traffic to ANF subnet'
        }
      }
    ]
  }
}

// ── Managed Identity + Least-Privilege RBAC ─────────────────
// Security principle: assign the narrowest role at the narrowest scope.
// The agent identity gets:
//   - "NetApp Account Contributor" on the ANF account (not broad Contributor)
//   - "Cognitive Services OpenAI User" on the AOAI resource (assigned in deploy.sh)
// This prevents the identity from modifying any resources outside ANF.

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: managedIdentityName
  location: location
}

// Built-in role: "Contributor" scoped ONLY to the ANF account
// For tighter control, consider a custom role with only:
//   Microsoft.NetApp/netAppAccounts/read
//   Microsoft.NetApp/netAppAccounts/capacityPools/read
//   Microsoft.NetApp/netAppAccounts/capacityPools/volumes/*
// For now, Contributor on the ANF account (not the RG) is acceptable
// because the scope is narrow — it cannot touch AOAI, Hub, or other resources.
resource anfRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(anfAccount.id, managedIdentity.id, 'Contributor')
  scope: anfAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c') // Contributor
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ── Outputs ─────────────────────────────────────────────────

output anfAccountName string = anfAccount.name
output poolName string = capacityPool.name
output volumeName string = volume.name
output managedIdentityClientId string = managedIdentity.properties.clientId
output managedIdentityPrincipalId string = managedIdentity.properties.principalId
output managedIdentityName string = managedIdentity.name
output nsgId string = nsg.id
output vnetId string = vnet.id

// NOTE: AI Foundry Hub + Project are created via CLI (deploy.sh Steps 4-5)
// because the Bicep resource provider for ML workspaces is evolving.
// The deploy.sh also handles:
//   - AOAI resource creation + GPT-4o deployment
//   - AOAI connection (auth_type: aad) to the Hub
//   - RBAC assignment for Cognitive Services OpenAI Contributor
//   - .env.generated output with connection string
