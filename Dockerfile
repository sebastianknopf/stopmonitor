# select base image
FROM python:3.10-slim

# workdir inside the container is /app
WORKDIR /app

# install git in order to use setuptools_scm
# required for automatic detection of version
RUN apt-get update && apt-get install -y git

# copy everything into container
COPY . .

# run installation inside the container
RUN pip install --no-cache-dir .
RUN rm -rf .git
RUN rm -rf .github

# set default environment variables
ENV HOST=0.0.0.0
ENV PORT=8080

# ready - run the stop monitor
ENTRYPOINT ["sh", "-c", "python stopmonitor run /app/config/config.yaml -h $HOST -p $PORT"]