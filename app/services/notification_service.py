#!/usr/bin/env python3
"""Notification Service: Webhook and system notification support for SpriteForge."""
from __future__ import annotations

import json
import platform
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from spriteforge_utils import load_json, ROOT


def _get_hooks_config() -> Dict[str, Any]:
    """Load notification hooks from config."""
    config = load_json(ROOT / "config" / "spriteforge_config.json", {})
    return config.get("notifications", {})


def send_discord_webhook(webhook_url: str, content: str, title: str = "SpriteForge",
                         color: int = 0x00ADB5, fields: Optional[list] = None) -> bool:
    """Send a Discord webhook message with embed."""
    payload = {
        "embeds": [{
            "title": title,
            "description": content,
            "color": color,
            "timestamp": None,
        }]
    }
    if fields:
        payload["embeds"][0]["fields"] = fields
    
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def send_slack_webhook(webhook_url: str, text: str) -> bool:
    """Send a Slack incoming webhook message."""
    payload = {"text": text}
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def send_system_notification(title: str, message: str) -> bool:
    """Send a desktop system notification (cross-platform)."""
    try:
        system = platform.system()
        if system == "Windows":
            # Use PowerShell toast notification
            ps_cmd = (
                f'[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]'
                f' > $null; '
                f'$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent('
                f'[Windows.UI.Notifications.ToastTemplateType]::ToastText02); '
                f'$template.GetElementsByTagName("text")[0].AppendChild('
                f'$template.CreateTextNode("{title}")).InnerText = "{title}"; '
                f'$template.GetElementsByTagName("text")[1].AppendChild('
                f'$template.CreateTextNode("{message}")).InnerText = "{message}"'
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, timeout=10
            )
            return True
        elif system == "Darwin":
            subprocess.run([
                "osascript", "-e",
                f'display notification "{message}" with title "{title}"'
            ], capture_output=True, timeout=10)
            return True
        elif system == "Linux":
            subprocess.run([
                "notify-send", title, message
            ], capture_output=True, timeout=10)
            return True
    except Exception:
        pass
    return False


def notify_on_job_complete(job: Dict[str, Any]) -> Dict[str, bool]:
    """Fire configured notifications for a completed job.
    
    Returns dict of channel -> success bool.
    """
    hooks = _get_hooks_config()
    if not hooks or not hooks.get("enabled", False):
        return {}
    
    results: Dict[str, bool] = {}
    
    job_title = job.get("title", "Unknown Job")
    exit_code = job.get("exit_code", 0)
    status = "succeeded" if exit_code == 0 else "failed"
    status_emoji = "✅" if exit_code == 0 else "❌"
    duration = job.get("duration", "unknown")
    
    content = f"{status_emoji} SpriteForge job **{job_title}** {status}."
    detail_content = f"Job: {job_title}\nStatus: {status}\nDuration: {duration}\nExit Code: {exit_code}"
    
    # Discord
    discord_url = hooks.get("discord_webhook", "")
    if discord_url:
        color = 0x00FF00 if exit_code == 0 else 0xFF0000
        fields = [
            {"name": "Status", "value": status, "inline": True},
            {"name": "Duration", "value": str(duration), "inline": True},
            {"name": "Exit Code", "value": str(exit_code), "inline": True},
        ]
        results["discord"] = send_discord_webhook(discord_url, content, title=f"SpriteForge: {job_title}", color=color, fields=fields)
    
    # Slack
    slack_url = hooks.get("slack_webhook", "")
    if slack_url:
        results["slack"] = send_slack_webhook(slack_url, detail_content)
    
    # System notification
    if hooks.get("system_notify", False):
        results["system"] = send_system_notification(
            f"SpriteForge: {job_title} {status}",
            detail_content
        )
    
    return results


def notify_on_job_start(job: Dict[str, Any]) -> Dict[str, bool]:
    """Fire configured notifications when a job starts."""
    hooks = _get_hooks_config()
    if not hooks or not hooks.get("enabled", False):
        return {}
    
    results: Dict[str, bool] = {}
    
    job_title = job.get("title", "Unknown Job")
    content = f"🔄 SpriteForge job started: **{job_title}**"
    detail_content = f"Job started: {job_title}"
    
    discord_url = hooks.get("discord_webhook", "")
    if discord_url:
        results["discord"] = send_discord_webhook(
            discord_url, content, title="SpriteForge: Job Started", color=0x3498DB
        )
    
    slack_url = hooks.get("slack_webhook", "")
    if slack_url:
        results["slack"] = send_slack_webhook(slack_url, detail_content)
    
    if hooks.get("system_notify", False):
        results["system"] = send_system_notification(
            f"SpriteForge: Started {job_title}",
            detail_content
        )
    
    return results


def is_enabled() -> bool:
    """Check if notifications are configured and enabled."""
    hooks = _get_hooks_config()
    return bool(hooks.get("enabled", False))


def get_config_summary() -> Dict[str, Any]:
    """Get a summary of notification configuration (hides secrets)."""
    hooks = _get_hooks_config()
    summary = {
        "enabled": bool(hooks.get("enabled", False)),
        "system_notify": bool(hooks.get("system_notify", False)),
        "discord": bool(hooks.get("discord_webhook", "")),
        "slack": bool(hooks.get("slack_webhook", "")),
    }
    return summary