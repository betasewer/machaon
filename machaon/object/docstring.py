from itertools import takewhile

#
class DocStringParseError(Exception):
    pass

#
#
#
class DocStringParser():
    def __init__(self, doc, section_names):
        sections = {k:[] for k in section_names + ("Summary", "Description")}

        lines = doc.splitlines()
        if not lines:
            raise DocStringParseError()
        
        sections["Summary"].append(lines[0])

        key = "Description"
        for line in lines[1:]:
            part, sep, rest = line.partition(":")
            if sep and part.strip() in sections:
                key = part.strip()
                if rest:
                    sections[key].append(rest)
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
