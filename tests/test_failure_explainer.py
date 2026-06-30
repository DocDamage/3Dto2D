from services.failure_explainer_service import explain_failure

def test_explain_failure_cuda_oom():
    res = explain_failure("RuntimeError: CUDA out of memory. Tried to allocate 2.30 GiB")
    assert res["code"] == "cuda_oom"
    assert "GPU" in res["title"]
    assert res["action"]["kind"] == "retry_with_safer_profile"

def test_explain_failure_comfyui_unreachable():
    res = explain_failure("urllib.error.URLError: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>")
    assert res["code"] == "comfyui_unreachable"
    assert "ComfyUI" in res["title"]
    assert res["action"]["kind"] == "launch_comfyui"

def test_explain_failure_permission_denied():
    res = explain_failure("PermissionError: [WinError 5] Access is denied: 'output/temp'")
    assert res["code"] == "permission_denied"
    assert "permission" in res["title"].lower()
    assert res["action"]["kind"] == "check_folder_access"

def test_explain_failure_ffmpeg_missing():
    res = explain_failure("FileNotFoundError: [WinError 2] The system cannot find the file specified: 'ffmpeg'")
    assert res["code"] == "ffmpeg_missing"
    assert "FFmpeg" in res["title"]
    assert res["action"]["kind"] == "open_setup_docs"

def test_explain_failure_generic():
    res = explain_failure("Some completely unknown weird error message text here")
    assert res["code"] == "generic_error"
    assert "Job processing failed" in res["title"]
    assert res["action"] is None
