FROM quay.io/fedora/fedora:35
LABEL description="Run Kuadrant integration tests \
Default ENTRYPOINT: 'make' and CMD: 'test' \
Bind dynaconf settings to /opt/secrets.yaml \
Bind kubeconfig to /opt/kubeconfig \
Bind a dir to /test-run-results to get reports "

RUN useradd --no-log-init -u 1001 -r -U testsuite
RUN dnf install -y python3 python3-pip make git

RUN curl https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable/openshift-client-linux.tar.gz >/tmp/oc.tgz && \
	tar xzf /tmp/oc.tgz -C /usr/local/bin && \
	rm /tmp/oc.tgz

RUN pip3 --no-cache-dir install pipenv

WORKDIR /opt/workdir/kuadrant-testsuite

COPY . .

RUN mkdir -m 0700 /test-run-results && chown testsuite /test-run-results && \
    mkdir -m 0700 -p /opt/workdir/virtualenvs && \
    chown testsuite -R /opt/workdir/*  && \
	chown testsuite /opt

USER 1001


ENV KUBECONFIG=/opt/kubeconfig \
    SECRETS_FOR_DYNACONF=/opt/secrets.yaml \
    PIPENV_IGNORE_VIRTUALENVS=1 \
    WORKON_HOME=/opt/workdir/virtualenvs \
    junit=yes \
    resultsdir=/test-run-results

RUN make mostlyclean pipenv && \
	rm -Rf $HOME/.cache/*

ENTRYPOINT [ "make" ]
CMD [ "test" ]
