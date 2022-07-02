#!/usr/bin/env python3
# coding: utf-8

import os
import unicodedata

#
# エラー文字表示方法を指定してエンコーディング変換
#
def reencode(s, encoding, errors="replace"):
    return s.encode(encoding,errors).decode(encoding)

def xprint(*args, **kwargs):
    from machaon.platforms import ui
    s = " ".join([str(x) for x in args])
    s = reencode(s, ui().default_encoding)
    print(s, **kwargs)
    
    
#
#
#
def get_char_width(c, *, a=True, tab_width=4):
    if c == "\t":
        return tab_width
    
    cat = unicodedata.category(c)
    if cat == "Cc" or cat == "Cf":
        return 0

    eaw = unicodedata.east_asian_width(c)
    if eaw in u"WF":
        return 2
    if a and eaw == u"A":
        return 2

    return 1

def get_text_width(text, *, a=True):
    width = 0
    for ch in text:
        chwidth = get_char_width(ch, a=a)
        width += chwidth
    return width

def ljust(text, width, sep=" "):
    return text + sep * (width - get_text_width(text))

def rjust(text, width, sep=" "):
    return sep * (width - get_text_width(text)) + text


#
# 指定の長さ以下は省略する
#
def collapse_text(text, width, tab_width=4):
    results = []
    for s in text.splitlines():
        s_width = 0
        s_res = ""
        for c in s:
            if c == "\n":
                break
        
            c_width = get_char_width(c, a=True, tab_width=tab_width)
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
#  *first_indent 一行目の字下げ（絶対的値）
#
class CompositText():
    def __init__(self, tab_width=4, a_width=True):
        self._tab_width = tab_width
        self._a_width = a_width
    
    # 文字列を折り返し、新たな各行の幅を返すジェネレータ
    def lines(self, s, width, *, first_indent=0):
        if first_indent and not isinstance(first_indent, int):
            raise TypeError("first_indent")

        line = ""
        linewidth = 0
        for ch in s:
            if ch == "\n":
                yield (line, linewidth)
                line = ""
                linewidth = 0
                continue
            
            if linewidth == 0 and first_indent:
                line += " " * first_indent
                linewidth += first_indent
            
            new_linewidth = linewidth + get_char_width(ch, a=self._a_width, tab_width=self._tab_width)
            if new_linewidth > width:
                yield (line, linewidth)
                line = ch
                linewidth = new_linewidth - linewidth
            else:
                line += ch
                linewidth = new_linewidth

        yield (line, linewidth)
        line = ""
        linewidth = 0
    
    # 足りない幅を指定の文字で補うジェネレータ（デフォルトは半角スペース）
    def filled_lines(self, s, width, *, fill=" ", first_indent=None):
        if isinstance(fill, tuple):
            f2 = fill[1]
            fill = fill[0]
        else:
            if fill is True:
                fill = " "
            f2 = None

        fillunitwidth = get_char_width(fill)
        for line, linewidth in self.lines(s, width, first_indent=first_indent):
            fillerwidth = width-linewidth
            filler = fill * (fillerwidth // fillunitwidth)
            
            if f2 is not None and (fillerwidth % fillunitwidth) != 0:
                # 単位を合わせるために第2の詰め文字で埋める
                filler = f2 * (fillerwidth % fillunitwidth) + filler

            yield (line + filler), width

    # 連結した文字列を返す
    def __call__(self, s, width, *, fill=None, first_indent=0) -> str:
        if fill is not None:
            lines = self.filled_lines(s, width, fill=fill, first_indent=first_indent)
        else:
            lines = self.lines(s, width, first_indent=first_indent)

        texts = []
        for line, _linewidth in lines:
            texts.append(line)
        return "\n".join(texts)

# API
composit_text = CompositText()


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
def parserecord(s, sep=None, *, length=None, default="", nostrip=False):
    if isinstance(sep, str):
        if length is None:
            raise TypeError("specify record length")
        if sep is None:
            sep = ' '
        sep = tuple(sep for x in range(length-1))

    length = len(sep)+1

    spl = []
    parting = s
    for asep in sep:
        value, separator, parting = parting.partition(asep)
        spl.append(value)
        if not separator: # 区切れなかった
            break

    if parting:
        spl.append(parting)

    if not nostrip:
        spl = [x.strip() for x in spl]

    if isinstance(default, tuple):
        if len(default) < length:
            raise ValueError("Too short default sequence is specified")
        for i in range(length):
            if i >= len(spl):
                spl.append(default[i])
    else:
        spl.extend([default for _ in range(length-len(spl))])

    return spl

#
#
#
class MiniProgressDisplay:
    def __init__(self, spirit, total=None, tag=None, width=30, title=None):
        self.spirit = spirit
        self.total = total
        self.progress = None
        self.tag = tag or "message"
        self.width = width
        self.title = title or ""
        self.marquee = None if total else 0
        self.lastbit = None

    def is_starting(self):
        """ updateでバーが初めて表示された """
        return self.progress == 0
    
    def set_total(self, total):
        if total:
            self.total = total
            self.marquee = None
        else:
            self.total = None
            self.marquee = 0
    
    def header(self):
        if self.title:
            return "{}: ".format(self.title)
        else:
            return ""

    def update(self, delta=None):
        progress = self.progress 
        if progress is None:
            progress = 0
        else:
            progress += int(delta)

        if self.marquee is not None:
            mq = self.marquee
            midbarwidth = 3
            fullbar = self.width * "-" + "o" * midbarwidth + (self.width + midbarwidth) * "-"
            d = mq # int(self.width / midbarwidth * mq)
            if self.width + midbarwidth * 2 <= d:
                d = 0
                mq = 0
            
            bar = "[{}] ({})".format(fullbar[d:self.width+d], progress)
            bit = mq

            self.marquee = mq + 1
        else:
            rate = progress / self.total
            hund = 100 * rate
            factor = self.width / 100
            head = round(factor * hund)
            rest = self.width - head
            isum = round(progress)
            itot = round(self.total)

            bit = round(hund)
            bar = "[{}{}] {}% ({}/{})".format(head*"o", rest*"-", bit, isum, itot)

        if self.lastbit != bit:
            if self.lastbit is not None:
                self.spirit.post("delete-message", count=1, line=-1)
            self.spirit.post(self.tag, self.header() + bar)
            self.lastbit = bit
        
        self.progress = progress
    

    def finish(self, total):
        if self.progress is not None:
            self.spirit.post("delete-message")
        
        bar = bar = "[{}] 完了 ".format("o"*self.width)
        if self.total is not None:
            bar += "({})".format(self.total)
        else:
            bar += "({})".format(self.progress)
        self.spirit.post(self.tag, self.header() + bar)
