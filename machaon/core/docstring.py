from collections import defaultdict
from itertools import takewhile
import os.path

#
class DocStringParseError(Exception):
    pass

#
#
#
class DocStringParser():
    def __init__(self, doc, section_names, indented_with_head=True):
        lines = doc.splitlines()
        if not lines:
            raise DocStringParseError()
        
        indent = self.detect_indent(lines, indented_with_head)

        # キーのエイリアス辞書を作成
        keymap = {}
        for secnames in section_names:
            keys = secnames.split()
            for k in keys:
                keymap[k] = keys[0]
        
        # セクションの値を取り出す
        sections = defaultdict(list)
        curkey = "Document"
        for i, line in enumerate(lines):
            if i == 0 and indented_with_head:
                line = line.strip() # 一行目は全インデントを削除
            else:
                line = line[indent:]
            part, sep, rest = line.partition(":")
            if sep:
                newkey = part.strip()
                if part.startswith(("  ", "\t")) or " " in newkey:
                    sections[curkey].append(line) # タブまたは空白2つ以上ではじまるか、空白が語中に含まれているならセクション名とみなさない
                    continue
                if newkey[0].islower():
                    newkey = newkey[0].upper() + newkey[1:]
                if newkey not in keymap:
                    raise DocStringParseError("定義されていないセクションです: {}".format(newkey), doc)
                else:
                    k = keymap[newkey]
                    if rest:
                        sections[k].append(rest)
                    curkey = k
            else:
                sections[curkey].append(line)
        
        # 最後の改行を落とす
        self.sections = {}
        for k, ls in sections.items():
            lls = []
            # 前後についている空行を落とす
            itr = (l for l in ls)
            for l in itr:
                if len(l.strip()) == 0: continue                
                lls.append(l)
                break
            for l in itr:
                if len(l.strip()) == 0: break
                lls.append(l)
            self.sections[k] = lls

    def detect_indent(self, lines, ignore_first_line):
        """ 無視するべき余分なインデントを計算 """
        if ignore_first_line:  # 1行目は考慮しない
            lines = lines[1:]
        
        indent = None
        for line in lines:
            spaced = len(line) - len(line.lstrip())
            if indent is None:
                indent = spaced
            else:
                indent = min(indent, spaced)
        return indent

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
            lines.extend(ls)
        return lines


class DocStringDeclaration:
    def __init__(self, decltype, name, aliases, props, rest):
        self.decltype = decltype
        self.name = name
        self.aliases = aliases 
        self.props = props
        self.rest = rest
    
    def create_parser(self, section_names): 
        return DocStringParser(self.rest, section_names, indented_with_head=False) # 宣言から切り離したのでインデントの考慮は必要ない


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

    # タイプをチェック
    if not any(doc.startswith(x) for x in decltypes):
        return None

    # ドキュメントの第一行目に書かれている
    line, br, rest = doc.partition("\n") 
    if not br:
        line = doc

    # エイリアス
    aliasnames = []
    if "[" in line and "]" in line: # [name1 name2 name3]
        line, _, aliasrow = line.partition("[")
        aliasrow, _, _ = aliasrow.partition("]")
        aliasnames = aliasrow.strip().split()

    # 指定子
    decls = line.split()
    if not decls:
        return None
    decltype = decls[0]
    
    if "alias-name" in decls:
        if not aliasnames:
            raise ValueError("alias-nameが指定されましたが、エイリアスの定義がありません")
        return DocStringDeclaration(decltype, aliasnames[0], aliasnames[1:], set(decls), rest)
    else:
        return DocStringDeclaration(decltype, None, aliasnames, set(decls), rest)


