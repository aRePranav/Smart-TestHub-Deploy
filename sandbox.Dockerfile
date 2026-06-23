# =====================================================================
# Automated Test Execution Platform — sandbox execution image
#
# This is the image inside which UNTRUSTED uploaded test files are
# actually compiled and run. It is launched fresh (--rm) for every
# single execution by backend/executors/base_executor.py with:
#
#     --network none          (no network access at all)
#     --read-only              (root fs read-only; only a small tmpfs
#                               work directory is writable)
#     --cap-drop ALL           (no Linux capabilities)
#     --security-opt no-new-privileges
#     --memory / --cpus / --pids-limit   (hard resource ceilings)
#     --user 1000:1000         (non-root, unprivileged)
#
# Build once:
#     docker build -f sandbox.Dockerfile -t test-platform-sandbox:latest .
# =====================================================================

FROM debian:12-slim

LABEL description="Locked-down execution sandbox for untrusted test files"

# Install only what's needed to run Python (pytest), compile/run C,
# and compile/run Java. No network tools, no extra utilities.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        gcc \
        default-jdk-headless \
        bash && \
    pip3 install --no-cache-dir --break-system-packages pytest && \
    apt-get purge -y --auto-remove && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Create a fixed unprivileged user (uid:gid 1000:1000, matched by
# the --user flag the base_executor passes at container run time).
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin sandboxuser

WORKDIR /work
USER sandboxuser

CMD ["bash"]
