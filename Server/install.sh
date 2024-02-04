if [ "$USER" != "root" ];
then
	echo "Run install.sh with root or sudo!"
	exit
fi

systemctl stop atto-comm

cp -f atto-comm.service /etc/systemd/system/

mkdir -p /home/www/comm
cp atto-comm.py /home/www/comm/

mkdir -p /var/log/atto-comm

systemctl daemon-reload
systemctl start atto-comm
