from itertools import takewhile
import os.path

#
class DocStringParseError(Exception):
    pass

#
#
#
class DocStringParser():
    def __init__(self, doc, section_names):
        sections = {k:[] for k in section_names + ("Decl", "Description")}

        lines = doc.splitlines()
        if not lines:
            raise DocStringParseError()

        # 無視するべき余分なインデント
        indent = len(os.path.commonprefix(lines[1:]))

        sections["Decl"].append(lines[0])

        key = "Description"
        for line in lines[1:]:
            line = line[indent:]
            part, sep, rest = line.partition(":")
            if sep:
                newkey = part.strip()
                if part.startswith(("  ", "\t")) or " " in newkey:
                    sections[key].append(line) # タブまたは空白2つ以上ではじまるか、空白が語中に含まれているならセクション名とみなさない
                    continue
                if newkey[0].islower():
                    newkey = newkey[0].upper() + newkey[1:]
                if newkey not in sections:
                    raise DocStringParseError("定義されていないセクションです: {}".format(newkey), doc)
                else:
                    if rest:
                        sections[newkey].append(rest)
                    key = newkey
            else:
                sections[key].append(line)
        
        self.sections = sections

    def get_value(self, key, default=None):
        """
        最後の値を取る
        """
        lines = self.get_lines(key)
        if not lines:
            return default
        return lines[-1].strip()
    
    def get_string(self, *keys):
        """
        結合した複数行を受け取る
        """
        return "\n".join(self.get_lines(*keys))

    def get_lines(self, *keys):
        """
        行データを受け取る
        """
        lines = []
        for k in keys:
            if k not in self.sections:
                continue
            ls = self.sections[k]
            # 末尾についている空行を落とす
            tail = len(list(takewhile(lambda l:len(l.strip())==0, reversed(ls))))
            if tail>0:
                lines.extend(ls[:-tail])
            else:
                lines.extend(ls)
        return lines


class DocStringDeclaration:
    def __init__(self, decltype, name, aliases, props):
        self.decltype = decltype
        self.name = name
        self.aliases = aliases 
        self.props = props


def parse_doc_declaration(obj, decltypes):
    if isinstance(obj, str):
        doc = obj
    else:
        doc = getattr(obj, "__doc__", None)
        if doc is None:
            return None
    
    doc = doc.strip()

    # 印
    if not doc.startswith("@"):
        return None
    doc = doc[1:] # 落とす

    # ドキュメントの第一行目に書かれている
    line, br, _ = doc.partition("\n") 
    if not br:
        line = doc

    # エイリアス
    aliasrow = ""
    if "[" in line and "]" in line: # [name1 name2 name3]
        line, _, aliasrow = line.partition("[")
        aliasrow, _, _ = aliasrow.partition("]")
    aliasnames = aliasrow.strip().split()

    # 指定子
    decls = line.split()
    if not decls:
        return None
    decltype = decls[0]

    if decltype not in decltypes:
        return None
    
    if "alias-name" in decls:
        if not aliasnames:
            raise ValueError("alias-nameが指定されましたが、エイリアスの定義がありません")
        return DocStringDeclaration(decltype, aliasnames[0], aliasnames[1:], set(decls))
    else:
        return DocStringDeclaration(decltype, None, aliasnames, set(decls))
