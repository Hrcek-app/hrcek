"""gunicorn settings for the container.

One process on purpose: the token-exchange throttle counts in the
process's own memory, so several workers would each keep a separate
tally. Threads give the concurrency a family needs.
"""

bind = "0.0.0.0:8000"
workers = 1
worker_class = "gthread"
threads = 4
accesslog = "-"
errorlog = "-"
