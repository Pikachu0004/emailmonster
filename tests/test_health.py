import pytest
from devengers_engine.web.app import health_check

@pytest.mark.anyio
async def test_health_endpoint_direct():
    data = await health_check()
    assert data["status"] == "online"
    assert "IST" in data["time_ist"]
    assert data["scheduler"] == "manual_on_demand"
