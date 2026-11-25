export const apps = [
    {
        name: "flask-api",
        script: "app.py",
        interpreter: "python",
        args: "--runserver",
        instances: 2, // Safe number of workers for API
        exec_mode: "cluster",
        watch: false,
        max_memory_restart: "1G", // Protects against OOM
        env: {
            NODE_ENV: "production",
        }
    },
    {
        name: "celery-worker",
        script: "venv/bin/celery",
        args: "-A celery_app worker --loglevel=info -P gevent -c 100 -Q celery,heavy_ingestion", // Consume legacy and bulk queues
        interpreter: "none",
        watch: false,
        max_memory_restart: "1G", // Kills & Restarts worker if it exceeds 1GB RAM
        env: {
            NODE_ENV: "production",
        }
    },
    {
        name: "gdrive-orchestrator",
        script: "worker_etl.py",
        interpreter: "python",
        instances: 1, // MUST BE 1. Do not scale this, it scans the drive
        watch: false,
        max_memory_restart: "500M",
        env: {
            NODE_ENV: "production",
        }
    }
];
