TOKEN_TERM = 0x01
TOKEN_BLOCK_BEGIN = 0x02
TOKEN_BLOCK_END = 0x04
TOKEN_STRING = 0x10

def read_token(source):
    buffer = []
    def flush(buf, tokentype):
        string = "".join(buf)
        if string:
            # 空であれば排出しない
            yield (string, tokentype)
            buf.clear()
    
    buffer = []
    quoted_by = None
    paren_count = 0
    for ch in source:
        if not quoted_by and (ch == "'" or ch == '"'):
            quoted_by = ch
        elif quoted_by and quoted_by == ch:
            quoted_by = None
            yield from flush(buffer, TOKEN_TERM|TOKEN_STRING)
        elif quoted_by is None:
            if ch == "(":
                yield from flush(buffer, TOKEN_TERM)
                yield ("", TOKEN_BLOCK_BEGIN)
                paren_count += 1
            elif ch == ")":
                yield from flush(buffer, TOKEN_TERM)
                yield ("", TOKEN_BLOCK_END)
                paren_count -= 1
                if paren_count < 0:
                    raise SyntaxError("始め括弧が足りません")
            elif ch.isspace():
                yield from flush(buffer, TOKEN_TERM)
            else:
                buffer += ch
        else:
            buffer += ch

    yield from flush(buffer, TOKEN_TERM)
    if paren_count > 0:
        raise SyntaxError("終わり括弧が足りません")



print(list(read_token("yama sashi ulix")))
print(list(read_token("'this is quoted.'")))
print(list(read_token("'this ' saka")))
print(list(read_token("((1 add 2) mul 5)")))

