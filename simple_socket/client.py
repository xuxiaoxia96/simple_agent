# -*- coding:utf-8 -*-
# 导入socket库
import socket
# 定义一个ip协议版本AF_INET，为IPv4；同时也定义一个传输协议（TCP）SOCK_STREAM
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# 定义IP地址与端口号
ip_port = ('', 8000)
# 进行连接服务器
client.connect(ip_port)
while True:
    message = input('You can say:')
    client.send(message.encode('utf-8'))  # 将发送的数据进行编码
    a = client.recv(1024)  # 接受服务端的信息，最大数据为1k
    print(a.decode('utf-8'))
    if a.decode('utf-8') == 'bye':
        break
