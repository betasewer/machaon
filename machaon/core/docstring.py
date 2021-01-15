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
                if part.startswith("  ") or " " in newkey:
                    sections[key].append(line) # 空白2つ以上ではじまるか、空白が語中に含まれているならセクション名とみなさない
                elif newkey not in sections:
                    raise DocStringParseError("Unknown section name: {}".format(newkey), doc)
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
