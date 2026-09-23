"""
Mock NetApp ONTAP FastMCP Server.
Synthetic data only. All write tools are dry-run only.
"""
import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastmcp import FastMCP

# Path to synthetic dataset
DATA_PATH = Path(__file__).parent / "data" / "estate.json"

def load_data() -> Dict[str, Any]:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

mcp = FastMCP("Mock NetApp ONTAP MCP Server")

@mcp.resource("ontap://inventory/summary")
def get_inventory_summary() -> str:
    """Read-only resource returning cluster, SVM, and aggregate names."""
    data = load_data()
    summary = {
        "synthetic": True,
        "clusters": [
            {
                "name": c["name"],
                "nodes": c["nodes"],
                "svms": c["svms"]
            }
            for c in data.get("clusters", [])
        ],
        "aggregates": [
            {
                "name": a["name"],
                "cluster": a["cluster"],
                "node": a["node"]["name"]
            }
            for a in data.get("aggregates", [])
        ]
    }
    return json.dumps(summary, indent=2)

class HealthSummaryInput(BaseModel):
    cluster: Optional[str] = Field(default=None, description="Filter summary by cluster name (e.g. cls-alpha, cls-beta)")

@mcp.tool(
    name="ontap_cluster_health_summary",
    description="Returns high-level health status, cluster/SVM/aggregate/volume counts, and detected issues across the ONTAP estate."
)
def ontap_cluster_health_summary(cluster: Optional[str] = None) -> Dict[str, Any]:
    data = load_data()
    clusters = data.get("clusters", [])
    aggregates = data.get("aggregates", [])
    volumes = data.get("volumes", [])

    if cluster:
        clusters = [c for c in clusters if c["name"] == cluster]
        aggregates = [a for a in aggregates if a["cluster"] == cluster]
        volumes = [v for v in volumes if v["cluster"] == cluster]

    issues = []

    # Check aggregates
    for aggr in aggregates:
        size = aggr["space"]["block_storage"]["size"]
        used = aggr["space"]["block_storage"]["used"]
        used_pct = (used / size) * 100 if size > 0 else 0
        if used_pct >= 90:
            issues.append({
                "severity": "critical",
                "object_type": "aggregate",
                "object_name": aggr["name"],
                "message": f"Aggregate capacity critical ({used_pct:.1f}% used)."
            })
        elif used_pct >= 85:
            issues.append({
                "severity": "warning",
                "object_type": "aggregate",
                "object_name": aggr["name"],
                "message": f"Aggregate capacity warning ({used_pct:.1f}% used)."
            })

    # Check volumes
    for vol in volumes:
        state = vol.get("state", "online")
        if state != "online":
            issues.append({
                "severity": "critical",
                "object_type": "volume",
                "object_name": vol["name"],
                "message": f"Volume state is '{state}'."
            })

        size = vol["size"]
        used = vol["space"]["used"]
        used_pct = (used / size) * 100 if size > 0 else 0
        if used_pct >= 90:
            issues.append({
                "severity": "warning",
                "object_type": "volume",
                "object_name": vol["name"],
                "message": f"Volume space nearly full ({used_pct:.1f}% used)."
            })

        snap_reserve_pct = vol["space"]["snapshot"]["reserve_percent"]
        snap_used = vol["space"]["snapshot"]["used"]
        snap_reserve_bytes = (size * snap_reserve_pct) / 100
        if snap_used > snap_reserve_bytes:
            snap_used_pct = (snap_used / size) * 100
            issues.append({
                "severity": "warning",
                "object_type": "volume",
                "object_name": vol["name"],
                "message": f"Snapshot space overrun ({snap_used_pct:.1f}% used vs {snap_reserve_pct}% reserve)."
            })

    return {
        "synthetic": True,
        "counts": {
            "clusters": len(clusters),
            "aggregates": len(aggregates),
            "volumes": len(volumes)
        },
        "issues": issues
    }

class AggrShowInput(BaseModel):
    cluster: Optional[str] = Field(default=None, description="Filter by cluster name")
    min_used_percent: Optional[int] = Field(default=None, description="Filter aggregates with used percentage >= this value (0-100)")

@mcp.tool(
    name="ontap_aggr_show",
    description="Returns aggregate details sorted by used percentage descending."
)
def ontap_aggr_show(cluster: Optional[str] = None, min_used_percent: Optional[int] = None) -> Dict[str, Any]:
    data = load_data()
    aggregates = data.get("aggregates", [])

    results = []
    for aggr in aggregates:
        if cluster and aggr["cluster"] != cluster:
            continue
        size = aggr["space"]["block_storage"]["size"]
        used = aggr["space"]["block_storage"]["used"]
        available = aggr["space"]["block_storage"]["available"]
        used_pct = (used / size) * 100 if size > 0 else 0

        if min_used_percent is not None and used_pct < min_used_percent:
            continue

        item = dict(aggr)
        item["used_percent"] = round(used_pct, 1)
        results.append(item)

    results.sort(key=lambda x: x["used_percent"], reverse=True)

    return {
        "synthetic": True,
        "aggregates": results
    }

