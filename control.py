#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import getopt
import os
import sys
import time
import traceback
from socket import socket, AF_INET, SOCK_STREAM
import json


if sys.version_info < (3, 6):
    print("--- Python版本必须大于3.6！ ---")
    sys.exit(1)

# 给文字加背景
def set_color(color, message):
    """
    :param color: 消息颜色
    :param message 消息内容
    :return: None
    """
    colors = {'red': 31, 'green': 32, 'yellow': 33, 'blue': 34, 'dark_green': 36, 'default': 37}
    if color in colors:
        fore = colors[color]
    else:
        fore = 37
    color = '\033[%d;%dm' % (1, fore)
    return '%s%s\033[0m' % (color, message)


def usage():
    print(
        """ 
使用: python3 {} [options...] 
参数:  
    -f : 读取主机列表文件，逐台执行命令。提示：文件中<主机一行一个>
    -i : 指定要连接主机IP，默认IP <127.0.0.1>
    -p : 指定要连接的主机端口，默认端口 <9876>
    -c : 要执行的命令
    -s : 不回显命令的执行结果
    -h : 帮助信息
    python3 {} -i 9.135.93.3 -c "ifconfig"  
    """.format(sys.argv[0], sys.argv[0])
    )

# 拿到终端大小，适配
def get_tty_size():
    try:
        cr = os.get_terminal_size()
    except Exception:
        cr = (80, 24)
    return int(cr[0]), int(cr[1])

# json结构
def handle_data(data):
    """
    主要方法，转换和处理数据
    :param data: 接收传入json或dict
    :return:  如果传入是json则会尝试解析成dict，如果传入是dict会尝试转换成json
    """
    if data != b'':
        if isinstance(data, bytes):
            _data = json.loads(data)
            if isinstance(_data, dict):
                return True, _data
            else:
                # return False, ValueError("使用handle_data处理数据时，解析出来的数据类型不正确，解析后的类型是：{}".format(_data))
                return False, {"keep_receive": False, "signal": "", "data": ["使用handle_data处理数据时，解析出来的数据类型不正确，解析后的类型是：{}".format(_data)]}
        elif isinstance(data, dict):
            return True, json.dumps(data)
        else:
            # return False, ValueError("使用handle_data处理数据时，传入的数据类型不正确，data类型是：{}" .format(data))
            return False, json.dumps({"keep_receive": False, "signal": "", "data": ["使用handle_data处理数据时，传入的数据类型不正确，data类型是：{}".format(data)]})


def handle_msg(keep_receive, signal, msg_list, *text):
    """
    封装发送的消息数据
    :param keep_receive: Ture/False，给控制端发送，用于控制端判断数据是否接收完，False表示当前为最后一个包，True表示后续还有数据
    :param signal: 给控制端发送的信号，用于控制端来做判断。或者是控制端给受控端发送需要被捕获的异常，用于受控端处理控制端出现的异常。
    :param msg_list: list，传入的特定的消息内容，比如是执行命令的结果缓存，通过readlines读取直接传入
    :param text: tuple，需要组合的消息，将会和msg_list拼接
    :return: bytes dict
    """
    msg_list = msg_list + list(text)
    return {"keep_receive": keep_receive, "signal": signal, "data": msg_list}


def while_receive(socket_obj, keep_receive):
    """
    while循环提取受控端发送的消息
    将此方法单独抽出来，方便后期复用或扩展
    :param socket_obj: socket对象
    :param keep_receive: 初始化退出条件
    :return:
    """
    while keep_receive:
        recv_data = socket_obj.recv(65535)
        if recv_data != b'':
            _status, _data = handle_data(recv_data)
            if _status:
                # 如果SocketControlledEndSayBye在signal的键值中存在，说明被控端主动提出结束
                if "SocketControlledEndSayBye" in _data.get('signal'):
                    print("".join(_data.get("data")).strip())
                    keep_receive = _data.get("keep_receive")
                else:
                    print("".join(_data.get("data")).strip())
        else:
            time.sleep(0.1)


def socket_control(host, port, send_data):
    """
    :param host: 主机，windows本机为127.0.0.1，Linux为本机的ip
    :param host: 开启的端口
    :param send_data: 发送的数据
    :return:    """
    # 建立socket连接，默认持续接受数据
    control_s = socket(AF_INET, SOCK_STREAM)
    keep_receive = True
    try:
        # 尝试建立连接
        try:
            control_s.connect((host, port), )
        except Exception as e:
            print(set_color("red", "被控端<{}:{}>无法连接，请检查被控端是否己运行。".format(host, port)))
            print(set_color("red", "Exception: {}".format(e)))
            sys.exit(1)
        # 处理数据
        _, _data = handle_data(send_data)
        # 发送数据
        control_s.send(_data.encode())
        # 循环等待
        while_receive(control_s, keep_receive)
    except KeyboardInterrupt:
        _, send_signal_data = handle_data(handle_msg(False, "SignalKillByKeyboardInterrupt", []))
        control_s.send(send_signal_data)
        while_receive(control_s, keep_receive)
        print(set_color("yellow", "控制端Ctrl-C, 强制终止..."))
    except Exception as e:
        print(set_color("red", "出现未知的错误：{}".format(e)))
        print(traceback.format_exc())
    finally:
        control_s.close()


if __name__ == "__main__":
    """
    控制端
    """
    # 被控端的IP列表文件
    file = ""
    # 被控端的连接IP
    ip = ""
    # 被控端的连接端口
    port = 9876
    command = ""
    show = True
    columns = 80

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hi:f:c:p:s")
    except getopt.GetoptError:
        usage()
        sys.exit()

    if len(opts) == 0:
        usage()
        sys.exit()

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt == "-f":
            file = arg
        elif opt == "-i":
            ip = arg
        elif opt == "-c":
            command = arg
        elif opt == "-p":
            port = arg
        elif opt == "-s":
            show = False

    if not command:
        print("command not found")
        sys.exit(1)

    columns, lines = get_tty_size()
    """
    •▪ =
    """

    # dict字典。C++的map
    send_data = {
        # 要执行的命令
        "command": command,
        # 是否回显执行过程
        "show": show,
        # 被控端的数据是否发送完成
        "keep_receive": True,
        # 控制信号
        "signal": "",
        "columns": columns,
        "setup": 1,
    }
    
    if file:
        with open(file) as fo:
            for ip in fo.readlines():
                socket_control(ip.strip(), port, send_data)
    else:
        if ip:
            socket_control(ip, port, send_data)
        else:
            print("错误：请指定正确的参数，详细请使用-h查看帮助。")
