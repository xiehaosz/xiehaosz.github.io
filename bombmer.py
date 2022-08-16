import socket
from queue import Queue, Empty
from threading import Thread
import json

from .game import GameMap, Player


class Client(Thread):
    def __init__(self, player_id: int, server_ip: str, server_port: int):
        self.host = server_ip
        self.port = server_port
        self.player_id = player_id
        self.player_name = ("WxSshTdd%s" % self.player_id)[:20]
        self.army = None        # type: Player
        self.map = None         # type: GameMap
        super(Client, self).__init__(name=self.host)
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.queue = Queue()
        self.running = True
        try:
            self.client.connect((self.host, self.port))
            print("Connect to server[%s] success" % self.host)
        except Exception as e:
            print("Connect to server[%s] fail, reason: %s" % (self.host, e))

    def run(self):
        Thread(target=self.parser_msg).start()
        self.register()
        while self.running:
            msg = self.client.recv(8192)
            if len(msg) == 0:
                self.stop()
            else:
                msg = msg.decode("utf-8")
                self.queue.put(msg)

    def parser_msg(self):
        merged_msg = ""     # 用来合并消息，解决粘包、分包问题
        while self.running:
            try:
                one_msg = self.queue.get(timeout=0.5)
                # 解决粘包分包问题 参考https://blog.csdn.net/weixin_43803688/article/details/123003363
                merged_msg = "%s%s" % (merged_msg, one_msg)         # 合并分片包
                if len(merged_msg) < 5:
                    continue
                else:
                    msg_len = int(merged_msg[:5])
                    msg_body = merged_msg[5:]
                    if len(msg_body) >= msg_len:        # 有粘包
                        actual_msg = json.loads(msg_body[:msg_len])
                        print("Recv msg: %s" % actual_msg)
                        merged_msg = msg_body[msg_len:]
                        msg_name = actual_msg.get("msg_name", None)
                        msg_data = actual_msg.get("msg_data", None)
                        if msg_name == "gameOver":
                            print("Game Over!")
                            self.stop()
                        elif msg_name == "gameStart":
                            _players = []
                            for _player in msg_data["players"]:
                                _p = Player(_player["playerId"])
                                if _player["playerId"] == self.player_id:
                                    _p.set_prefix("1")
                                else:
                                    _p.set_prefix("2")
                                _p.set_object_id_range(_player["objectIdRange"])
                                _players.append(_p)
                            self.map = GameMap(*_players)
                            self.map.init_map(msg_data["map"])
                            self.ready()
                        elif msg_name == "inquire":
                            # todo 执行行动
                            self.map.update(msg_data["objects"])
                            print(self.map.obj_id_to_pos)
                            print(self.map.pos_to_obj)
                            turn = msg_data["round"]
                            objs = self.map.get_player_objs(self.player_id)
                            self.move_action(turn, objs[0].obj_id, objs[0].move(0, 1))
                            self.map.print_state(self.player_id)

            except Exception as e:
                if not isinstance(e, Empty):
                    print("Parser msg fail, reason: %s" % e)
                    raise e

    def send(self, msg_body: dict):
        """
        :param msg_body: 待发送消息
        :return:
        """
        msg = json.dumps(msg_body)
        msg_len = str(len(msg)).rjust(5, "0")
        msg = "%s%s" % (msg_len, msg)
        self.client.send(msg.encode("utf-8"))

    def register(self):
        msg_body = {
            "msg_name": "registration",
            "msg_data": {
                "playerId": self.player_id,
                "playerName": self.player_name,
                "version": "v1.0"
            }
        }
        self.send(msg_body)

    def ready(self):
        msg_body = {
            "msg_name": "gameReady",
            "msg_data": {
                "playerId": self.player_id
            }
        }
        self.send(msg_body)

    def move_action(self, turn, obj_id, obj_pos):
        msg_body = {
            "msg_name": "action",
            "msg_data": {
                "round": turn,
                "actions": [
                    {
                        "id": obj_id,           # 移动者ID
                        "action": "move",       # 移动命令
                        "position": obj_pos     # 目的位置坐标
                    }
                ]
            }
        }
        self.send(msg_body)

    def bomb_action(self, turn, obj_id):
        msg_body = {
            "msg_name": "action",
            "msg_data": {
                "round": turn,
                "actions": [
                    {
                        "id": obj_id,  # 要使用的炸弹ID
                        "action": "bomb"  # 爆炸命令
                    }
                ]
            }
        }
        self.send(msg_body)

    def no_action(self, turn):
        msg_body = {
            "msg_name": "action",
            "msg_data": {
                "round": turn,
                "actions": [
                    {
                        "action": "nop"  # 空操作命令，表示该回合不做动作
                    }
                ]
            }
        }
        self.send(msg_body)

    def stop(self):
        self.running = False


if __name__ == "__main__":
    c = Client(8000, "127.0.0.1", 6000)
    c.start()

