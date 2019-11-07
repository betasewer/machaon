#!/usr/bin/env python3
# coding: utf-8
import unicodedata
from machaon.command import describe_command, describe_command_package

#
def char_detail_line(code, char=None):
    if char is None and code < 0x110000:
        char = chr(code)
    if char is not None:
        name = unicodedata.name(char, None)
        cat = unicodedata.category(char)

    if char is None:
        disp = "[not a character]"
    elif cat.startswith("C") or cat.startswith("Z"):
        if cat == "Cn":
            name = "[not a character]"
        else:
            name = "[{} control character]".format(cat)
        disp = name
    else:
        disp = char + "  " + name
    return " {:04X} {}".format(code, disp)

    
#   
#
#
def encode_unicodes(app, characters):
    app.message("input:")
    for char in characters:
        line = char_detail_line(ord(char), char)
        app.message(line)

#
#
#
def decode_unicodes(app, characters):
    app.message("input:")
    for codebit in characters.split():
        try:        
            code = int(codebit, 16)
        except ValueError:
            continue
        line = char_detail_line(code)
        app.message(line)
        
#
def unicode_commands():
    return describe_command_package(
        description="文字に関するコマンドです。"
    )["unicode"](
        describe_command(
            process=encode_unicodes,
            description="文字を入力 -> コードにする"
        )["target characters"](
            help="コードにしたい文字列"
        )
    )["unidec"](
        describe_command(
            process=decode_unicodes,
            description="コードを入力 -> 文字にする"
        )["target characters"](
            help="文字列にしたいコード"
        )
    )        
