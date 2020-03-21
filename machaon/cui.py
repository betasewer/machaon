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
#
#
def get_char_width(c, *, a=False):
    eaw = unicodedata.east_asian_width(c)
    if eaw in u"WF":
        return 2
    if a and eaw == u"A":
        return 2
    return 1

def get_text_width(text, *, a=False):
    width = 0
    for ch in text:
        chwidth = get_char_width(ch, a=True)
        width += chwidth
    return width

def ljust(text, width, sep=" "):
    return text + sep * (width - get_text_width(text))

def rjust(text, width, sep=" "):
    return sep * (width - get_text_width(text)) + text


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
        
            c_width = get_char_width(c, a=True)
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
#  max_width 全体の幅
#  indent 全体の字下げ
#  *first_indent 一行目の字下げ（絶対）
#
def composit_text(s, max_width, indent, first_indent=None):
    if first_indent is None:
        first_indent = indent
        
    text = " " * indent
    line_width = 0
    for ch in s:
        line_width += get_char_width(ch, a=True)
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

#
#
#
def fixsplit(s, sep=None, *, maxsplit, default=""):
    spl = s.split(sep=sep, maxsplit=maxsplit)
    if maxsplit>0:
        for _ in range(maxsplit-len(spl)+1):
            spl.append(default)
    return spl

#
#
#
class MiniProgressDisplay:
    def __init__(self, spirit, total=None, tag=None, width=30, title=None):
        self.spirit = spirit
        self.total = total
        self.suma = None
        self.tag = tag
        self.width = width
        self.title = title or "進行中"
        self.marquee = None if total is not None else 0

    def update(self, delta=None):
        suma = self.suma 
        if suma is None:
            suma = 0
        else:
            suma += delta
            self.spirit.delete_message()

        if self.marquee is not None:
            mq = self.marquee
            midbarwidth = 2
            fullbar = self.width * "-" + "o" * midbarwidth + (self.width + midbarwidth) * "-"
            d = int(self.width / midbarwidth * mq)
            if self.width + midbarwidth * 2 <= d:
                d = 0
                mq = 0
            bar = "[{}] ({})".format(fullbar[d:self.width+d], suma)
            self.marquee = mq + 1
        else:
            rate = suma / self.total
            hund = 100 * rate
            factor = self.width / 100
            head = round(factor * hund)
            rest = self.width - head
            isum = round(suma)
            itot = round(self.total)
            bar = "[{}{}] {}% ({}/{})".format(head*"o", rest*"-", round(hund), isum, itot)

        bar = "{}: ".format(self.title) + bar
        self.spirit.custom_message(self.tag, bar)
        self.suma = suma

    #
    def finish(self, total):
        if self.suma is not None:
            self.spirit.delete_message()
        bar = "[{}] 完了 ({})".format("o"*self.width, total)
        bar = "{}: ".format(self.title) + bar
        self.spirit.custom_message(self.tag, bar)
