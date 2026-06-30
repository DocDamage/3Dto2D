from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from pathlib import Path
from typing import List, Optional

from spriteforge_utils import load_json, save_json
from services.easy_helpers import (
    resolve_root_path,
    short_path,
    open_path,
)

ROOT = Path(__file__).resolve().parent.parent
DROP_VIDEOS_DIR = ROOT / "01_DROP_VIDEOS_HERE"
IMAGE_EXTS = ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp")

class EasyUiTabsMixin:
    def _convert_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        tab.columnconfigure(0, weight=1)
        self.convert_tab_ref = tab
        self.notebook.add(tab, text="Convert Video")

        form = self.section(tab, "Convert an existing WAN / ComfyUI video into a spritesheet", 0, 0, sticky="ew")
        self.video_file_var = self.v("video_file", "")
        self.video_output_name_var = self.v("video_output_name", "")
        self.video_fps_var = self.v("video_fps", "12")
        self.cell_size_var = self.v("cell_size", "512x512")
        self.key_color_var = self.v("key_color", "auto")
        self.key_tolerance_var = self.v("key_tolerance", "45")
        self.make_text_row(form, "Video file", self.video_file_var, 0, browse=self.browse_video_file)
        self.make_text_row(form, "Output name (optional)", self.video_output_name_var, 1)
        self.make_text_row(form, "FPS", self.video_fps_var, 2, width=20)
        self.make_text_row(form, "Cell size", self.cell_size_var, 3, width=20)
        self.make_text_row(form, "Key color", self.key_color_var, 4, width=20)
        self.make_text_row(form, "Key tolerance", self.key_tolerance_var, 5, width=20)
        ttk.Button(form, text="Convert Video to Sprite", command=self.convert_video).grid(row=6, column=1, sticky="ew", pady=(10, 0))
        ttk.Button(form, text="Inspect Video First", command=self.inspect_video).grid(row=6, column=2, sticky="ew", padx=(6, 0), pady=(10, 0))
        ttk.Button(form, text="Open Drop Folder", command=lambda: open_path(DROP_VIDEOS_DIR)).grid(row=7, column=1, sticky="ew", pady=(8, 0))
        ttk.Button(form, text="Convert All Videos in Drop Folder", command=self.convert_drop_folder).grid(row=7, column=2, sticky="ew", padx=(6, 0), pady=(8, 0))

        note = self.section(tab, "Tip", 1, 0, sticky="ew")
        ttk.Label(note, text="Best results: generate the source video on a plain green/blue background with a locked camera and full-body character.").grid(row=0, column=0, sticky="w")

    def _qa_export_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        self.qa_tab_ref = tab
        self.notebook.add(tab, text="QA / Export")

        select = self.section(tab, "Select sprite output", 0, 0, 2, "ew")
        self.sprite_dir_var = self.v("sprite_dir", "")
        self.make_text_row(select, "Sprite folder", self.sprite_dir_var, 0, browse=self.browse_sprite_dir)
        ttk.Button(select, text="Use Most Recent Output", command=self.use_most_recent_output).grid(row=1, column=1, sticky="ew", pady=(8, 0))
        ttk.Button(select, text="Open Selected Folder", command=self.open_sprite_dir).grid(row=1, column=2, sticky="ew", padx=(6, 0), pady=(8, 0))

        qa = self.section(tab, "Fix / quality", 1, 0)
        self.blend_loop_frames_var = self.v("blend_loop_frames", "3")
        ttk.Button(qa, text="Run QA Report", command=self.qa_report).grid(row=0, column=0, columnspan=2, sticky="ew", pady=4)
        ttk.Button(qa, text="Auto-Fix Sprite", command=self.autofix_sprite).grid(row=1, column=0, columnspan=2, sticky="ew", pady=4)
        ttk.Button(qa, text="Open report.html", command=self.open_report_html).grid(row=2, column=0, columnspan=2, sticky="ew", pady=4)
        
        ttk.Label(qa, text="Loop Blend Frames:").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(qa, textvariable=self.blend_loop_frames_var, width=6).grid(row=3, column=1, sticky="w", pady=4)
        
        qa.columnconfigure(0, weight=1)
        qa.columnconfigure(1, weight=1)

        export = self.section(tab, "Export", 1, 1)
        ttk.Button(export, text="Export to Godot", command=lambda: self.export_engine("godot")).grid(row=0, column=0, sticky="ew", pady=4)
        ttk.Button(export, text="Export to Unity", command=lambda: self.export_engine("unity")).grid(row=1, column=0, sticky="ew", pady=4)
        ttk.Button(export, text="Build Atlas from Output Folder", command=self.build_atlas_from_output_root).grid(row=2, column=0, sticky="ew", pady=4)
        export.columnconfigure(0, weight=1)

        self.qa_summary_panel = self.section(tab, "QA Report Summary", 2, 0, 2, "ew")
        self.qa_summary_inner = ttk.Frame(self.qa_summary_panel)
        self.qa_summary_inner.pack(fill="both", expand=True)
        
        self.sprite_dir_var.trace_add("write", lambda *args: self.update_qa_summary())
        self.after(500, self.update_qa_summary)

    def update_qa_summary(self, folder: Path = None) -> None:
        if folder is None:
            val = self.sprite_dir_var.get().strip()
            if val:
                folder = Path(val)
                if not folder.is_absolute():
                    folder = ROOT / folder
            
        for widget in self.qa_summary_inner.winfo_children():
            widget.destroy()
            
        if not folder or not folder.exists():
            ttk.Label(self.qa_summary_inner, text="No folder selected", font=("Segoe UI", 10, "italic")).pack(anchor="w")
            return
            
        report_path = folder / "qa" / "qa_report.json"
        if not report_path.exists():
            ttk.Label(self.qa_summary_inner, text="No QA report found. Click 'Run QA Report' to analyze this sprite.", font=("Segoe UI", 10, "italic")).pack(anchor="w")
            return
            
        try:
            report = load_json(report_path)
            metrics = report.get("metrics", {})
            issues = report.get("issues", [])
            
            status_text = "PASS"
            status_color = "green"
            if issues:
                has_error = any(it.get("level") == "error" for it in issues)
                status_text = "FAIL" if has_error else "WARN"
                status_color = "#ff4444" if has_error else "#ffaa00"
                
            badge_frame = ttk.Frame(self.qa_summary_inner)
            badge_frame.pack(fill="x", pady=(0, 6))
            ttk.Label(badge_frame, text="Overall QA Status: ", font=("Segoe UI", 10, "bold")).pack(side="left")
            
            badge = tk.Label(badge_frame, text=status_text, font=("Segoe UI", 10, "bold"), fg=status_color, bg="#1e1e1e")
            badge.pack(side="left")
            
            grid_frame = ttk.Frame(self.qa_summary_inner)
            grid_frame.pack(fill="x", pady=4)
            for i in range(3):
                grid_frame.columnconfigure(i, weight=1)
            
            def add_metric(label, val, row, col, unit=""):
                f = ttk.Frame(grid_frame)
                f.grid(row=row, column=col, sticky="w", padx=10, pady=2)
                ttk.Label(f, text=label, font=("Segoe UI", 9, "bold")).pack(anchor="w")
                ttk.Label(f, text=f"{val} {unit}".strip(), font=("Segoe UI", 9)).pack(anchor="w")
                
            add_metric("Loop Seam RMSE", f"{metrics.get('loop_seam_rmse', 0.0):.2f}", 0, 0)
            add_metric("Center Jitter (X stdev)", f"{metrics.get('center_x_stdev_px', 0.0):.2f}", 0, 1, "px")
            add_metric("Foot Drift (Y stdev)", f"{metrics.get('foot_y_stdev_px', 0.0):.2f}", 0, 2, "px")
            add_metric("Brightness Flicker", f"{metrics.get('brightness_stdev', 0.0):.2f}", 1, 0)
            add_metric("Duplicate Frames", f"{len(metrics.get('duplicate_frames_after_previous', []))}", 1, 1)
            add_metric("Total Issues", f"{len(issues)}", 1, 2)
            
            if issues:
                ttk.Label(self.qa_summary_inner, text="Issues / Suggestions:", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(8, 2))
                issues_text = ScrolledText(self.qa_summary_inner, height=4, wrap="word", font=("Segoe UI", 8), bg="#121212", fg="#e0e0e0", insertbackground="#e0e0e0", bd=0, highlightthickness=1, highlightbackground="#3a3a3a", highlightcolor="#00adb5")
                issues_text.pack(fill="both", expand=True)
                for it in issues:
                    issues_text.insert(tk.END, f"• [{it.get('level').upper()}] {it.get('message')}\n")
                issues_text.config(state="disabled")
        except Exception as exc:
            ttk.Label(self.qa_summary_inner, text=f"Error reading QA report: {exc}", font=("Segoe UI", 10, "italic")).pack(anchor="w")

    def _project_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        tab.columnconfigure(0, weight=1)
        self.notebook.add(tab, text="Character Pack")

        form = self.section(tab, "Create a reusable character pack", 0, 0, sticky="ew")
        self.pack_name_var = self.v("pack_name", "hero")
        self.pack_description_var = self.v("pack_description", "single full body original game hero, simple outfit, boots, clean silhouette")
        self.pack_actions_var = self.v("pack_actions", "idle,walk,run,attack_light,hurt")
        self.pack_directions_var = self.v("pack_directions", "right")
        self.pack_reference_var = self.v("pack_reference", "")
        
        self.make_text_row(form, "Pack name", self.pack_name_var, 0, width=30)
        self.make_text_row(form, "Character description", self.pack_description_var, 1)
        
        self.make_text_row(form, "Actions", self.pack_actions_var, 2)
        
        self.actions_warning_lbl = ttk.Label(form, text="✓ Actions valid", font=("Segoe UI", 9))
        self.actions_warning_lbl.grid(row=3, column=1, sticky="w", pady=(0, 6))
        self.pack_actions_var.trace_add("write", self._validate_pack_actions)
        
        self.make_text_row(form, "Directions", self.pack_directions_var, 4)
        self.make_text_row(form, "Reference image optional", self.pack_reference_var, 5, browse=self.browse_pack_reference)
        ttk.Button(form, text="Create Character Pack", command=self.create_character_pack).grid(row=6, column=1, sticky="ew", pady=(10, 0))
        ttk.Button(form, text="Build Batch Plan From Pack", command=self.build_batch_plan).grid(row=6, column=2, sticky="ew", padx=(6, 0), pady=(10, 0))
        
        self._validate_pack_actions()

    def _validate_pack_actions(self, *args) -> None:
        val = self.pack_actions_var.get().strip()
        if not val:
            self.actions_warning_lbl.config(text="⚠️ Warning: Actions field cannot be blank", foreground="orange")
            return
            
        from spriteforge_prompts import ACTION_TEMPLATES
        actions = [a.strip() for a in val.split(",") if a.strip()]
        invalid = [a for a in actions if a not in ACTION_TEMPLATES]
        if invalid:
            self.actions_warning_lbl.config(
                text=f"⚠️ Unknown actions: {', '.join(invalid)}. (Standard: {', '.join(sorted(ACTION_TEMPLATES.keys()))})",
                foreground="orange"
            )
        else:
            self.actions_warning_lbl.config(text="✓ Actions valid", foreground="green")

    def _jobs_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        self.notebook.add(tab, text="Jobs Queue")
        
        top = ttk.Frame(tab)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        top.columnconfigure(1, weight=1)
        
        ttk.Label(top, text="Select Queue: ").pack(side="left")
        self.queue_selector = ttk.Combobox(top, state="readonly", width=30)
        self.queue_selector.pack(side="left", padx=4)
        self.queue_selector.bind("<<ComboboxSelected>>", lambda e: self.refresh_jobs_status())
        
        self.jobs_summary_lbl = ttk.Label(top, text="Pending: 0 | Running: 0 | Done: 0 | Failed: 0", font=("Segoe UI", 9, "bold"))
        self.jobs_summary_lbl.pack(side="right", padx=10)
        
        tree_frame = ttk.Frame(tab)
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        cols = ("id", "action", "direction", "status", "exit_code")
        self.jobs_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        self.jobs_tree.grid(row=0, column=0, sticky="nsew")
        
        self.jobs_tree.heading("id", text="Job ID")
        self.jobs_tree.heading("action", text="Action")
        self.jobs_tree.heading("direction", text="Direction")
        self.jobs_tree.heading("status", text="Status")
        self.jobs_tree.heading("exit_code", text="Exit Code")
        
        self.jobs_tree.column("id", width=180, anchor="w")
        self.jobs_tree.column("action", width=120, anchor="center")
        self.jobs_tree.column("direction", width=100, anchor="center")
        self.jobs_tree.column("status", width=100, anchor="center")
        self.jobs_tree.column("exit_code", width=80, anchor="center")
        
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.jobs_tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.jobs_tree.configure(yscrollcommand=sb.set)
        
        btns = ttk.Frame(tab)
        btns.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(btns, text="Run Queue", command=self.run_selected_queue).pack(side="left", padx=4)
        ttk.Button(btns, text="Reset Queue", command=self.reset_selected_queue).pack(side="left", padx=4)
        ttk.Button(btns, text="Delete Job", command=self.delete_selected_job).pack(side="left", padx=4)
        ttk.Button(btns, text="Refresh", command=self.refresh_jobs_status).pack(side="left", padx=4)
        
        self.after(400, self.refresh_jobs_status)

    def refresh_jobs_status(self) -> None:
        jobs_dir = ROOT / "output" / "jobs"
        jobs_dir.mkdir(parents=True, exist_ok=True)
        queues = sorted([p.name for p in jobs_dir.glob("*_queue.json")])
        
        self.queue_selector["values"] = queues
        
        current = self.queue_selector.get()
        if not current and queues:
            if "gui_queue_queue.json" in queues:
                current = "gui_queue_queue.json"
            elif any(x.startswith("gui_queue") for x in queues):
                current = [x for x in queues if x.startswith("gui_queue")][0]
            else:
                current = queues[0]
            self.queue_selector.set(current)
            
        self.jobs_tree.delete(*self.jobs_tree.get_children())
        if not current:
            self.jobs_summary_lbl.config(text="No queues found.")
            return
            
        qpath = jobs_dir / current
        data = load_json(qpath, {})
        jobs = data.get("jobs", [])
        
        counts = {"pending": 0, "running": 0, "done": 0, "failed": 0, "interrupted": 0}
        for j in jobs:
            status = j.get("status", "pending")
            counts[status] = counts.get(status, 0) + 1
            self.jobs_tree.insert("", "end", iid=j.get("id"), values=(
                j.get("id"),
                j.get("action", ""),
                j.get("direction", ""),
                status.upper(),
                j.get("exit_code", "") if j.get("exit_code") is not None else "-"
            ))
            
        self.jobs_summary_lbl.config(text=f"Pending: {counts.get('pending', 0)} | Running: {counts.get('running', 0)} | Done: {counts.get('done', 0)} | Failed: {counts.get('failed', 0)}")

    def run_selected_queue(self) -> None:
        current = self.queue_selector.get()
        if not current:
            messagebox.showwarning("No queue", "Select a queue to run first.")
            return
        qpath = ROOT / "output" / "jobs" / current
        cmd = self.pycmd("spriteforge_queue.py", "run", "--queue", str(qpath), "--continue-on-error")
        
        def done(code: int):
            self.refresh_jobs_status()
            if code == 0:
                messagebox.showinfo("Queue Done", "The job queue completed successfully.")
            else:
                messagebox.showwarning("Queue Finished", "Queue completed with some failed jobs.")
                
        self.runner.run(f"Run Queue: {current}", cmd, on_done=done)

    def reset_selected_queue(self) -> None:
        current = self.queue_selector.get()
        if not current:
            return
        qpath = ROOT / "output" / "jobs" / current
        data = load_json(qpath, {})
        for j in data.get("jobs", []):
            j["status"] = "pending"
            j["started_at"] = None
            j["finished_at"] = None
            j["exit_code"] = None
        save_json(qpath, data)
        self.refresh_jobs_status()
        messagebox.showinfo("Queue Reset", f"All jobs in queue '{current}' have been reset to pending.")

    def delete_selected_job(self) -> None:
        current = self.queue_selector.get()
        if not current:
            return
        sel = self.jobs_tree.selection()
        if not sel:
            messagebox.showwarning("No job selected", "Choose a job from the list first.")
            return
        job_id = sel[0]
        qpath = ROOT / "output" / "jobs" / current
        data = load_json(qpath, {})
        jobs = data.get("jobs", [])
        new_jobs = [j for j in jobs if j.get("id") != job_id]
        data["jobs"] = new_jobs
        save_json(qpath, data)
        self.refresh_jobs_status()

    def enqueue_job(self, name: str, cmd: List[str], action: str = "custom", direction: str = "none") -> None:
        jobs_dir = ROOT / "output" / "jobs"
        jobs_dir.mkdir(parents=True, exist_ok=True)
        qpath = jobs_dir / "gui_queue_queue.json"
        
        data = load_json(qpath, None)
        if not data or "jobs" not in data:
            import datetime as dt
            data = {
                "schema": "spriteforge_queue_v12",
                "name": "gui_queue",
                "created_at": dt.datetime.now().isoformat(timespec="seconds"),
                "jobs": []
            }
            
        import datetime as dt
        idx = len(data["jobs"]) + 1
        job_id = f"{idx:03d}_{action}_{direction}_{int(time.time())}"
        
        job = {
            "id": job_id,
            "action": action,
            "direction": direction,
            "status": "pending",
            "created_at": dt.datetime.now().isoformat(timespec="seconds"),
            "started_at": None,
            "finished_at": None,
            "exit_code": None,
            "command": cmd,
            "log": None,
        }
        data["jobs"].append(job)
        save_json(qpath, data)
        self.log(f"Enqueued job {job_id} to gui_queue_queue.json\n")
        self.refresh_jobs_status()

    def _advanced_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=12)
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        self.notebook.add(tab, text="Advanced")

        cloud = self.section(tab, "Remote / cloud ComfyUI", 0, 0, 2, "ew")
        self.remote_server_var = self.v("remote_server", "http://YOUR_SERVER:8188")
        self.remote_workflow_var = self.v("remote_workflow", "")
        self.remote_prompt_var = self.v("remote_prompt", "single full body original game character walking cycle, professional appealing character design, heroic adult proportions, distinctive outfit, crisp cel-shaded edges, side view, plain green background")
        self.make_text_row(cloud, "Server", self.remote_server_var, 0)
        self.make_text_row(cloud, "Workflow API JSON", self.remote_workflow_var, 1, browse=self.browse_remote_workflow)
        self.make_text_row(cloud, "Prompt", self.remote_prompt_var, 2)
        ttk.Button(cloud, text="Remote Generate + Convert", command=self.remote_generate).grid(row=3, column=1, sticky="ew", pady=(10, 0))

        maint = self.section(tab, "Maintenance", 1, 0)
        ttk.Button(maint, text="Create Snapshot", command=self.snapshot).grid(row=0, column=0, sticky="ew", pady=4)
        ttk.Button(maint, text="Safe Update", command=self.safe_update).grid(row=1, column=0, sticky="ew", pady=4)
        ttk.Button(maint, text="Model Report", command=self.model_report).grid(row=2, column=0, sticky="ew", pady=4)
        ttk.Button(maint, text="Open Model Download Pages", command=self.open_model_pages).grid(row=3, column=0, sticky="ew", pady=4)
        maint.columnconfigure(0, weight=1)

        docs = self.section(tab, "Guides", 1, 1)
        ttk.Button(docs, text="Open End User Guide", command=lambda: open_path(ROOT / "docs" / "END_USER_GUIDE.md")).grid(row=0, column=0, sticky="ew", pady=4)
        ttk.Button(docs, text="Open One-Page Cheat Sheet", command=lambda: open_path(ROOT / "docs" / "ONE_PAGE_CHEAT_SHEET.md")).grid(row=1, column=0, sticky="ew", pady=4)
        ttk.Button(docs, text="Open Advanced README", command=lambda: open_path(ROOT / "docs" / "README_ADVANCED_v6_BASE.md")).grid(row=2, column=0, sticky="ew", pady=4)
        docs.columnconfigure(0, weight=1)
