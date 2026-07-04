from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"


def test_cloud_hub_assets_are_wired():
    index = (APP / "web" / "index.html").read_text(encoding="utf-8")
    component = (APP / "web" / "components" / "cloud_hub.html").read_text(encoding="utf-8")
    script = (APP / "web" / "js" / "cloud_hub.js").read_text(encoding="utf-8")
    css = (APP / "web" / "cloud_hub.css").read_text(encoding="utf-8")

    assert "cloud_hub.css" in index
    assert "'cloud_hub'" in index
    assert 'data-view="cloud_hub"' in index
    assert "js/cloud_hub.js" in index
    assert 'id="cloudHubNodes"' in component
    assert 'id="cloudImageProviders"' in component
    assert 'id="cloudImagePlanPreview"' in component
    assert 'id="cloudImageGenerate"' in component
    assert 'id="cloudImagePlanModel"' in component
    assert 'id="cloudImagePlanSourceImages"' in component
    assert 'id="cloudImagePlanResult"' in component
    assert 'id="cloudQueuePlanPreview"' in component
    assert 'id="cloudQueuePlanResult"' in component
    assert 'id="cloudHubNodeMaxJobs"' in component
    assert 'id="cloudHubNodeStatus"' in component
    assert "/api/cloud/nodes" in script
    assert "/api/cloud/image-providers" in script
    assert "/api/cloud/image-generation-plan" in script
    assert "runAction('cloud_image_sprite'" in script
    assert "function generateCloudImageSprite" in script
    assert "/api/cloud/queue-plan" in script
    assert "renderCloudImagePlan" in script
    assert "renderCloudQueuePlan" in script
    assert "renderCloudHubSkeleton" in script
    assert "Planning remote queue distribution" in script
    assert "Planning cloud image sprite" in script
    assert "active_jobs" in script
    assert "max_jobs" in script
    assert "data-cloud-state" in script
    assert 'data-cloud-status="draining"' in script
    assert 'data-cloud-enabled="false"' in script
    assert "function updateCloudHubNodeState" in script
    assert "installCloudHub" in script
    assert ".cloud-hub-layout" in css
    assert ".cloud-hub-node .compact-actions" in css
