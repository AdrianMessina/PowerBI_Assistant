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
import math
import threading
from collections import Counter, defaultdict
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
        self._lock = threading.RLock()

    def log_event(self, event_name: str, data: Optional[Dict[str, Any]] = None,
                  username: Optional[str] = None,
                  conversation_id: Optional[str] = None):
        """Log an event to the daily JSONL file."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'session_id': self.session_id,
            'conversation_id': conversation_id,
            'username': (username or self.username or 'unknown').lower(),
            'hostname': self.hostname,
            'event': event_name,
            'data': data or {},
        }

        log_file = self.logs_dir / f"usage_{datetime.now().strftime('%Y%m%d')}.jsonl"
        try:
            with self._lock:
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"[WARN] Failed to log event: {e}")

    def log_chat(self, user_msg: str, response_len: int, duration_ms: int,
                 tone: str, cli_session: Optional[str] = None,
                 latency: Optional[Dict[str, Any]] = None,
                 username: Optional[str] = None,
                 project: Optional[str] = None,
                 token_usage: Optional[Dict[str, Any]] = None):
        """Log a chat interaction."""
        usage = dict(token_usage or {})
        actual_input = int(usage.get('input_tokens') or 0)
        actual_output = int(usage.get('output_tokens') or 0)
        if not token_usage:
            actual_input = max(1, math.ceil(len(user_msg or '') / 4))
            actual_output = max(1, math.ceil(int(response_len or 0) / 4))
        cache_creation = int(usage.get('cache_creation_input_tokens') or 0)
        cache_read = int(usage.get('cache_read_input_tokens') or 0)
        usage.update({
            'input_tokens': actual_input,
            'output_tokens': actual_output,
            'total_tokens': actual_input + actual_output + cache_creation + cache_read,
            'source': usage.get('source') or ('provider' if token_usage else 'estimated_chars'),
        })
        self.log_event('chat_message', {
            'message_preview': user_msg[:100],
            'message_length': len(user_msg or ''),
            'response_length': response_len,
            'duration_ms': duration_ms,
            'tone': tone,
            'cli_session': cli_session,
            'project': project,
            'tokens': usage,
            'latency': latency or {},
        }, username=username, conversation_id=cli_session)

    def get_all_events(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Read all events from JSONL files."""
        all_events = []
        with self._lock:
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

    def get_stats(self, username: Optional[str] = None) -> Dict[str, Any]:
        """Get aggregated usage statistics."""
        events = self.get_all_events()
        if username:
            events = [e for e in events if e.get('username', '').lower() == username.lower()]
        if not events:
            return {
                'total_events': 0, 'total_messages': 0,
                'unique_sessions': 0, 'unique_users': 0,
                'total_tokens': 0, 'input_tokens': 0, 'output_tokens': 0,
                'daily_activity': [], 'recent_events': [], 'by_user': [], 'by_project': [],
            }

        chat_events = [e for e in events if e['event'] == 'chat_message']
        sessions = {
            e.get('conversation_id') or e.get('data', {}).get('cli_session') or e.get('session_id')
            for e in chat_events
        }
        sessions.discard(None)
        users = set(e['username'] for e in events)

        # Daily activity (last 14 days)
        daily = Counter()
        for e in events:
            day = e['timestamp'][:10]  # YYYY-MM-DD
            daily[day] += 1

        daily_sorted = sorted(daily.items())[-14:]

        token_events = [e for e in events if isinstance(e.get('data', {}).get('tokens'), dict)]
        input_tokens = sum(int(e.get('data', {}).get('tokens', {}).get('input_tokens') or 0) for e in token_events)
        output_tokens = sum(int(e.get('data', {}).get('tokens', {}).get('output_tokens') or 0) for e in token_events)
        cache_tokens = sum(
            int(e.get('data', {}).get('tokens', {}).get('cache_creation_input_tokens') or 0)
            + int(e.get('data', {}).get('tokens', {}).get('cache_read_input_tokens') or 0)
            for e in token_events
        )

        user_rollup = defaultdict(lambda: {'messages': 0, 'tokens': 0, 'conversations': set()})
        project_rollup = defaultdict(lambda: {
            'messages': 0, 'tokens': 0, 'conversations': set(), 'uploads': 0,
            'estimated_context_tokens': 0,
        })
        for event in events:
            data = event.get('data', {})
            event_user = event.get('username') or 'unknown'
            project = data.get('project') or data.get('pbip_project') or 'Sin PBIP'
            conversation = event.get('conversation_id') or data.get('cli_session')
            tokens = int(data.get('tokens', {}).get('total_tokens') or 0)
            user_rollup[event_user]['tokens'] += tokens
            project_rollup[project]['tokens'] += tokens
            if event.get('event') == 'chat_message':
                user_rollup[event_user]['messages'] += 1
                project_rollup[project]['messages'] += 1
                if conversation:
                    user_rollup[event_user]['conversations'].add(conversation)
                    project_rollup[project]['conversations'].add(conversation)
            elif event.get('event') == 'pbip_uploaded':
                project_rollup[project]['uploads'] += 1
                project_rollup[project]['estimated_context_tokens'] = max(
                    project_rollup[project]['estimated_context_tokens'],
                    int(data.get('estimated_context_tokens') or 0),
                )

        by_user = [
            {'username': key, 'messages': value['messages'], 'tokens': value['tokens'],
             'conversations': len(value['conversations'])}
            for key, value in sorted(user_rollup.items())
        ]
        by_project = [
            {'project': key, 'messages': value['messages'], 'tokens': value['tokens'],
             'conversations': len(value['conversations']), 'uploads': value['uploads'],
             'estimated_context_tokens': value['estimated_context_tokens']}
            for key, value in sorted(project_rollup.items())
        ]

        return {
            'total_events': len(events),
            'total_messages': len(chat_events),
            'unique_sessions': len(sessions),
            'unique_users': len(users),
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'cache_tokens': cache_tokens,
            'total_tokens': input_tokens + output_tokens + cache_tokens,
            'daily_activity': [{'date': d, 'count': c} for d, c in daily_sorted],
            'recent_events': events[:20],
            'users': list(users),
            'by_user': by_user,
            'by_project': by_project,
        }
