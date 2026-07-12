# AIMETA P=Celery配置_异步任务队列设置|R=Celery应用_任务路由_序列化|NR=不含任务定义|E=celery_app|X=job|A=Celery实例|D=celery,redis|S=net|RD=./README.ai
import os
from celery import Celery
from kombu import Exchange, Queue
from dotenv import load_dotenv

load_dotenv()

# 创建 Celery 应用
app = Celery(
    'mofeng',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1'),
)

# Celery 配置
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 分钟
    task_soft_time_limit=25 * 60,  # 25 分钟
    result_expires=3600,  # 结果保留 1 小时
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# 定义任务队列
app.conf.task_queues = (
    Queue('emotion_analysis', Exchange('emotion_analysis'), routing_key='emotion_analysis'),
    Queue('default', Exchange('default'), routing_key='default'),
)

# 定义任务路由
app.conf.task_routes = {
    'app.tasks.emotion_tasks.analyze_emotion_async': {'queue': 'emotion_analysis'},
}

# Celery worker 进程级共享 async engine（避免每个任务重复 create/dispose）
from celery.signals import worker_process_init, worker_process_shutdown  # noqa: E402

_async_engine = None
AsyncSessionLocal = None


@worker_process_init.connect
def _init_worker_engine(**kwargs):
    """worker 子进程启动时建一次共享 engine 与 session factory。"""
    global _async_engine, AsyncSessionLocal
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    _async_engine = create_async_engine(settings.sqlalchemy_database_uri, echo=False)
    AsyncSessionLocal = sessionmaker(_async_engine, class_=AsyncSession, expire_on_commit=False)


@worker_process_shutdown.connect
def _shutdown_worker_engine(**kwargs):
    """worker 子进程退出时释放共享 engine。"""
    global _async_engine, AsyncSessionLocal
    if _async_engine is not None:
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(_async_engine.dispose())
            loop.close()
        except Exception:  # noqa: BLE001
            pass
    _async_engine = None
    AsyncSessionLocal = None


def get_task_session_factory():
    """返回 (session_factory, own_engine)。

    worker 进程内复用共享 factory（own_engine=None）；非 worker 环境（如直接调用/测试）
    建临时 engine，由调用方在用完后 dispose。
    """
    if AsyncSessionLocal is not None:
        return AsyncSessionLocal, None
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    engine = create_async_engine(settings.sqlalchemy_database_uri, echo=False)
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine

# 定义定时任务（可选）
app.conf.beat_schedule = {
    # 可以在这里添加定时任务
}

if __name__ == '__main__':
    app.start()
