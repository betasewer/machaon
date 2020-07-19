import pytest

from machaon.starter import TkStarter
from machaon.command import describe_command_package, describe_command

def hello_world(spi, count, string=None):
    if string is None: string = "Hello, world"
    print("count = {}".format(count))
    print("string = {}".format(string))
    for i in range(count):
        spi.message("{:3} {}!".format(i, string))

def yielder(fn, typename):
    def y_(spi, parameter):
        value = fn(parameter)
        if value is not None:
            spi.push_object(typename, value)
    return y_

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
        )["int"](
            describe_command(
                yielder(int, "int"),
                description="make int object",
            )["target parameter: parameter"](
                help="整数の表現"
            )["yield: int"](
                help="int"
            )
        )["str"](
            describe_command(
                yielder(str, "str"),
                description="make int object",
            )["target parameter: parameter"](
                help="整数の表現"
            )["yield: str"](
                help="str"
            )
        )
    )
    sta.go()


if __name__ == "__main__":
    test_start()


