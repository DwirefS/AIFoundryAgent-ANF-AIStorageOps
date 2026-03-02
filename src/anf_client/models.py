"""
Pydantic models for ANF resource representations.

These models provide structured, validated responses from ANF operations
that are serialized to JSON for the Foundry agent's function call outputs.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class VolumeInfo(BaseModel):
    """Represents an Azure NetApp Files volume."""

    name: str = Field(description="Volume name")
    resource_group: str = Field(description="Resource group name")
    account_name: str = Field(description="ANF account name")
    pool_name: str = Field(description="Capacity pool name")
    location: str = Field(description="Azure region")
    service_level: str = Field(description="Service level: Standard, Premium, or Ultra")
    quota_in_bytes: int = Field(description="Provisioned size in bytes")
    quota_in_gib: float = Field(description="Provisioned size in GiB")
    protocol_types: list[str] = Field(default_factory=list, description="Enabled protocols")
    provisioning_state: str = Field(description="Current provisioning state")
    throughput_mibps: Optional[float] = Field(None, description="Throughput in MiB/s")
    creation_token: str = Field(description="Unique file path / creation token")
    subnet_id: Optional[str] = Field(None, description="Delegated subnet resource ID")
    snapshot_directory_visible: Optional[bool] = Field(
        None, description="Whether .snapshot directory is visible"
    )

    @classmethod
    def from_sdk(cls, volume, resource_group: str, account_name: str, pool_name: str) -> VolumeInfo:
        """Create VolumeInfo from azure-mgmt-netapp Volume object."""
        quota_bytes = volume.usage_threshold or 0
        return cls(
            name=volume.name.split("/")[-1] if "/" in volume.name else volume.name,
            resource_group=resource_group,
            account_name=account_name,
            pool_name=pool_name,
            location=volume.location,
            service_level=volume.service_level or "Unknown",
            quota_in_bytes=quota_bytes,
            quota_in_gib=round(quota_bytes / (1024**3), 2),
            protocol_types=list(volume.protocol_types or []),
            provisioning_state=volume.provisioning_state or "Unknown",
            throughput_mibps=volume.actual_throughput_mibps,
            creation_token=volume.creation_token or "",
            subnet_id=volume.subnet_id,
            snapshot_directory_visible=volume.snapshot_directory_visible,
        )


class SnapshotInfo(BaseModel):
    """Represents an Azure NetApp Files snapshot."""

    name: str = Field(description="Snapshot name")
    volume_name: str = Field(description="Parent volume name")
    location: str = Field(description="Azure region")
    provisioning_state: str = Field(description="Current provisioning state")
    created: Optional[datetime] = Field(None, description="Snapshot creation timestamp")
    snapshot_id: Optional[str] = Field(None, description="Unique snapshot identifier")

    @classmethod
    def from_sdk(cls, snapshot, volume_name: str) -> SnapshotInfo:
        """Create SnapshotInfo from azure-mgmt-netapp Snapshot object."""
        return cls(
            name=snapshot.name.split("/")[-1] if "/" in snapshot.name else snapshot.name,
            volume_name=volume_name,
            location=snapshot.location,
            provisioning_state=snapshot.provisioning_state or "Unknown",
            created=snapshot.created,
            snapshot_id=snapshot.snapshot_id,
        )


class AccountInfo(BaseModel):
    """Represents an Azure NetApp Files account."""

    name: str = Field(description="Account name")
    resource_group: str = Field(description="Resource group name")
    location: str = Field(description="Azure region")
    provisioning_state: str = Field(description="Current provisioning state")
    active_directories: int = Field(description="Number of Active Directory connections")


class OperationResult(BaseModel):
    """Represents the result of an ANF management operation."""

    success: bool = Field(description="Whether the operation succeeded")
    operation: str = Field(description="Operation that was performed")
    resource_name: str = Field(description="Name of the resource affected")
    details: str = Field(description="Human-readable result details")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class CapacityPoolInfo(BaseModel):
    """Represents an Azure NetApp Files capacity pool."""

    name: str = Field(description="Pool name")
    resource_group: str = Field(description="Resource group name")
    location: str = Field(description="Azure region")
    service_level: str = Field(description="Service level: Standard, Premium, or Ultra")
    size_in_bytes: int = Field(description="Provisioned size in bytes")
    size_in_gib: float = Field(description="Provisioned size in GiB")
    provisioning_state: str = Field(description="Current provisioning state")
    utilization_percent: Optional[float] = Field(
        None, description="Pool utilization as percentage of provisioned capacity"
    )

    @classmethod
    def from_sdk(cls, pool, resource_group: str, utilization: Optional[float] = None) -> CapacityPoolInfo:
        """Create CapacityPoolInfo from azure-mgmt-netapp CapacityPool object."""
        return cls(
            name=pool.name.split("/")[-1] if "/" in pool.name else pool.name,
            resource_group=resource_group,
            location=pool.location,
            service_level=pool.service_level or "Unknown",
            size_in_bytes=pool.size or 0,
            size_in_gib=round((pool.size or 0) / (1024**3), 2),
            provisioning_state=pool.provisioning_state or "Unknown",
            utilization_percent=utilization,
        )


class QuotaInfo(BaseModel):
    """Represents ANF regional quota limits and current usage."""

    region: str = Field(description="Azure region")
    resource_type: str = Field(description="Resource type being queried")
    current_value: int = Field(description="Current usage count")
    limit: int = Field(description="Maximum allowed count")
    unit: str = Field(default="Count", description="Unit of measure")


class VolumeHealthInfo(BaseModel):
    """Aggregated health and utilization summary for a volume."""

    volume_name: str = Field(description="Volume name")
    pool_name: str = Field(description="Capacity pool name")
    provisioning_state: str = Field(description="Current provisioning state")
    size_gib: float = Field(description="Provisioned size in GiB")
    service_level: str = Field(description="Service level")
    throughput_mibps: Optional[float] = Field(None, description="Actual throughput in MiB/s")
    protocol_types: list[str] = Field(default_factory=list, description="Enabled protocols")
    snapshot_count: int = Field(description="Number of existing snapshots")
    latest_snapshot_name: Optional[str] = Field(None, description="Most recent snapshot name")
    latest_snapshot_date: Optional[datetime] = Field(None, description="Most recent snapshot timestamp")
    export_policy_client_count: int = Field(
        default=0, description="Number of export policy rules configured"
    )
    snapshot_directory_visible: Optional[bool] = Field(
        None, description="Whether .snapshot directory is visible to clients"
    )
