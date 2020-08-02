import pytest

from machaon.starter import TkStarter
from machaon.command import describe_command_package, describe_command

def hello_world(spi, count, string=None):
    if string is None: string = "Hello, world"
    print("count = {}".format(count))
    print("string = {}".format(string))
    for i in range(count):
        spi.message("{:3} {}!".format(i, string))


class WorkerShift():
    @classmethod
    def describe_object(cls, traits):
        traits.describe(
            typename="worker-shift",
            description="授業員のシフト"
        )["member name"](
            help="名前"
        )["member day"](
            help="シフトに入れる日数",
            return_type=int
        )
    
    def __init__(self, name, day):
        self._name = name
        self._day = day
    
    def name(self):
        return self._name
    
    def day(self):
        return self._day

def worker_shift_table(spi):
    workers = [
        WorkerShift("渡辺", 5),
        WorkerShift("井上", 3),
        WorkerShift("林", 2),
    ]
    spi.push_dataview(workers, "name day")

def empty_table(spi):
    spi.push_dataview([], itemtype=WorkerShift)


@pytest.mark.skip(True)
def test_start():
    sta = TkStarter(title="machaon sample app", geometry=(900,500), directory="")
    sta.commandset(
        describe_command_package(
            "testpackage",
            description="test"
        )["hello"](
            describe_command(
                hello_world,
                description="hello-world",
            )["target count: int"](
                help="回数"
            )["target string: str"](
                help="文字列"
            )
        )["shift"](
            describe_command(
                worker_shift_table,
                description="全員のシフト表を表示",
            )
        )["emptiness"](
            describe_command(
                empty_table,
                description="空の表を表示",
            )
        )
    )
    sta.go()


if __name__ == "__main__":
    test_start()


