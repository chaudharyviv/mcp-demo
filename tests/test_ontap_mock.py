import json
from pathlib import Path
import pytest
from ontap_mock.server import (
    load_data,
    ontap_cluster_health_summary,
    ontap_aggr_show,
    ontap_vol_show,
    ontap_vol_resize,
    get_inventory_summary
)

def test_data_consistency():
    """Volume footprints sum to each aggregate's used space."""
    data = load_data()
    aggregates = data["aggregates"]
    volumes = data["volumes"]

    for aggr in aggregates:
        aggr_name = aggr["name"]
        aggr_used = aggr["space"]["block_storage"]["used"]
        aggr_vols = [v for v in volumes if any(a["name"] == aggr_name for a in v["aggregates"])]
        sum_footprints = sum(v["footprint"] for v in aggr_vols)
        assert sum_footprints == aggr_used, f"Aggregate {aggr_name} used ({aggr_used}) does not equal sum of volume footprints ({sum_footprints})"

def test_health_summary_planted_issues():
    """Test health summary finds planted issues: aggr_a01 91%, vol_legacy_ftp offline, vol_reports snapshot overrun."""
    result = ontap_cluster_health_summary()
    assert result["synthetic"] is True
    issues = result["issues"]

    aggr_a01_issue = next((i for i in issues if i["object_name"] == "aggr_a01" and i["severity"] == "critical"), None)
    assert aggr_a01_issue is not None, "aggr_a01 critical issue missing"

    vol_offline_issue = next((i for i in issues if i["object_name"] == "vol_legacy_ftp" and i["severity"] == "critical"), None)
    assert vol_offline_issue is not None, "vol_legacy_ftp offline issue missing"

    vol_snap_issue = next((i for i in issues if i["object_name"] == "vol_reports" and i["severity"] == "warning"), None)
    assert vol_snap_issue is not None, "vol_reports snapshot overrun warning missing"

def test_aggr_show():
    """Test aggr_show returns aggregates sorted by used_percent descending."""
    result = ontap_aggr_show()
    assert result["synthetic"] is True
    aggrs = result["aggregates"]
    assert len(aggrs) == 4
    assert aggrs[0]["name"] == "aggr_a01"
    assert aggrs[0]["used_percent"] == 91.0

def test_vol_show():
    """Test vol_show filtering."""
    result = ontap_vol_show(state="offline")
    assert result["synthetic"] is True
    vols = result["volumes"]
    assert len(vols) == 1
    assert vols[0]["name"] == "vol_legacy_ftp"

def test_vol_resize_no_change_id():
    """Resize with no change_id returns refused."""
    result = ontap_vol_resize(volume="vol_payments_db", grow_by_gb=200)
    assert result["synthetic"] is True
    assert result["status"] == "refused"
    assert "change number is required" in result["message"].lower()

def test_vol_resize_malformed_change_id():
    """Resize with malformed change_id returns refused."""
    result = ontap_vol_resize(volume="vol_payments_db", grow_by_gb=200, change_id="INVALID123")
    assert result["synthetic"] is True
    assert result["status"] == "refused"
    assert "expected format" in result["message"].lower()

def test_vol_resize_valid_change_id():
    """Resize with CHG0012345 returns dry_run, projected ~92%, with aggr_a02 suggestion."""
    result = ontap_vol_resize(volume="vol_payments_db", grow_by_gb=200, change_id="CHG0012345")
    assert result["synthetic"] is True
    assert result["status"] == "dry_run"
    assert result["executed"] is False
    plan = result["plan"]
    assert plan["volume"] == "vol_payments_db"
    assert plan["projected_aggregate_used_percent"] == 91.9 or plan["projected_aggregate_used_percent"] == 92.0 or round(plan["projected_aggregate_used_percent"]) == 92
    assert len(plan["warnings"]) > 0
    assert "aggr_a02" in plan["warnings"][0]

def test_dataset_unmodified_after_resize():
    """The dataset is unchanged after any resize call."""
    data_before = load_data()
    ontap_vol_resize(volume="vol_payments_db", grow_by_gb=200, change_id="CHG0012345")
    data_after = load_data()
    assert data_before == data_after

def test_resource_inventory_summary():
    """Test resource ontap://inventory/summary."""
    summary_str = get_inventory_summary()
    summary = json.loads(summary_str)
    assert summary["synthetic"] is True
    assert len(summary["clusters"]) == 2
    assert len(summary["aggregates"]) == 4

@pytest.mark.asyncio
@pytest.mark.parametrize("grow_by_gb, expect_error", [(0, True), (-5000, True), (5001, True), (1, False), (5000, False)])
async def test_vol_resize_grow_bounds_enforced_over_mcp(grow_by_gb, expect_error):
    """grow_by_gb must be 1-5000 when called through MCP; dataset unchanged either way (CODE_REVIEW H7)."""
    from agent.mcp_clients import MCPClientManager
    data_before = load_data()
    result = await MCPClientManager().call_tool(
        "ontap", "ontap_vol_resize",
        {"volume": "vol_payments_db", "grow_by_gb": grow_by_gb, "change_id": "CHG0012345"}
    )
    assert bool(result["isError"]) is expect_error
    if not expect_error:
        assert json.loads(result["content"][0].text)["status"] == "dry_run"
    assert load_data() == data_before

@pytest.mark.asyncio
async def test_tool_schemas_carry_bounds_and_descriptions():
    """Pydantic Field bounds/descriptions reach the schema the model sees (CODE_REVIEW H7)."""
    from agent.mcp_clients import MCPClientManager
    tools = {t["name"]: t["inputSchema"] for t in (await MCPClientManager().get_server_tools("ontap"))["tools"]}
    grow = tools["ontap_vol_resize"]["properties"]["grow_by_gb"]
    assert grow["minimum"] == 1 and grow["maximum"] == 5000 and grow["description"]
    assert tools["ontap_vol_show"]["properties"]["limit"]["minimum"] == 1
