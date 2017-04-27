+++
date = "2017-03-30T00:00:00+05:30"
draft = false
title = "MySQL master slave using docker"

+++

Docker makes it easy to run multiple independent mysql instances on the same machines for different projects. But some projects use a Master and slave setup of MySQL, where usually writes are directed to Master and the reads are directed to Slave.

I based my approach on [tegansnyder/docker-mysql-master-slave](https://github.com/tegansnyder/docker-mysql-master-slave/blob/master/setup.sh). But what I didn't like about the existing setup is that it assumed mysql client setup on the host. I wanted to do it using the mysql docker images itself. Also other things I wanted is that it is compatible with `docker-compose` as well.

So we first create a basic `docker-compose.yml` with two mysql instances

```yml
version: '2'
services:
  mysqlmaster:
    image: mysql:5.7
    environment:
      - "MYSQL_ROOT_PASSWORD=root"
    volumes:
      - ./data/mysql-master:/var/lib/mysql/
      - ./config/mysql-master:/etc/mysql/conf.d/
  mysqlslave:
    image: mysql:5.7
    environment:
      - "MYSQL_ROOT_PASSWORD=root"
    volumes:
      - ./data/mysql-slave:/var/lib/mysql/
      - ./config/mysql-slave:/etc/mysql/conf.d/
```

Now next we need master and slave config to give `server-id` to the mysql instances.

##### config/mysql-master/master.cnf

```ini
[mysqld]
server-id=1
log-bin=mysql-bin
log-slave-updates=1
datadir=/var/lib/mysql/
innodb_flush_log_at_trx_commit = 2
innodb_flush_method = O_DIRECT
skip-host-cache
skip-name-resolve
```

##### config/mysql-slave/slave.cnf

```ini
[mysqld]
server-id=2
log-bin=mysql-bin
log-slave-updates=1
auto_increment_increment=2
auto_increment_offset=2
datadir=/var/lib/mysql
read-only=1
slave-skip-errors = 1062
skip-host-cache
skip-name-resolve
```

### Configuration script

Next we create a configuration shell script which we would run in an seperate image

##### mysql_connector.sh

```bash
#!/bin/bash
BASE_PATH=$(dirname $0)

echo "Waiting for mysql to get up"
# Give 60 seconds for master and slave to come up
sleep 60

echo "Create MySQL Servers (master / slave repl)"
echo "-----------------"


echo "* Create replication user"

mysql --host mysqlslave -uroot -p$MYSQL_SLAVE_PASSWORD -AN -e 'STOP SLAVE;';
mysql --host mysqlslave -uroot -p$MYSQL_MASTER_PASSWORD -AN -e 'RESET SLAVE ALL;';

mysql --host mysqlmaster -uroot -p$MYSQL_MASTER_PASSWORD -AN -e "CREATE USER '$MYSQL_REPLICATION_USER'@'%';"
mysql --host mysqlmaster -uroot -p$MYSQL_MASTER_PASSWORD -AN -e "GRANT REPLICATION SLAVE ON *.* TO '$MYSQL_REPLICATION_USER'@'%' IDENTIFIED BY '$MYSQL_REPLICATION_PASSWORD';"
mysql --host mysqlmaster -uroot -p$MYSQL_MASTER_PASSWORD -AN -e 'flush privileges;'


echo "* Set MySQL01 as master on MySQL02"

MYSQL01_Position=$(eval "mysql --host mysqlmaster -uroot -p$MYSQL_MASTER_PASSWORD -e 'show master status \G' | grep Position | sed -n -e 's/^.*: //p'")
MYSQL01_File=$(eval "mysql --host mysqlmaster -uroot -p$MYSQL_MASTER_PASSWORD -e 'show master status \G'     | grep File     | sed -n -e 's/^.*: //p'")
MASTER_IP=$(eval "getent hosts mysqlmaster|awk '{print \$1}'")
echo $MASTER_IP
mysql --host mysqlslave -uroot -p$MYSQL_SLAVE_PASSWORD -AN -e "CHANGE MASTER TO master_host='mysqlmaster', master_port=3306, \
        master_user='$MYSQL_REPLICATION_USER', master_password='$MYSQL_REPLICATION_PASSWORD', master_log_file='$MYSQL01_File', \
        master_log_pos=$MYSQL01_Position;"

echo "* Set MySQL02 as master on MySQL01"

MYSQL02_Position=$(eval "mysql --host mysqlslave -uroot -p$MYSQL_SLAVE_PASSWORD -e 'show master status \G' | grep Position | sed -n -e 's/^.*: //p'")
MYSQL02_File=$(eval "mysql --host mysqlslave -uroot -p$MYSQL_SLAVE_PASSWORD -e 'show master status \G'     | grep File     | sed -n -e 's/^.*: //p'")

SLAVE_IP=$(eval "getent hosts mysqlslave|awk '{print \$1}'")
echo $SLAVE_IP
mysql --host mysqlmaster -uroot -p$MYSQL_MASTER_PASSWORD -AN -e "CHANGE MASTER TO master_host='mysqlslave', master_port=3306, \
        master_user='$MYSQL_REPLICATION_USER', master_password='$MYSQL_REPLICATION_PASSWORD', master_log_file='$MYSQL02_File', \
        master_log_pos=$MYSQL02_Position;"

echo "* Start Slave on both Servers"
mysql --host mysqlslave -uroot -p$MYSQL_SLAVE_PASSWORD -AN -e "start slave;"

echo "Increase the max_connections to 2000"
mysql --host mysqlmaster -uroot -p$MYSQL_MASTER_PASSWORD -AN -e 'set GLOBAL max_connections=2000';
mysql --host mysqlslave -uroot -p$MYSQL_SLAVE_PASSWORD -AN -e 'set GLOBAL max_connections=2000';

mysql --host mysqlslave -uroot -p$MYSQL_MASTER_PASSWORD -e "show slave status \G"

echo "MySQL servers created!"
echo "--------------------"
echo
echo Variables available fo you :-
echo
echo MYSQL01_IP       : mysqlmaster
echo MYSQL02_IP       : mysqlslave
```

Next we update on our `docker-compose.yml` to run this script

```yaml
version: '2'
services:
  mysqlmaster:
    image: mysql:5.7.15
    environment:
      - "MYSQL_ROOT_PASSWORD=root"
    volumes:
      - ./data/mysql-master:/var/lib/mysql/
      - ./config/mysql-master:/etc/mysql/conf.d/
  mysqlslave:
    image: mysql:5.7
    environment:
      - "MYSQL_ROOT_PASSWORD=root"
    volumes:
      - ./data/mysql-slave:/var/lib/mysql/
      - ./config/mysql-slave:/etc/mysql/conf.d/
  mysqlconfigure:
    image: mysql:5.7.15
    environment:
      - "MYSQL_SLAVE_PASSWORD=root"
      - "MYSQL_MASTER_PASSWORD=root"
      - "MYSQL_ROOT_PASSWORD=root"
      - "MYSQL_REPLICATION_USER=repl"
      - "MYSQL_REPLICATION_PASSWORD=repl"
    volumes:
      - ./mysql_connector.sh:/tmp/mysql_connector.sh
    command: /bin/bash -x /tmp/mysql_connector.sh
```

### Testing the setup

```bash

$ docker-compose up -d
$ docker-compose logs -f mysqlconfigure
$ docker-compose exec mysqlmaster mysql -uroot -proot -e "CREATE DATABASE test_replication;"
$ docker-compose exec mysqlslave mysql -uroot -proot -e "SHOW DATABASES;"
```

The last command produces below output showing that the replication works fine

```
+--------------------+
| Database           |
+--------------------+
| information_schema |
| mysql              |
| performance_schema |
| sys                |
| test_replication   |
+--------------------+
```

You can find the whole setup on my [tarunlalwani/docker-compose-mysql-master-slave](https://github.com/tarunlalwani/docker-compose-mysql-master-slave)