class VolShowInput(BaseModel):
    cluster: Optional[str] = Field(default=None, description="Filter by cluster name")
    svm: Optional[str] = Field(default=None, description="Filter by SVM name")
    aggregate: Optional[str] = Field(default=None, description="Filter by aggregate name")
    state: Optional[str] = Field(default=None, description="Filter by volume state (online/offline)")
    name: Optional[str] = Field(default=None, description="Filter by volume name")
    limit: int = Field(default=20, description="Max volumes to return")

@mcp.tool(
    name="ontap_vol_show",
    description="Returns volume details matching filters."
)
def ontap_vol_show(
    cluster: Optional[str] = None,
    svm: Optional[str] = None,
    aggregate: Optional[str] = None,
    state: Optional[str] = None,
    name: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    data = load_data()
    volumes = data.get("volumes", [])

    results = []
    for vol in volumes:
        if cluster and vol.get("cluster") != cluster:
            continue
        if svm and vol.get("svm", {}).get("name") != svm:
            continue
        if aggregate:
            aggr_names = [a.get("name") for a in vol.get("aggregates", [])]
            if aggregate not in aggr_names:
                continue
        if state and vol.get("state") != state:
            continue
        if name and vol.get("name") != name:
            continue

        size = vol["size"]
        used = vol["space"]["used"]
        used_pct = (used / size) * 100 if size > 0 else 0

        item = dict(vol)
        item["used_percent"] = round(used_pct, 1)
        results.append(item)
        if len(results) >= limit:
            break

    return {
        "synthetic": True,
        "volumes": results
    }

class VolResizeInput(BaseModel):
    volume: str = Field(description="Name of the volume to resize")
    grow_by_gb: int = Field(description="Gigabytes to grow the volume by (1 to 5000)")
    change_id: Optional[str] = Field(default=None, description="Required Change Request ID (format: CHG followed by 7 digits, e.g. CHG0012345)")

@mcp.tool(
    name="ontap_vol_resize",
    description="Plans a volume resize operation (dry run only). Requires a valid Change Request ID."
)
def ontap_vol_resize(volume: str, grow_by_gb: int, change_id: Optional[str] = None) -> Dict[str, Any]:
    if not change_id:
        return {
            "synthetic": True,
            "status": "refused",
            "message": "A change number is required (format CHG followed by 7 digits)."
        }

    if not re.match(r"^CHG\d{7}$", change_id):
        return {
            "synthetic": True,
            "status": "refused",
            "message": f"Invalid change_id '{change_id}'. Expected format is CHG followed by 7 digits (e.g. CHG0012345)."
        }

    data = load_data()
    volumes = data.get("volumes", [])
    target_vol = next((v for v in volumes if v["name"] == volume), None)

    if not target_vol:
        matches = [v["name"] for v in volumes if volume.lower() in v["name"].lower()]
        return {
            "synthetic": True,
            "status": "error",
            "message": f"Volume '{volume}' not found.",
            "close_matches": matches
        }

    aggr_name = target_vol["aggregates"][0]["name"]
    aggregates = data.get("aggregates", [])
    target_aggr = next((a for a in aggregates if a["name"] == aggr_name), None)

    bytes_per_gb = 1073741824
    grow_bytes = grow_by_gb * bytes_per_gb

    curr_vol_size = target_vol["size"]
    new_vol_size = curr_vol_size + grow_bytes

    aggr_size = target_aggr["space"]["block_storage"]["size"]
    aggr_used = target_aggr["space"]["block_storage"]["used"]
    curr_aggr_used_pct = (aggr_used / aggr_size) * 100

    proj_aggr_used = aggr_used + grow_bytes
    proj_aggr_used_pct = (proj_aggr_used / aggr_size) * 100

    warnings = []
    if proj_aggr_used_pct >= 90:
        # Find least-used aggregate on the same cluster
        cluster = target_aggr["cluster"]
        same_cluster_aggrs = [a for a in aggregates if a["cluster"] == cluster]
        sorted_aggrs = sorted(
            same_cluster_aggrs,
            key=lambda a: (a["space"]["block_storage"]["used"] / a["space"]["block_storage"]["size"])
        )
        least_used = sorted_aggrs[0]["name"] if sorted_aggrs else "another aggregate"
        warnings.append(f"Aggregate would remain above 90%; consider moving the volume to a less-used aggregate such as {least_used}.")

    return {
        "synthetic": True,
        "status": "dry_run",
        "executed": False,
        "change_id": change_id,
        "plan": {
            "volume": volume,
            "current_size_bytes": curr_vol_size,
            "new_size_bytes": new_vol_size,
            "grow_by_gb": grow_by_gb,
            "aggregate": aggr_name,
            "current_aggregate_used_percent": round(curr_aggr_used_pct, 1),
            "projected_aggregate_used_percent": round(proj_aggr_used_pct, 1),
            "warnings": warnings
        }
    }

if __name__ == "__main__":
    mcp.run()
