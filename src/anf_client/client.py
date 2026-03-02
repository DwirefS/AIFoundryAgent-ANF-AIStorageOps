"""
Azure NetApp Files Management Client Wrapper.

Wraps the azure-mgmt-netapp SDK to provide clean, typed operations
that the Foundry agent's function calling tools invoke. Each method
returns a Pydantic model (from .models) serializable to JSON.

Reference:
  - SDK docs: https://learn.microsoft.com/python/api/azure-mgmt-netapp
  - REST API:  https://learn.microsoft.com/rest/api/netapp
  - Samples:   https://github.com/Azure-Samples/netappfiles-python-sdk-sample
"""

from __future__ import annotations

import logging
from typing import Optional

from azure.identity import DefaultAzureCredential
from azure.mgmt.netapp import NetAppManagementClient
from azure.mgmt.netapp.models import Snapshot, VolumePatch

from .models import (
    AccountInfo,
    CapacityPoolInfo,
    OperationResult,
    QuotaInfo,
    SnapshotInfo,
    VolumeHealthInfo,
    VolumeInfo,
)

logger = logging.getLogger(__name__)


class ANFClient:
    """
    High-level wrapper around the Azure NetApp Files Management SDK.

    Provides the operations exposed as function tools to the Foundry agent:
      - list_capacity_pools, list_volumes, get_volume, create_volume, delete_volume
      - create_snapshot, list_snapshots, delete_snapshot, revert_volume
      - resize_volume
      - get_account_info, get_quota_limits, check_volume_health
    """

    def __init__(
        self,
        subscription_id: str,
        resource_group: str,
        account_name: str,
        pool_name: str,
        credential: Optional[DefaultAzureCredential] = None,
    ):
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.account_name = account_name
        self.default_pool_name = pool_name

        self._credential = credential or DefaultAzureCredential()
        self._client = NetAppManagementClient(
            credential=self._credential,
            subscription_id=self.subscription_id,
        )
        logger.info(
            "ANFClient initialized for account=%s, pool=%s, rg=%s",
            account_name,
            pool_name,
            resource_group,
        )

    # ── Pool Operations ───────────────────────────────────────────────

    def list_capacity_pools(self) -> list[CapacityPoolInfo]:
        """
        List all capacity pools in the ANF account.

        Returns:
            List of CapacityPoolInfo objects.
        """
        logger.info("Listing capacity pools: rg=%s, account=%s", self.resource_group, self.account_name)

        pools = []
        for pool in self._client.pools.list(
            resource_group_name=self.resource_group,
            account_name=self.account_name,
        ):
            pools.append(CapacityPoolInfo.from_sdk(pool, self.resource_group))

        logger.info("Found %d capacity pools", len(pools))
        return pools

    # ── Volume Operations ─────────────────────────────────────────────

    def list_volumes(self, pool_name: Optional[str] = None) -> list[VolumeInfo]:
        """
        List all volumes in a capacity pool.

        Args:
            pool_name: Capacity pool name. Uses default if not specified.

        Returns:
            List of VolumeInfo objects.
        """
        pool = pool_name or self.default_pool_name
        logger.info(
            "Listing volumes: rg=%s, account=%s, pool=%s", self.resource_group, self.account_name, pool
        )

        volumes = []
        for vol in self._client.volumes.list(
            resource_group_name=self.resource_group,
            account_name=self.account_name,
            pool_name=pool,
        ):
            volumes.append(VolumeInfo.from_sdk(vol, self.resource_group, self.account_name, pool))

        logger.info("Found %d volumes in pool %s", len(volumes), pool)
        return volumes

    def get_volume(self, volume_name: str, pool_name: Optional[str] = None) -> VolumeInfo:
        """
        Get detailed information about a specific volume.

        Args:
            volume_name: Name of the volume.
            pool_name: Capacity pool name. Uses default if not specified.

        Returns:
            VolumeInfo object.
        """
        pool = pool_name or self.default_pool_name
        logger.info("Getting volume: %s (pool=%s)", volume_name, pool)

        vol = self._client.volumes.get(
            resource_group_name=self.resource_group,
            account_name=self.account_name,
            pool_name=pool,
            volume_name=volume_name,
        )
        return VolumeInfo.from_sdk(vol, self.resource_group, self.account_name, pool)

    def delete_volume(self, volume_name: str, pool_name: Optional[str] = None) -> OperationResult:
        """
        Delete an ANF volume. This is a destructive operation.

        Args:
            volume_name: Name of the volume to delete.
            pool_name: Capacity pool name. Uses default if not specified.

        Returns:
            OperationResult indicating success/failure.
        """
        pool = pool_name or self.default_pool_name
        logger.info("Deleting volume '%s' from pool '%s'", volume_name, pool)

        try:
            poller = self._client.volumes.begin_delete(
                resource_group_name=self.resource_group,
                account_name=self.account_name,
                pool_name=pool,
                volume_name=volume_name,
            )
            poller.result()  # Wait for completion

            return OperationResult(
                success=True,
                operation="delete_volume",
                resource_name=volume_name,
                details=f"Volume '{volume_name}' deleted successfully.",
            )
        except Exception as e:
            logger.error("Failed to delete volume %s: %s", volume_name, str(e))
            return OperationResult(
                success=False,
                operation="delete_volume",
                resource_name=volume_name,
                details="",
                error=str(e),
            )

    def revert_volume(
        self, volume_name: str, snapshot_id: str, pool_name: Optional[str] = None
    ) -> OperationResult:
        """
        Revert a volume to one of its snapshots.

        Args:
            volume_name: Name of the volume to revert.
            snapshot_id: The resource ID of the snapshot to revert to.
            pool_name: Capacity pool name. Uses default if not specified.

        Returns:
            OperationResult indicating success/failure.
        """
        pool = pool_name or self.default_pool_name
        logger.info("Reverting volume '%s' to snapshot ID '%s'", volume_name, snapshot_id)

        try:
            poller = self._client.volumes.begin_revert(
                resource_group_name=self.resource_group,
                account_name=self.account_name,
                pool_name=pool,
                volume_name=volume_name,
                body={"snapshotId": snapshot_id},
            )
            poller.result()  # Wait for completion

            return OperationResult(
                success=True,
                operation="revert_volume",
                resource_name=volume_name,
                details=f"Volume '{volume_name}' reverted successfully to snapshot.",
            )
        except Exception as e:
            logger.error("Failed to revert volume %s: %s", volume_name, str(e))
            return OperationResult(
                success=False,
                operation="revert_volume",
                resource_name=volume_name,
                details="",
                error=str(e),
            )

    def resize_volume(
        self, volume_name: str, new_size_gib: int, pool_name: Optional[str] = None
    ) -> OperationResult:
        """
        Resize an ANF volume. ANF supports online resize — no downtime.

        Args:
            volume_name: Name of the volume to resize.
            new_size_gib: New size in GiB (must be >= 100 GiB, multiples of 1 GiB).
            pool_name: Capacity pool name. Uses default if not specified.

        Returns:
            OperationResult indicating success/failure.
        """
        pool = pool_name or self.default_pool_name
        new_size_bytes = int(new_size_gib) * (1024**3)

        logger.info("Resizing volume %s to %d GiB (%d bytes)", volume_name, new_size_gib, new_size_bytes)

        # Validate minimum size
        if new_size_gib < 100:
            return OperationResult(
                success=False,
                operation="resize_volume",
                resource_name=volume_name,
                details="",
                error=f"Minimum volume size is 100 GiB. Requested: {new_size_gib} GiB.",
            )

        try:
            # Get current volume to report before/after
            current = self._client.volumes.get(
                resource_group_name=self.resource_group,
                account_name=self.account_name,
                pool_name=pool,
                volume_name=volume_name,
            )
            old_size_bytes = current.usage_threshold or 0
            old_size_gib = round(old_size_bytes / (1024**3), 2)

            # Execute resize (long-running operation)
            # azure-mgmt-netapp 14.0.x has a _deserialize_model bug with VolumePatch.
            # Pass a raw dict instead of VolumePatch to avoid the serialization issue,
            # and use poller.wait() instead of poller.result() to skip deserialization.
            poller = self._client.volumes.begin_update(
                resource_group_name=self.resource_group,
                account_name=self.account_name,
                pool_name=pool,
                volume_name=volume_name,
                body={"properties": {"usageThreshold": new_size_bytes}},
            )
            poller.wait()

            # Verify the resize by re-fetching the volume
            updated = self._client.volumes.get(
                resource_group_name=self.resource_group,
                account_name=self.account_name,
                pool_name=pool,
                volume_name=volume_name,
            )
            actual_size_gib = round((updated.usage_threshold or 0) / (1024**3), 2)

            return OperationResult(
                success=True,
                operation="resize_volume",
                resource_name=volume_name,
                details=(
                    f"Volume '{volume_name}' resized from {old_size_gib} GiB to {actual_size_gib} GiB. "
                    f"ANF volume resize is online — no downtime required."
                ),
            )
        except Exception as e:
            logger.error("Failed to resize volume %s: %s", volume_name, str(e))
            return OperationResult(
                success=False,
                operation="resize_volume",
                resource_name=volume_name,
                details="",
                error=str(e),
            )

    # ── Snapshot Operations ───────────────────────────────────────────

    def create_snapshot(
        self,
        volume_name: str,
        snapshot_name: str,
        pool_name: Optional[str] = None,
    ) -> OperationResult:
        """
        Create a snapshot of an ANF volume.

        ANF snapshots are instant, space-efficient (redirect-on-write),
        and have zero performance impact on the volume.

        Args:
            volume_name: Name of the volume to snapshot.
            snapshot_name: Name for the new snapshot.
            pool_name: Capacity pool name. Uses default if not specified.

        Returns:
            OperationResult indicating success/failure.
        """
        pool = pool_name or self.default_pool_name
        logger.info("Creating snapshot '%s' on volume '%s'", snapshot_name, volume_name)

        try:
            # Get volume to determine location
            vol = self._client.volumes.get(
                resource_group_name=self.resource_group,
                account_name=self.account_name,
                pool_name=pool,
                volume_name=volume_name,
            )

            snapshot_body = Snapshot(location=vol.location)

            poller = self._client.snapshots.begin_create(
                resource_group_name=self.resource_group,
                account_name=self.account_name,
                pool_name=pool,
                volume_name=volume_name,
                snapshot_name=snapshot_name,
                body=snapshot_body,
            )
            result = poller.result()  # Wait for completion

            return OperationResult(
                success=True,
                operation="create_snapshot",
                resource_name=snapshot_name,
                details=(
                    f"Snapshot '{snapshot_name}' created on volume '{volume_name}'. "
                    f"Provisioning state: {result.provisioning_state}. "
                    f"Created at: {result.created}. "
                    f"ANF snapshots are instant and have zero performance impact."
                ),
            )
        except Exception as e:
            logger.error("Failed to create snapshot %s: %s", snapshot_name, str(e))
            return OperationResult(
                success=False,
                operation="create_snapshot",
                resource_name=snapshot_name,
                details="",
                error=str(e),
            )

    def list_snapshots(self, volume_name: str, pool_name: Optional[str] = None) -> list[SnapshotInfo]:
        """
        List all snapshots for a volume.

        Args:
            volume_name: Name of the volume.
            pool_name: Capacity pool name. Uses default if not specified.

        Returns:
            List of SnapshotInfo objects.
        """
        pool = pool_name or self.default_pool_name
        logger.info("Listing snapshots for volume '%s'", volume_name)

        snapshots = []
        for snap in self._client.snapshots.list(
            resource_group_name=self.resource_group,
            account_name=self.account_name,
            pool_name=pool,
            volume_name=volume_name,
        ):
            snapshots.append(SnapshotInfo.from_sdk(snap, volume_name))

        logger.info("Found %d snapshots for volume %s", len(snapshots), volume_name)
        return snapshots

    def delete_snapshot(
        self,
        volume_name: str,
        snapshot_name: str,
        pool_name: Optional[str] = None,
    ) -> OperationResult:
        """
        Delete a snapshot from a volume.

        Args:
            volume_name: Name of the volume.
            snapshot_name: Name of the snapshot to delete.
            pool_name: Capacity pool name. Uses default if not specified.

        Returns:
            OperationResult indicating success/failure.
        """
        pool = pool_name or self.default_pool_name
        logger.info("Deleting snapshot '%s' from volume '%s'", snapshot_name, volume_name)

        try:
            poller = self._client.snapshots.begin_delete(
                resource_group_name=self.resource_group,
                account_name=self.account_name,
                pool_name=pool,
                volume_name=volume_name,
                snapshot_name=snapshot_name,
            )
            poller.result()

            return OperationResult(
                success=True,
                operation="delete_snapshot",
                resource_name=snapshot_name,
                details=f"Snapshot '{snapshot_name}' deleted from volume '{volume_name}'.",
            )
        except Exception as e:
            logger.error("Failed to delete snapshot %s: %s", snapshot_name, str(e))
            return OperationResult(
                success=False,
                operation="delete_snapshot",
                resource_name=snapshot_name,
                details="",
                error=str(e),
            )

    # ── Account Operations ────────────────────────────────────────────

    def get_account_info(self) -> AccountInfo:
        """
        Get information about the ANF account.

        Returns:
            AccountInfo object.
        """
        logger.info("Getting account info: %s", self.account_name)

        account = self._client.accounts.get(
            resource_group_name=self.resource_group,
            account_name=self.account_name,
        )

        ad_count = len(account.active_directories) if account.active_directories else 0

        return AccountInfo(
            name=account.name,
            resource_group=self.resource_group,
            location=account.location,
            provisioning_state=account.provisioning_state or "Unknown",
            active_directories=ad_count,
        )

    # ── Volume Creation ────────────────────────────────────────────────

    def create_volume(
        self,
        volume_name: str,
        size_gib: int,
        pool_name: Optional[str] = None,
        protocol: str = "NFSv4.1",
    ) -> OperationResult:
        """
        Create a new Azure NetApp Files volume in a capacity pool.

        ANF volumes are provisioned within a capacity pool and inherit its
        service level. The volume gets a dedicated NFS/SMB endpoint on the
        ANF-delegated subnet.

        Args:
            volume_name: Name for the new volume (must be unique in the pool).
            size_gib: Volume quota in GiB (minimum 100 GiB).
            pool_name: Target capacity pool. Uses default pool if not specified.
            protocol: Protocol type — "NFSv4.1" (default), "NFSv3", or "CIFS".

        Returns:
            OperationResult indicating success or failure.
        """
        pool = pool_name or self.default_pool_name
        logger.info("Creating volume %s (%d GiB) in pool %s", volume_name, size_gib, pool)

        if size_gib < 100:
            return OperationResult(
                success=False,
                operation="create_volume",
                resource_name=volume_name,
                details="",
                error="Volume size must be at least 100 GiB.",
            )

        # Resolve the subnet ID from an existing volume in the pool
        # (ANF volumes must be on the same delegated subnet)
        try:
            existing_volumes = list(
                self._client.volumes.list(
                    resource_group_name=self.resource_group,
                    account_name=self.account_name,
                    pool_name=pool,
                )
            )
            if not existing_volumes:
                return OperationResult(
                    success=False,
                    operation="create_volume",
                    resource_name=volume_name,
                    details="",
                    error=f"No existing volumes in pool '{pool}' to derive subnet ID. "
                    "Create the first volume via Azure Portal or Bicep.",
                )
            subnet_id = existing_volumes[0].subnet_id

            # Map protocol string to protocol types array
            protocol_map = {
                "NFSv4.1": ["NFSv4.1"],
                "NFSv3": ["NFSv3"],
                "CIFS": ["CIFS"],
            }
            protocol_types = protocol_map.get(protocol, ["NFSv4.1"])

            new_size_bytes = size_gib * (1024**3)

            # Use raw dict to avoid DPG serialization issues (same pattern as resize_volume)
            poller = self._client.volumes.begin_create_or_update(
                resource_group_name=self.resource_group,
                account_name=self.account_name,
                pool_name=pool,
                volume_name=volume_name,
                body={
                    "location": existing_volumes[0].location,
                    "properties": {
                        "creationToken": volume_name,
                        "usageThreshold": new_size_bytes,
                        "subnetId": subnet_id,
                        "protocolTypes": protocol_types,
                        "snapshotDirectoryVisible": True,
                        "exportPolicy": {
                            "rules": [
                                {
                                    "ruleIndex": 1,
                                    "unixReadOnly": False,
                                    "unixReadWrite": True,
                                    "allowedClients": "10.0.0.0/16",
                                    "nfsv41": "NFSv4.1" in protocol_types,
                                    "nfsv3": "NFSv3" in protocol_types,
                                }
                            ]
                        },
                    },
                },
            )
            poller.result()  # Wait for completion

            return OperationResult(
                success=True,
                operation="create_volume",
                resource_name=volume_name,
                details=(
                    f"Volume '{volume_name}' created in pool '{pool}' "
                    f"with {size_gib} GiB capacity, {protocol} protocol."
                ),
            )
        except Exception as e:
            logger.error("create_volume failed: %s", str(e))
            return OperationResult(
                success=False,
                operation="create_volume",
                resource_name=volume_name,
                details="",
                error=str(e),
            )

    # ── Monitoring & Health ────────────────────────────────────────────

    def check_volume_health(
        self,
        volume_name: str,
        pool_name: Optional[str] = None,
    ) -> VolumeHealthInfo:
        """
        Get an aggregated health and utilization summary for a volume.

        Combines volume metadata with snapshot inventory to provide a
        single-call health check useful for operational monitoring.

        Args:
            volume_name: Name of the ANF volume to inspect.
            pool_name: Capacity pool name. Uses default if not specified.

        Returns:
            VolumeHealthInfo with volume details and snapshot summary.
        """
        pool = pool_name or self.default_pool_name
        logger.info("Checking health of volume %s in pool %s", volume_name, pool)

        # Get volume details
        volume = self._client.volumes.get(
            resource_group_name=self.resource_group,
            account_name=self.account_name,
            pool_name=pool,
            volume_name=volume_name,
        )

        # Get snapshots for this volume
        snapshots = list(
            self._client.snapshots.list(
                resource_group_name=self.resource_group,
                account_name=self.account_name,
                pool_name=pool,
                volume_name=volume_name,
            )
        )

        # Find the latest snapshot
        latest_snapshot = None
        if snapshots:
            snapshots_with_dates = [s for s in snapshots if s.created]
            if snapshots_with_dates:
                latest_snapshot = max(snapshots_with_dates, key=lambda s: s.created)

        # Count export policy rules
        export_rules = 0
        if volume.export_policy and volume.export_policy.rules:
            export_rules = len(volume.export_policy.rules)

        return VolumeHealthInfo(
            volume_name=volume_name,
            pool_name=pool,
            provisioning_state=volume.provisioning_state or "Unknown",
            size_gib=round((volume.usage_threshold or 0) / (1024**3), 2),
            service_level=volume.service_level or "Unknown",
            throughput_mibps=volume.actual_throughput_mibps,
            protocol_types=list(volume.protocol_types or []),
            snapshot_count=len(snapshots),
            latest_snapshot_name=(
                latest_snapshot.name.split("/")[-1] if latest_snapshot else None
            ),
            latest_snapshot_date=latest_snapshot.created if latest_snapshot else None,
            export_policy_client_count=export_rules,
            snapshot_directory_visible=volume.snapshot_directory_visible,
        )

    def get_quota_limits(self) -> list[QuotaInfo]:
        """
        Get ANF quota limits for the account's region.

        Queries the subscription-level quota limits for Azure NetApp Files
        in the region where the account is deployed. Useful for capacity
        planning and ensuring operations won't exceed quotas.

        Returns:
            List of QuotaInfo objects describing regional limits.
        """
        logger.info("Getting quota limits for account %s", self.account_name)

        # First, get the account to determine its location
        account = self._client.accounts.get(
            resource_group_name=self.resource_group,
            account_name=self.account_name,
        )
        location = account.location

        # Query quota limits for this region
        try:
            quotas = list(
                self._client.net_app_resource_quota_limits.list(
                    location=location,
                )
            )

            result = []
            for q in quotas:
                result.append(
                    QuotaInfo(
                        region=location,
                        resource_type=q.name or "Unknown",
                        current_value=q.current_value or 0,
                        limit=q.default or 0,
                        unit=q.unit or "Count",
                    )
                )
            return result
        except Exception as e:
            logger.error("get_quota_limits failed: %s", str(e))
            # Return a single error entry rather than raising,
            # so the agent can report the issue gracefully
            return [
                QuotaInfo(
                    region=location,
                    resource_type="error",
                    current_value=0,
                    limit=0,
                    unit=str(e),
                )
            ]
