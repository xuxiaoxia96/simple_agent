#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import getopt
import os
import random
from socket import gethostname, gethostbyname
import sys
import time
import json


if sys.version_info < (3, 6):
    print("Python版本必须大于3.6!")
    sys.exit(1)

from socketserver import ThreadingMixIn, TCPServer, BaseRequestHandler
from subprocess import Popen


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
    -i : 指定运行服务的IP，默认IP <0.0.0.0>
    -p : 指定运行服务的端口，默认端口 <9876>
    -h : 帮助信息
    python3 {} -i 172.16.123.10 -p 1234
    """.format(sys.argv[0], sys.argv[0])
    )


def get_time():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))

# 继承两个类，并且实现他们的方法
class ServerEndpoint(ThreadingMixIn, TCPServer):
    # 如果被控端触发了Ctrl-C 将杀死所有派生线程
    daemon_threads = True
    # 快速重新绑定
    allow_reuse_address = True
    # 先执行这个函数进行初始化
    def __init__(self, server_address, RequestHandlerClass):
        TCPServer.__init__(self, server_address, RequestHandlerClass)


class TcpServerHandler(BaseRequestHandler):
    def __init__(self, request, client_address, server):
        super().__init__(request, client_address, server)
        self.command = ""
        self.show = True
        self.keep_receive = True
        self.columns = 80
        self.banner = ""
        self.tmp_file = ""

    @staticmethod
    def handle_msg(keep_receive, signal, msg_list, *text):
        """
        封装发送的消息数据
        :param keep_receive: Ture/False，给控制端发送，用于控制端判断数据是否接收完，False表示当前为最后一个包，True表示后续还有数据
        :param signal: 给控制端发送的信号，用于控制端来做判断。或者是控制端给被控端发送需要被捕获的异常，用于被控端处理控制端出现的异常。
        :param msg_list: list，传入的特定的消息内容，比如是执行命令的结果缓存，通过readlines()读取直接传入
        :param text: tuple，需要组合的消息，将会和msg_list拼接
        :return: dict
        """
        msg_list = msg_list + list(text)
        return {"keep_receive": keep_receive, "signal": signal, "data": msg_list}

    @staticmethod
    def handle_data(data):
        print("222222")

        """
        转换和处理数据
        :param data: 接收传入json或dict
        :return:  如果传入是json则会尝试解析成dict，如果传入是dict会尝试转换成json
        """
        if isinstance(data, bytes):
            _data = json.loads(data)
            if isinstance(_data, dict):
                return True, _data
            else:
                return False, {"keep_receive": False, "signal": "", "data": ["使用handle_data处理数据时，解析出来的数据类型不正确，解析后的类型是：{}".format(_data)]}
        elif isinstance(data, dict):
            return True, json.dumps(data)
        else:
            return False, json.dumps({"keep_receive": False, "signal": "", "data": ["使用handle_data处理数据时，传入的数据类型不正确，data类型是：{}".format(data)]})

    # 执行linux命令
    def exec_command(self):
        log_file = "{}-{}".format(self.tmp_file, random.randint(100000, 999999))
        w_pipe = open(log_file, "wb")
        result = Popen(self.command, stdout=w_pipe, stderr=w_pipe, shell=True, bufsize=0, universal_newlines=True)
        print(result)
        r_pipe = open(log_file, "r")

        try:
            while True:
                read_data = r_pipe.readlines(0-10)
                try:
                    # 尝试再次获取一次控制端的recv，flags=0x40或64 也就是(socket.MSG_DONTWAIT)
                    # 正常情况下socket recv如果没有获取到新的消息，会一直等待接收，会阻塞后续的操作
                    # check_status, check_data = self.handle_data(self.request.recv(65535, 0x40))
                    check_status, check_data = self.handle_data(self.request.recv(65535, 64))
                    if not check_status:
                        check_data = {"keep_receive": True, "signal": "", "data": ["get receive check_data is null, check_data: {}".format(check_data)]}
                except Exception as e:
                    check_data = {"keep_receive": True, "signal": "", "data": ["get receive check_data is null, reason: {}".format(e)]}

                # 如果启用显示实时回显执行过程
                if self.show:
                    # 尝试获取一下socket是否有传输带有SignalKillByKeyboardInterrupt，如果有表示控制端已经接收到Ctrl-C
                    # 则被控端当前正在运行的命令需要被强制结束。
                    if "SignalKillByKeyboardInterrupt" in check_data.get("signal"):
                        result.send_signal(2)
                        # 再发送一次文件内容，比如程序在接收到2信号会处理信号，会有新的结果产生
                        print("控制端发送<Ctrl-C>，命令<{}>，被强制终止...".format(self.command))
                        time.sleep(0.1)
                        _, send_msg = self.handle_data(self.handle_msg(
                            False,
                            "SocketControlledEndSayBye",
                            r_pipe.readlines(),
                            set_color("dark_green", "{}    --    Aborted    --    {}".format(gethostbyname(gethostname()), get_time())),
                        ))
                        self.request.send(send_msg)
                        self.request.close()
                        return

                    # 如果result.pool()不为None 说明己执行完成
                    if result.poll() is not None:
                        if len(read_data) > 0:
                            _, send_msg = self.handle_data(self.handle_msg(True, "", read_data))
                            self.request.send(send_msg.encode())
                            continue
                        break
                    # 否则还在执行中，持续读取文件内容发给控制端
                    else:
                        if len(read_data) > 0:
                            _, send_msg = self.handle_data(self.handle_msg(True, "", read_data))
                            self.request.send(send_msg.encode())
                        continue
                # 否则就是不回显执行过程
                else:
                    if result.poll() is not None:
                        break
            if result.returncode == 0:
                _, send_msg = self.handle_data(self.handle_msg(
                    False,
                    "SocketControlledEndSayBye",
                    [],
                    set_color("green", "{}    --    SUCCESS    --    {}".format(gethostbyname(gethostname()), get_time())),
                ))
            else:
                _, send_msg = self.handle_data(self.handle_msg(
                    False,
                    "SocketControlledEndSayBye",
                    [],
                    set_color("red", "{}    --    FAILED    --    {}".format(gethostbyname(gethostname()), get_time())),
                ))
            time.sleep(0.1)
            self.request.send(send_msg.encode())
        except BrokenPipeError:
            pass
        except KeyboardInterrupt:
            result.send_signal(2)
            time.sleep(0.1)
            _, send_msg = self.handle_data(self.handle_msg(
                False,
                "SocketControlledEndSayBye",
                r_pipe.readlines(),
                set_color("yellow", "{}    --    KeyboardInterrupt    --    {}".format(gethostbyname(gethostname()), get_time())),
            ))
            self.request.send(send_msg)
        except Exception as e:
            result.send_signal(2)
            time.sleep(0.1)
            _, send_msg = self.handle_data(self.handle_msg(
                False,
                "SocketControlledEndSayBye",
                r_pipe.readlines(),
                "被控端执行过程出现异常：{}".format(e),
                set_color("red", "{}    --    Exception    --    {}".format(gethostbyname(gethostname()), get_time())),
            ))
            self.request.send(send_msg)
        finally:
            w_pipe.close()
            r_pipe.close()
            os.remove(log_file)

    def handle_setup_msg(self):
        _, setup_msg = self.handle_data(self.handle_msg(
            True,
            "",
            [],
            "Setup\t--\t连接建立：\t<{}:{}> ←-→ <{}:{}>".format(
                self.client_address[0], self.client_address[1],
                gethostbyname(gethostname()),
                self.server.server_address[1]
            )
        ))
        self.request.send(setup_msg)

    def handle_run_msg(self):
        _, run_msg = self.handle_data(self.handle_msg(
            True,
            "",
            [],
            set_color("blue", "{}    --    Result    >>".format(gethostbyname(gethostname()))),
        ))
        print(type(run_msg.encode()))

        self.request.send(run_msg.encode())

    def setup(self):
        print("Run\t\t--\t开始执行：\t", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())))
        print("Setup\t--\t连接建立：\t<{}:{}>".format(self.client_address[0], self.client_address[1]))

    def handle(self):
        send_msg = {"keep_receive": False, "signal": "", "data": []}
        receive_status, receive_data = self.handle_data(self.request.recv(65535))
        # 先判断下接收到的第一个数据是否合规
        if receive_status and not receive_data.get("signal") and receive_data.get("setup") == 1:
            self.command = receive_data.get("command")
            self.show = receive_data.get("show")
            self.keep_receive = receive_data.get("keep_receive")
            self.columns = receive_data.get("columns")
            if 'win' in sys.platform:
                self.tmp_file = "{}\\socket-server-filestream" .format(os.getenv('TMP'))
            else:
                self.tmp_file = "/tmp/socket-server-filestream"
            self.banner = "=" * self.columns

            # self.handle_setup_msg()
            self.handle_run_msg()
            self.exec_command()
        else:
            _, send_msg = self.handle_data(self.handle_msg(
                False,
                "SocketControlledEndSayBye",
                [],
                set_color("red", "{}    --    Error    --    >>".format(gethostbyname(gethostname()))),
                "{}".format(receive_data),
            ))
            self.request.send(send_msg)

    def finish(self):
        self.request.close()
        print("Finish\t--\t执行命令：\t<{}> 完成...".format(self.command))


if __name__ == "__main__":
    """
    被控端
    """
    host = "0.0.0.0"
    port = 9876

    # 拿到命令行的参数
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hi:p:")
    except getopt.GetoptError:
        usage()
        sys.exit()

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt == "-i":
            host = arg
        elif opt == "-p":
            port = arg

    try:
        # 衍生一个多线程被控端
        server = ServerEndpoint((host, port), TcpServerHandler)
        print(set_color("blue", "使用<{}:{}>启动被控端...".format(host, port)))
        # 启动服务，服务将一直保持运行状态
        server.serve_forever()
    except KeyboardInterrupt:
        print("Ctrl-C，强制终止...")
        sys.exit(1)
