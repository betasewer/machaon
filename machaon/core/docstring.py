from collections import defaultdict
from typing import Sequence
from machaon.core.symbol import SIGIL_DEFINITION_DOC

#
class DocStringParseError(Exception):
    pass

#
#
#
class DocStringParser:
    def __init__(self, doc, section_names, indented_with_head=True):
        self.sections = {}

        lines = doc.splitlines()
        if not lines:
            return
        
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
    
    def get_sections(self):
        return self.sections



class DocStringDeclaration:
    @classmethod
    def parse(cls, doc: str):
        # 印を落とす
        if doc[0] == SIGIL_DEFINITION_DOC:
            doc = doc[1:]

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
            raise ValueError("no decltype is specified")
        decltype = decls[0]

        if "alias-name" in decls:
            if not aliasnames:
                raise ValueError("alias-nameが指定されましたが、エイリアスの定義がありません")
            return cls(decltype, aliasnames[0], aliasnames[1:], set(decls), rest)
        else:
            return cls(decltype, None, aliasnames, set(decls), rest)

    def __init__(self, decltype, name, aliases, props, rest):
        self.decltype = decltype
        self.name = name
        self.aliases = aliases 
        self.props = props
        self.rest = rest
    
    def get_rest(self):
        return self.rest

    def get_first_alias(self):
        if self.name is None:
            if self.aliases:
                return self.aliases[0]
            else:
                return None
        else:
            return self.name


def get_doc_declaration_type(doc):
    """ 定義タイプのみを取り出す """
    doc = doc.lstrip()
    # 印
    if not doc.startswith(SIGIL_DEFINITION_DOC):
        return None
    doc = doc[1:]
    # 先頭のタイプを取り出す
    line, br, rest = doc.partition("\n") 
    if not br:
        line = doc
    typedecl, sep, _ = line.partition(" ")
    return typedecl.rstrip()

def parse_doc_declaration(obj, decltypes):
    if isinstance(obj, str):
        doc = obj
    else:
        doc = getattr(obj, "__doc__", None)
        if doc is None:
            return None    
    doc = doc.strip()

    # 宣言タイプ
    decltype = get_doc_declaration_type(doc)
    if decltype is None or decltype not in decltypes: # タイプをチェック
        return None
    return DocStringDeclaration.parse(doc)


class DocStringDefinition:
    @classmethod
    def parse(cls, decl: DocStringDeclaration, sectionnames: Sequence[str]):
        # 宣言から切り離したのでインデントの考慮は必要ない
        parser = DocStringParser(decl.get_rest(), sectionnames, indented_with_head=False)
        return cls(decl).set_parsed(parser)

    def __init__(self, decl=None, parser=None):
        self._decl = decl
        self._parser = parser
        self._sections = {}

    def set_parsed(self, p):
        self._parser = p
        self._sections.update(p.get_sections())
        return self

    def is_declared(self, v):
        """
        宣言された要素
        """
        return v in self._decl.props
    
    def get_first_alias(self):
        """
        """
        return self._decl.get_first_alias()
    
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
            if k not in self._sections:
                continue
            ls = self._sections[k]
            lines.extend(ls)
        return lines


