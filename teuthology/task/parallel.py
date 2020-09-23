"""
Task to group parallel running tasks
"""
import os
import sys
import logging

from teuthology import run_tasks
from teuthology.run_tasks import generate_unique_name, add_file_handler, \
    remove_log_handler, formatter, get_log_level, all_tasks, get_task
from teuthology import parallel

log = logging.getLogger(__name__)

parallel_tasks = list()


def task(ctx, config, **kwargs):
    """
    Run a group of tasks in parallel.

    example::

        - parallel:
           - tasktest:
           - tasktest:

    You can also define tasks in a top-level section outside of
    'tasks:', and reference them here.

    The referenced section must contain a list of tasks to run
    sequentially, or a single task as a dict. The latter is only
    available for backwards compatibility with existing suites::

        tasks:
        - parallel:
          - tasktest: # task inline
          - foo       # reference to top-level 'foo' section
          - bar       # reference to top-level 'bar' section
        foo:
        - tasktest1:
        - tasktest2:
        bar:
          tasktest: # note the list syntax from 'foo' is preferred

    That is, if the entry is not a dict, we will look it up in the top-level
    config.

    Sequential tasks and Parallel tasks can be nested.
    """

    log.info('starting parallel...')
    main_task = {} if not all_tasks else all_tasks[-1]
    archive_path = ctx.config.get('archive_path')
    with parallel.parallel() as p:
        for entry in config:
            if not isinstance(entry, dict):
                entry = ctx.config.get(entry, {})
                # support the usual list syntax for tasks
                if isinstance(entry, list):
                    entry = dict(sequential=entry)
            ((taskname, confg),) = entry.items()
            log_path = None
            log_level = None
            if taskname.lower() not in "parallel" and archive_path:
                log_level = get_log_level(ctx)
                log_task_dir = os.path.dirname(main_task.get('log_file'))
                log_path = os.path.join(log_task_dir, main_task.get('name'))
                os.makedirs(log_path, exist_ok=True)
            p.spawn(_run_spawned, ctx, confg, taskname,
                    log_level=log_level, log_path=log_path, **kwargs)


def _run_spawned(ctx, config, taskname, **kwargs):
    """Run one of the tasks (this runs in parallel with others)"""
    mgr = {}
    handler = None
    log_path = kwargs.get('log_path')
    log_level = kwargs.get('log_level')

    # Configure logger
    if log_path:
        file_name = generate_unique_name(taskname, parallel_tasks)
        module = get_task(taskname)
        module.__init__(name=file_name.strip(".log"))
        logger = logging.getLogger(taskname)
        log_file = os.path.join(log_path, file_name)
        handler = add_file_handler(logger, log_level,
                                   formatter, log_file)
    try:

        log.info('In parallel, running task %s...' % taskname)
        mgr = run_tasks.run_one_task(taskname, ctx=ctx, config=config)
        if hasattr(mgr, '__enter__'):
            mgr.__enter__()
    finally:
        remove_log_handler(handler)
        exc_info = sys.exc_info()
        if hasattr(mgr, '__exit__'):
            mgr.__exit__(*exc_info)
        del exc_info
