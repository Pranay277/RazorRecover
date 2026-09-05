"""Asynchronous recovery execution layer (Celery + Redis).

The API enqueues work through :mod:`razor_recover.tasks.queue`; the
:mod:`razor_recover.tasks.recovery_task` adapter runs the existing recovery
workflow in a Celery worker. No recovery logic is duplicated here.
"""