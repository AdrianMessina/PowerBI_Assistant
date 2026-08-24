"""
Usage Logger for PBI Assistant
Adapted from ypf_bi_monitor/shared/usage_logger.py
Logs chat events to JSONL files for usage analytics.
"""

import json
import os
import socket
from pathlib import Path
from datetime import datetime
import uuid
from typing import Optional, Dict, Any, List


def _get_username() -> str:
    return os.environ.get('USERNAME', os.environ.get('USER', 'unknown')).lower()


def _get_hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return 'unknown'


class ChatLogger:
    """Logs PBI Assistant usage events to JSONL files."""

    def __init__(self, log_dir: Optional[str] = None):
        if log_dir:
            self.logs_dir = Path(log_dir)
        else:
            self.logs_dir = Path(__file__).parent / "logs"

        self.logs_dir.mkdir(exist_ok=True, parents=True)
        self.session_id = str(uuid.uuid4())[:8]
        self.username = _get_username()
        self.hostname = _get_hostname()

    def log_event(self, event_name: str, data: Optional[Dict[str, Any]] = None):
        """Log an event to the daily JSONL file."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'session_id': self.session_id,
            'username': self.username,
            'hostname': self.hostname,
            'event': event_name,
            'data': data or {},
        }

        log_file = self.logs_dir / f"usage_{datetime.now().strftime('%Y%m%d')}.jsonl"
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"[WARN] Failed to log event: {e}")

    def log_chat(self, user_msg: str, response_len: int, duration_ms: int,
                 tone: str, cli_session: Optional[str] = None):
        """Log a chat interaction."""
        self.log_event('chat_message', {
            'message_preview': user_msg[:100],
            'response_length': response_len,
            'duration_ms': duration_ms,
            'tone': tone,
            'cli_session': cli_session,
        })

    def get_all_events(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Read all events from JSONL files."""
        all_events = []
        for log_file in sorted(self.logs_dir.glob("usage_*.jsonl")):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            all_events.append(json.loads(line))
            except Exception as e:
                print(f"[WARN] Error reading {log_file.name}: {e}")

        all_events.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        if limit:
            return all_events[:limit]
        return all_events

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregated usage statistics."""
        events = self.get_all_events()
        if not events:
            return {
                'total_events': 0, 'total_messages': 0,
                'unique_sessions': 0, 'unique_users': 0,
                'daily_activity': [], 'recent_events': [],
            }

        chat_events = [e for e in events if e['event'] == 'chat_message']
        sessions = set(e['session_id'] for e in events)
        users = set(e['username'] for e in events)

        # Daily activity (last 14 days)
        from collections import Counter
        daily = Counter()
        for e in events:
            day = e['timestamp'][:10]  # YYYY-MM-DD
            daily[day] += 1

        daily_sorted = sorted(daily.items())[-14:]

        return {
            'total_events': len(events),
            'total_messages': len(chat_events),
            'unique_sessions': len(sessions),
            'unique_users': len(users),
            'daily_activity': [{'date': d, 'count': c} for d, c in daily_sorted],
            'recent_events': events[:20],
            'users': list(users),
        }
