FROM quay.io/centos/centos:stream9
LABEL description="Run Kuadrant integration tests \
Default ENTRYPOINT: 'make' and CMD: 'test' \
Bind dynaconf settings to /opt/secrets.yaml \
Bind kubeconfig to /opt/kubeconfig \
Bind a dir to /test-run-results to get reports "

RUN useradd --no-log-init -u 1001 -g root -m testsuite
RUN dnf install -y python3.11 python3.11-pip make git && dnf clean all

RUN curl https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable/openshift-client-linux.tar.gz >/tmp/oc.tgz && \
	tar xzf /tmp/oc.tgz -C /usr/local/bin && \
	rm /tmp/oc.tgz

RUN curl -L https://github.com/cloudflare/cfssl/releases/download/v1.6.3/cfssl_1.6.3_linux_amd64 >/usr/bin/cfssl && \
    chmod +x /usr/bin/cfssl

RUN python3.11 -m pip --no-cache-dir install poetry

WORKDIR /opt/workdir/kuadrant-testsuite

COPY . .

RUN mkdir -m 0770 /test-run-results && mkdir -m 0750 /opt/workdir/virtualenvs && chown testsuite /test-run-results && \
    chown testsuite -R /opt/workdir/*

RUN touch /run/kubeconfig && chmod 660 /run/kubeconfig && chown testsuite /run/kubeconfig

USER testsuite


ENV KUBECONFIG=/run/kubeconfig \
    SECRETS_FOR_DYNACONF=/run/secrets.yaml \
    POETRY_VIRTUALENVS_PATH=/opt/workdir/virtualenvs/ \
    junit=yes \
    resultsdir=/test-run-results

RUN make poetry-no-dev && \
	rm -Rf $HOME/.cache/*

ENTRYPOINT [ "make" ]
CMD [ "test" ]
