#!/usr/bin/env python3
# coding: utf-8

import os
import unicodedata

#
# エラー文字表示方法を指定してエンコーディング変換
#
def reencode(s, encoding, errors="replace"):
    return s.encode(encoding,errors).decode(encoding)

#
# 指定の長さ以下は省略する
#
def collapse_text(text, width):
    results = []
    for s in text.splitlines():
        s_width = 0
        s_res = ""
        for c in s:
            if c == "\n":
                break
        
            c_width = (2 if unicodedata.east_asian_width(c) in u"WFA" else 1)
            if s_width + c_width > width:
                s_res += "..."
                break
                
            s_width += c_width
            s_res += c

        results.append(s_res)
    return "\n".join(results)
        
#
# 指定の数値で改行、字下げを入れる
#
def composit_text(s, max_width, indent, first_indent=None):
    if first_indent is None:
        first_indent = indent
        
    text = " " * indent
    line_width = 0
    for ch in s:
        line_width += (2 if unicodedata.east_asian_width(ch) in u"WFA" else 1)
        text += ch
        
        if line_width > max_width:
            ch = "\n"
            text += " " * indent
            
        if ch == "\n":
            text += " " * first_indent
            line_width = 0
        
    return text

#
def complete_break(text):
    if text[-1:]!="\n":
        return text+"\n"
    else:
        return text

#
def drop_break(text):
    if text[-1:]!="\n":
        return text
    else:
        return text[:-1]
    
#
# 選択肢
#
def test_yesno(answer):
    if answer == "Y" or answer == "y":
        return True
    elif answer == "N" or answer == "n":
        return False
    else:
        return False
