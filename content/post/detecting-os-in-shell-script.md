+++
date = "2017-04-02T00:00:00+05:30"
title = "Detecting OS in shell script"
draft = false

+++

Each linux distribution uses different package manager. To be able to execute commands based on the type of OS in a shell script, we need a way to detect the OS first.

## Using `which` command

My first take on resolving this was to use the `which` command

```bash
#!/bin/bash
if [[ `which yum` ]]; then
   IS_RHEL=1
elif [[ `which apt` ]]; then
   IS_UBUNTU=1
elif [[ `which apk` ]]; then
   IS_ALPINE=1
else
   IS_UNKNOWN=1
fi
```

Now this works well on most OS, but the issue is that when you use the same on docker images. Official Docker images have minimal software packages. And `which` command is missing in case of the `centos:7.2.1511` image

```bash
tarunlalwani@instance-1:~$ docker run -it centos:7.2.1511 bash
[root@cf78fcecc38e /]# which yum
bash: which: command not found
[root@cf78fcecc38e /]#
```

Now since we need to install the which command, we can either bruteforce the installation to make sure which command exists

```bash
#!/bin/bash
yum install -y which >/dev/null
```

And this command would run irrespective of the OS. Not a very clean approach but still works. Now let's turn our attention to the `alpine:3.5` docker image. Alpine images don't have the `bash` shell, instead it uses `sh`. This means in the she bang we should use `#!/bin/sh` instead of `#!/bin/bash`. But this breaks our script on `ubuntu:16.04` as ubuntu uses dash as its low end shell. `/bin/sh` is just symlink to `dash` in ubuntu. 

```bash
$ if [[ `which yum` ]]; then
   IS_RHEL=1
fi
sh: 1: [[: not found
``` 

The `[[:` not found issue is because `[[` is a bash operator and not supported in `dash`. But easy fix to the same is replacing `[[` and `]]` with `[` and `]` respectively. The updated code is shown below

``` bash
#!/bin/bash
if [ `which yum` ]; then
   IS_RHEL=1
elif [ `which apt` ]; then
   IS_UBUNTU=1
elif [ `which apk` ]; then
   IS_ALPINE=1
else
   IS_UNKNOWN=1
fi
```

## Using more reliable `/etc/os-release`

After some research I found a better a more reliable way of finding the OS details. Which is by using `/etc/os-release` file. Sample content for the `centos:7.2.1511` docker image is below

```bash
NAME="CentOS Linux"
VERSION="7 (Core)"
ID="centos"
ID_LIKE="rhel fedora"
VERSION_ID="7"
PRETTY_NAME="CentOS Linux 7 (Core)"
ANSI_COLOR="0;31"
CPE_NAME="cpe:/o:centos:centos:7"
HOME_URL="https://www.centos.org/"
BUG_REPORT_URL="https://bugs.centos.org/"

CENTOS_MANTISBT_PROJECT="CentOS-7"
CENTOS_MANTISBT_PROJECT_VERSION="7"
REDHAT_SUPPORT_PRODUCT="centos"
REDHAT_SUPPORT_PRODUCT_VERSION="7"
```

And for `ubuntu:16.04` docker image

```bash
NAME="Ubuntu"
VERSION="16.04.2 LTS (Xenial Xerus)"
ID=ubuntu
ID_LIKE=debian
PRETTY_NAME="Ubuntu 16.04.2 LTS"
VERSION_ID="16.04"
HOME_URL="http://www.ubuntu.com/"
SUPPORT_URL="http://help.ubuntu.com/"
BUG_REPORT_URL="http://bugs.launchpad.net/ubuntu/"
VERSION_CODENAME=xenial
UBUNTU_CODENAME=xenial
```

So we can use `$ID` to identify the OS. Simply use the `source` command to load the file in your script and then use `$ID` for checking the OS

```bash
#!/bin/sh
source /etc/os-release

echo "Your OS is $ID"
```

In case of Ubuntu's `dash` you will get an error `sh: 1: source: not found`. This is becase `dash` doesn't implement the bash's `source` command. The simple fix is to replace `source` with `.` command

```bash
#!/bin/sh
. /etc/os-release

echo "Your OS is $ID"
```

#### References

* [os-release — Operating system identification](https://www.freedesktop.org/software/systemd/man/os-release.html)