import os
import time
import json
import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent

class PoseEstimationService:
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
            # Clean up raw frames
            shutil.rmtree(temp_frames_dir, ignore_errors=True)
            return {
                "ok": False,
                "message": "MediaPipe is not installed. Run 'pip install mediapipe' to enable automatic rotoscoping and pose estimation."
            }
            
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
            "frames": anchor_data
        }, indent=2), encoding="utf-8")
        
        return {
            "ok": True,
            "message": f"Successfully generated {frames_extracted} pose guidelines.",
            "frames_count": frames_extracted,
            "posepack_path": str(pose_pack_dir.relative_to(ROOT)).replace("\\", "/")
        }
