from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "app" / "web"


def test_lora_compare_plan_ui_is_wired():
    html = (WEB / "components" / "training.html").read_text(encoding="utf-8")
    js = (WEB / "js" / "app_forms.js").read_text(encoding="utf-8")

    assert 'id="loraComparePrompt"' in html
    assert 'id="previewTrainingDataset"' in html
    assert 'id="trainingDatasetPreview"' in html
    assert 'id="trainingDatasetDropzone"' in html
    assert 'id="trainingDatasetDropHint"' in html
    assert 'id="loraCompareNames"' in html
    assert 'id="buildLoraComparePlan"' in html
    assert 'id="applyLoraGpuDefaults"' in html
    assert 'id="loraGpuDefaultsHint"' in html
    assert "function buildLoraComparePlan" in js
    assert "function previewTrainingDataset" in js
    assert "function initTrainingDatasetBuilder" in js
    assert "event.dataTransfer" in js
    assert "event.clipboardData" in js
    assert "function applyLoraGpuDefaults" in js
    assert "/api/training-dataset/preview" in js
    assert "thumbnail_data_uri" in js
    css = (WEB / "css" / "components.css").read_text(encoding="utf-8")
    assert ".training-dataset-preview-row img" in css
    assert ".training-dataset-dropzone" in css
    assert "/api/lora/compare-plan" in js
    assert "/api/lora/recommended-defaults" in js
    assert "Compare Player" in html
