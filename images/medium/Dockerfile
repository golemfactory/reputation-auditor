FROM ubuntu:latest

RUN apt update && apt install -y sysbench jq


# Ensure the script is available in the container
COPY benchmark-cpu.sh /benchmark-cpu.sh
COPY benchmark-memory.sh /benchmark-memory.sh
COPY benchmark-disk.sh /benchmark-disk.sh
RUN chmod +x /benchmark-cpu.sh
RUN chmod +x /benchmark-memory.sh
RUN chmod +x /benchmark-disk.sh

VOLUME /golem/work
# Other Dockerfile commands...
CMD ["tail", "-f", "/dev/null"]