import os
import time
import json
import math
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from PIL import Image, ImageDraw
from spriteforge_utils import ROOT

logger = logging.getLogger(__name__)

class PoseEstimationService:
    @staticmethod
    def _largest_component_mask(mask):
        try:
            import cv2
            import numpy as np
        except Exception as exc:
            logger.warning("OpenCV/numpy unavailable for largest pose component mask; using original mask: %s", exc)
            return mask
        if mask is None or mask.size == 0:
            return mask
        num, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        if num <= 1:
            return mask
        best_idx = 1
        best_area = int(stats[1, cv2.CC_STAT_AREA])
        for idx in range(2, num):
            area = int(stats[idx, cv2.CC_STAT_AREA])
            if area > best_area:
                best_idx = idx
                best_area = area
        out = np.zeros_like(mask)
        out[labels == best_idx] = 255
        return out

    @staticmethod
    def _native_subject_mask(cv_bgr):
        """Build a coarse foreground mask without external ML dependencies."""
        try:
            import cv2
            import numpy as np
        except Exception as exc:
            logger.warning("OpenCV/numpy unavailable for native subject mask: %s", exc)
            return None

        h, w = cv_bgr.shape[:2]
        if h < 2 or w < 2:
            return None

        border = np.concatenate([
            cv_bgr[0, :, :],
            cv_bgr[h - 1, :, :],
            cv_bgr[1:h - 1, 0, :],
            cv_bgr[1:h - 1, w - 1, :],
        ], axis=0)
        bg_color = np.median(border.astype(np.float32), axis=0)

        diff = np.linalg.norm(cv_bgr.astype(np.float32) - bg_color[None, None, :], axis=2)
        mask = (diff > 32.0).astype(np.uint8) * 255

        kernel = np.ones((5, 5), dtype=np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        if int(mask.sum() // 255) < max(32, (h * w) // 200):
            gray = cv2.cvtColor(cv_bgr, cv2.COLOR_BGR2GRAY)
            _thr, alt = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            alt = cv2.morphologyEx(alt, cv2.MORPH_OPEN, kernel)
            alt = cv2.morphologyEx(alt, cv2.MORPH_CLOSE, kernel)
            if int(alt.sum() // 255) > int(mask.sum() // 255):
                mask = alt

        mask = PoseEstimationService._largest_component_mask(mask)
        return mask

    @staticmethod
    def _draw_native_pose(mask, canvas, w, h):
        """Draw a deterministic stick pose from silhouette bounds."""
        try:
            import cv2
            import numpy as np
        except Exception as exc:
            logger.warning("OpenCV/numpy unavailable for native pose drawing; using fallback anchors: %s", exc)
            return {
                "anchor_x": w / 2.0,
                "anchor_y": float(h),
                "left_heel_y": float(h),
                "right_heel_y": float(h),
            }

        draw = ImageDraw.Draw(canvas)
        ys, xs = np.where(mask > 0)
        if len(xs) < 8:
            return {
                "anchor_x": w / 2.0,
                "anchor_y": float(h),
                "left_heel_y": float(h),
                "right_heel_y": float(h),
            }

        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        bw = max(1, x1 - x0 + 1)
        bh = max(1, y1 - y0 + 1)

        cx = x0 + bw // 2
        shoulder_y = y0 + int(0.22 * bh)
        hip_y = y0 + int(0.56 * bh)
        knee_y = y0 + int(0.78 * bh)
        foot_y = y1

        shoulder_dx = max(6, int(0.18 * bw))
        hip_dx = max(4, int(0.10 * bw))
        hand_y = y0 + int(0.48 * bh)
        elbow_y = y0 + int(0.37 * bh)

        pts = {
            "head": (cx, y0 + int(0.10 * bh)),
            "neck": (cx, y0 + int(0.18 * bh)),
            "l_shoulder": (cx - shoulder_dx, shoulder_y),
            "r_shoulder": (cx + shoulder_dx, shoulder_y),
            "l_hip": (cx - hip_dx, hip_y),
            "r_hip": (cx + hip_dx, hip_y),
            "l_knee": (cx - hip_dx, knee_y),
            "r_knee": (cx + hip_dx, knee_y),
            "l_ankle": (cx - hip_dx, foot_y),
            "r_ankle": (cx + hip_dx, foot_y),
            "l_elbow": (cx - shoulder_dx - max(3, bw // 20), elbow_y),
            "r_elbow": (cx + shoulder_dx + max(3, bw // 20), elbow_y),
            "l_wrist": (cx - shoulder_dx - max(5, bw // 14), hand_y),
            "r_wrist": (cx + shoulder_dx + max(5, bw // 14), hand_y),
        }

        lines = [
            ((0, 0, 255), "l_shoulder", "r_shoulder"),
            ((0, 0, 255), "l_shoulder", "l_hip"),
            ((0, 0, 255), "r_shoulder", "r_hip"),
            ((0, 0, 255), "l_hip", "r_hip"),
            ((0, 255, 0), "l_shoulder", "l_elbow"),
            ((0, 255, 0), "l_elbow", "l_wrist"),
            ((255, 0, 0), "r_shoulder", "r_elbow"),
            ((255, 0, 0), "r_elbow", "r_wrist"),
            ((255, 255, 0), "l_hip", "l_knee"),
            ((255, 255, 0), "l_knee", "l_ankle"),
            ((255, 0, 255), "r_hip", "r_knee"),
            ((255, 0, 255), "r_knee", "r_ankle"),
            ((255, 255, 255), "neck", "head"),
        ]

        for color, a, b in lines:
            draw.line([pts[a], pts[b]], fill=color, width=4)
        for p in pts.values():
            draw.ellipse([(p[0] - 3, p[1] - 3), (p[0] + 3, p[1] + 3)], fill=(255, 255, 255))

        return {
            "anchor_x": float((pts["l_ankle"][0] + pts["r_ankle"][0]) / 2.0),
            "anchor_y": float(max(pts["l_ankle"][1], pts["r_ankle"][1])),
            "left_heel_y": float(pts["l_ankle"][1]),
            "right_heel_y": float(pts["r_ankle"][1]),
        }

    @staticmethod
    def _estimate_pose_native(frames_dir: Path, frames_extracted: int, pose_pack_dir: Path, w: int, h: int, action_name: str):
        import cv2

        anchor_data = []
        for idx in range(frames_extracted):
            frame_path = frames_dir / f"frame_{idx:04d}.png"
            cv_img = cv2.imread(str(frame_path))
            if cv_img is None:
                continue
            mask = PoseEstimationService._native_subject_mask(cv_img)
            pose_canvas = Image.new("RGB", (w, h), (0, 0, 0))
            if mask is not None:
                anchor = PoseEstimationService._draw_native_pose(mask, pose_canvas, w, h)
            else:
                anchor = {
                    "anchor_x": w / 2.0,
                    "anchor_y": float(h),
                    "left_heel_y": float(h),
                    "right_heel_y": float(h),
                }
            anchor_data.append({"frame": idx, **anchor})
            pose_canvas.save(pose_pack_dir / f"frame_{idx:04d}.png")

        if not anchor_data:
            for idx in range(frames_extracted):
                pose_canvas = Image.new("RGB", (w, h), (0, 0, 0))
                pose_canvas.save(pose_pack_dir / f"frame_{idx:04d}.png")
                anchor_data.append({
                    "frame": idx,
                    "anchor_x": w / 2.0,
                    "anchor_y": float(h),
                    "left_heel_y": float(h),
                    "right_heel_y": float(h),
                })

        anchor_file = pose_pack_dir / "anchors.json"
        anchor_file.write_text(json.dumps({
            "action": action_name,
            "width": w,
            "height": h,
            "backend": "native-opencv-fallback",
            "frames": anchor_data,
        }, indent=2), encoding="utf-8")

        return {
            "ok": True,
            "message": f"Generated {len(anchor_data)} pose guidelines using the native fallback estimator.",
            "frames_count": len(anchor_data),
            "posepack_path": str(pose_pack_dir.relative_to(ROOT)).replace("\\", "/"),
            "backend": "native-opencv-fallback",
        }

    @staticmethod
    def estimate_pose(video_path: str, project_dir: str, action_name: str) -> Dict[str, Any]:
        """Extract frames from video and run MediaPipe pose estimation to build a posepack."""
        # 1. Verify files and folders
        video = ROOT / video_path
        if not video.exists():
            return {"ok": False, "message": f"Video file not found at: {video_path}"}
            
        proj_dir = ROOT / project_dir
        if not proj_dir.exists():
            return {"ok": False, "message": f"Project directory not found at: {project_dir}"}
            
        # Target output folder for the pose pack
        pose_pack_dir = proj_dir / "posepacks" / action_name
        pose_pack_dir.mkdir(parents=True, exist_ok=True)
        
        # Temp folder to extract raw video frames
        import tempfile
        import shutil
        temp_frames_dir = Path(tempfile.gettempdir()) / f"pose_extract_{int(time.time())}"
        temp_frames_dir.mkdir(parents=True, exist_ok=True)
        
        # 2. Extract frames from video using OpenCV
        try:
            import cv2
        except ImportError:
            return {"ok": False, "message": "opencv-python is required. Install it using the dependency installer."}
            
        cap = cv2.VideoCapture(str(video))
        if not cap.isOpened():
            return {"ok": False, "message": f"Could not open video file: {video_path}"}
            
        frames_extracted = 0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 512
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 512
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            # Save frame
            frame_path = temp_frames_dir / f"frame_{frames_extracted:04d}.png"
            cv2.imwrite(str(frame_path), frame)
            frames_extracted += 1
            if frames_extracted >= 120:  # Safety cap at 120 frames
                break
        cap.release()
        
        if frames_extracted == 0:
            shutil.rmtree(temp_frames_dir, ignore_errors=True)
            return {"ok": False, "message": "No frames could be extracted from the video."}
            
        # 3. Try running MediaPipe pose estimation
        try:
            import mediapipe as mp
        except ImportError:
            try:
                result = PoseEstimationService._estimate_pose_native(
                    temp_frames_dir,
                    frames_extracted,
                    pose_pack_dir,
                    w,
                    h,
                    action_name,
                )
                return result
            finally:
                shutil.rmtree(temp_frames_dir, ignore_errors=True)
            
        # Initialize MediaPipe Pose
        mp_pose = mp.solutions.pose
        pose = mp_pose.Pose(static_image_mode=False, model_complexity=1, min_detection_confidence=0.5)
        
        # Draw connections mapping
        # Connection line color mapping: (R, G, B)
        CONN_COLORS = {
            # Torso (Blue)
            (mp_pose.PoseLandmark.LEFT_SHOULDER, mp_pose.PoseLandmark.RIGHT_SHOULDER): (0, 0, 255),
            (mp_pose.PoseLandmark.LEFT_SHOULDER, mp_pose.PoseLandmark.LEFT_HIP): (0, 0, 255),
            (mp_pose.PoseLandmark.RIGHT_SHOULDER, mp_pose.PoseLandmark.RIGHT_HIP): (0, 0, 255),
            (mp_pose.PoseLandmark.LEFT_HIP, mp_pose.PoseLandmark.RIGHT_HIP): (0, 0, 255),
            # Left Arm (Green)
            (mp_pose.PoseLandmark.LEFT_SHOULDER, mp_pose.PoseLandmark.LEFT_ELBOW): (0, 255, 0),
            (mp_pose.PoseLandmark.LEFT_ELBOW, mp_pose.PoseLandmark.LEFT_WRIST): (0, 255, 0),
            # Right Arm (Red)
            (mp_pose.PoseLandmark.RIGHT_SHOULDER, mp_pose.PoseLandmark.RIGHT_ELBOW): (255, 0, 0),
            (mp_pose.PoseLandmark.RIGHT_ELBOW, mp_pose.PoseLandmark.RIGHT_WRIST): (255, 0, 0),
            # Left Leg (Yellow)
            (mp_pose.PoseLandmark.LEFT_HIP, mp_pose.PoseLandmark.LEFT_KNEE): (255, 255, 0),
            (mp_pose.PoseLandmark.LEFT_KNEE, mp_pose.PoseLandmark.LEFT_ANKLE): (255, 255, 0),
            # Right Leg (Magenta)
            (mp_pose.PoseLandmark.RIGHT_HIP, mp_pose.PoseLandmark.RIGHT_KNEE): (255, 0, 255),
            (mp_pose.PoseLandmark.RIGHT_KNEE, mp_pose.PoseLandmark.RIGHT_ANKLE): (255, 0, 255),
        }
        
        anchor_data = []
        
        # Process each frame
        for idx in range(frames_extracted):
            frame_path = temp_frames_dir / f"frame_{idx:04d}.png"
            # Read back as RGB
            cv_img = cv2.imread(str(frame_path))
            cv_rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
            
            results = pose.process(cv_rgb)
            
            # Create a black background canvas
            pose_canvas = Image.new("RGB", (w, h), (0, 0, 0))
            draw = ImageDraw.Draw(pose_canvas)
            
            # If joints detected, draw skeleton
            if results.pose_landmarks:
                landmarks = results.pose_landmarks.landmark
                
                # Draw connections
                for conn, color in CONN_COLORS.items():
                    start_lm = landmarks[conn[0]]
                    end_lm = landmarks[conn[1]]
                    
                    if start_lm.visibility > 0.5 and end_lm.visibility > 0.5:
                        x1, y1 = int(start_lm.x * w), int(start_lm.y * h)
                        x2, y2 = int(end_lm.x * w), int(end_lm.y * h)
                        draw.line([(x1, y1), (x2, y2)], fill=color, width=4)
                        
                # Draw joint circles
                for lm_idx, landmark in enumerate(landmarks):
                    if landmark.visibility > 0.5:
                        lx, ly = int(landmark.x * w), int(landmark.y * h)
                        draw.ellipse([(lx - 4, ly - 4), (lx + 4, ly + 4)], fill=(255, 255, 255))
                
                # Collect feet position data to estimate center/heel ground anchors
                left_heel = landmarks[mp_pose.PoseLandmark.LEFT_HEEL]
                right_heel = landmarks[mp_pose.PoseLandmark.RIGHT_HEEL]
                
                gy = max(left_heel.y, right_heel.y) * h
                gx = ((left_heel.x + right_heel.x) / 2.0) * w
                
                anchor_data.append({
                    "frame": idx,
                    "anchor_x": gx,
                    "anchor_y": gy,
                    "left_heel_y": left_heel.y * h,
                    "right_heel_y": right_heel.y * h
                })
            else:
                anchor_data.append({
                    "frame": idx,
                    "anchor_x": w / 2.0,
                    "anchor_y": float(h),
                    "left_heel_y": float(h),
                    "right_heel_y": float(h)
                })
                
            # Save the final ControlNet pose guide frame
            pose_canvas.save(pose_pack_dir / f"frame_{idx:04d}.png")
            
        pose.close()
        shutil.rmtree(temp_frames_dir, ignore_errors=True)
        
        # Write anchor metadata to stabilize the characters during pack
        anchor_file = pose_pack_dir / "anchors.json"
        anchor_file.write_text(json.dumps({
            "action": action_name,
            "width": w,
            "height": h,
            "backend": "mediapipe",
            "frames": anchor_data
        }, indent=2), encoding="utf-8")
        
        return {
            "ok": True,
            "message": f"Successfully generated {frames_extracted} pose guidelines.",
            "frames_count": frames_extracted,
            "posepack_path": str(pose_pack_dir.relative_to(ROOT)).replace("\\", "/"),
            "backend": "mediapipe",
        }
