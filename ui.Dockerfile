FROM mcr.microsoft.com/playwright/python:v1.57.0-noble
LABEL description="Run Kuadrant UI tests with Playwright \
Default ENTRYPOINT: 'make' and CMD: 'ui' \
Bind dynaconf settings to /run/secrets.yaml \
Bind kubeconfig to /run/kubeconfig \
Bind a dir to /test-run-results to get reports"

# Install poetry and make
RUN pip install poetry && \
    apt-get update && apt-get install -y make && \
    rm -rf /var/lib/apt/lists/*

# Install kubectl
RUN ARCH=$(dpkg --print-architecture) && \
    curl -LO "https://dl.k8s.io/release/v1.30.2/bin/linux/${ARCH}/kubectl" && \
    mv kubectl /usr/local/bin && \
    chmod +x /usr/local/bin/kubectl

WORKDIR /opt/workdir/kuadrant-testsuite

COPY . .

# Create required dirs and permissions
RUN mkdir -m 0770 /test-run-results && \
    mkdir -m 0750 /opt/workdir/virtualenvs && \
    chown pwuser /test-run-results && \
    chown pwuser -R /opt/workdir/* && \
    touch /run/kubeconfig && chmod 660 /run/kubeconfig && chown pwuser /run/kubeconfig && \
    touch /run/secrets.yaml && chmod 660 /run/secrets.yaml && chown pwuser /run/secrets.yaml

# Switch to non-root Playwright user
USER pwuser

ENV KUBECONFIG=/run/kubeconfig \
    SECRETS_FOR_DYNACONF=/run/secrets.yaml \
    POETRY_VIRTUALENVS_PATH=/opt/workdir/virtualenvs/ \
    junit=yes \
    resultsdir=/test-run-results

# Install test deps
RUN make poetry-no-dev && \
    touch .make-playwright-install && \
    rm -Rf $HOME/.cache/*

ENTRYPOINT ["make"]
CMD ["ui", "flags=--browser firefox"]
