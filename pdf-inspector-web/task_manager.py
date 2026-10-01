#!/usr/bin/env python3
# task_manager.py
"""
輕量級任務管理器（替代 Celery）

使用 Python 內建的 ThreadPoolExecutor 實現異步任務：
- 提交任務後立即返回 task_id
- 任務在後台線程中執行
- 結果存儲在內存字典中
- 前端通過 task_id 查詢進度

適合比賽演示，無需 Redis/Celery。
"""

import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Callable, Any


class TaskManager:
    """線程池任務管理器"""

    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.tasks = {}          # {task_id: task_info}
        self.lock = threading.Lock()

    def submit(self, func: Callable, *args, **kwargs) -> str:
        """
        提交任務
        返回 task_id，可立即用於查詢進度
        """
        task_id = str(uuid.uuid4())

        with self.lock:
            self.tasks[task_id] = {
                'task_id': task_id,
                'state': 'PENDING',
                'result': None,
                'created_at': datetime.now().isoformat(),
            }

        # 提交到線程池
        future = self.executor.submit(func, *args, **kwargs)
        future.add_done_callback(
            lambda f: self._on_task_done(task_id, f)
        )

        # 立即更新狀態為 PROCESSING
        with self.lock:
            self.tasks[task_id]['state'] = 'PROCESSING'

        return task_id

    def _on_task_done(self, task_id: str, future):
        """任務完成回調"""
        with self.lock:
            try:
                result = future.result()
                self.tasks[task_id]['state'] = 'SUCCESS'
                self.tasks[task_id]['result'] = result
            except Exception as e:
                self.tasks[task_id]['state'] = 'FAILURE'
                self.tasks[task_id]['result'] = {
                    'status': 'failed',
                    'reason': f'{type(e).__name__}: {str(e)}'
                }

    def get_status(self, task_id: str) -> dict:
        """查詢任務狀態"""
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return {
                    'task_id': task_id,
                    'state': 'UNKNOWN',
                    'ready': False,
                    'result': None,
                }
            return {
                'task_id': task_id,
                'state': task['state'],
                'ready': task['state'] in ('SUCCESS', 'FAILURE'),
                'result': task['result'],
            }

    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """清理過期任務（可選）"""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        with self.lock:
            to_remove = [
                tid for tid, t in self.tasks.items()
                if datetime.fromisoformat(t['created_at']) < cutoff
            ]
            for tid in to_remove:
                del self.tasks[tid]


# 全局單例
task_manager = TaskManager(max_workers=4)