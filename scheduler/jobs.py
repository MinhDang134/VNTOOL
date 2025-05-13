from apscheduler.schedulers.blocking import BlockingScheduler
from crawlers.wipo import crawl_wipo
from crawlers.vietnam import crawl_vietnam
from monitor.watcher import monitor_in_progress_brands

sched = BlockingScheduler()
sched.add_job(lambda: crawl_wipo("2024-05"), 'cron', hour=1)
sched.add_job(lambda: crawl_vietnam("2024-05"), 'cron', hour=2)
sched.add_job(monitor_in_progress_brands, 'cron', hour=0)