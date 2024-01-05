#! /bin/sh
_cputype="$(uname -m)"

case "$_cputype" in
x86_64 | x86-64 | x64 | amd64)
    _cputype=x86_64
    mv /yagna/amd64/yagna /root/.local/bin/yagna
    mv /yagna/amd64/gftp /root/.local/bin/gftp
    ;;
arm64 | aarch64)
    _cputype=aarch64
    mv /yagna/arm64/yagna /root/.local/bin/yagna
    mv /yagna/arm64/gftp /root/.local/bin/gftp
    ;;
*)
    err "invalid cputype: $_cputype"
    ;;
esac
# Start yagna service in the background and log it
mkdir -p /golem/work
touch /golem/work/yagna.log
echo "Starting Yagna"
YAGNA_AUTOCONF_APPKEY=reputation /root/.local/bin/yagna service run >/dev/null 2>&1 &
sleep 5
