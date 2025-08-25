from __future__ import annotations
import mimetypes
import csv
from io import StringIO, BytesIO

from machaon.types.file import detect_text_encoding

USING_FRAMEWORK = "fastapi"

# class AnyBlob:
class ContentType:
    def __init__(self, *, mimetype=None, encoding=None, extension=None, text_encoding=None):
        self.extension = extension
        self.mimetype = mimetype
        self.encoding = encoding
        self.text_encoding = text_encoding or text_encoding

    @classmethod
    def from_extension(cls, extension: str):
        ctype, encoding = mimetypes.guess_type("file" + extension)
        if encoding is None:
            encoding = "utf-8"
        ctype = ctype or "application/octet-stream"
        return cls(mimetype=ctype, encoding=encoding, extension=extension)
    

class ContentBits:
    def __init__(self, bits: bytes, content_type: ContentType):
        self.bits = bits
        self.content_type = content_type

    def text(self, encoding=None, errors="replace"):
        if self.content_type.text_encoding:
            return self.bits.decode(self.content_type.text_encoding, errors=errors)
        else:
            return self.bits.decode(encoding or "utf-8", errors=errors)
    
    @classmethod
    def from_text_file(cls, file, possible_encodings=None):
        if possible_encodings is None:
            encoding = None
        else:
            encoding = detect_text_encoding(file, encodings=possible_encodings)
        bits = file.read()
        return cls(bits=bits, content_type=ContentType(mimetype="text/plain", text_encoding=encoding, extension=".txt"))

    @classmethod
    def from_csv_rows(cls, rows: list[str], encoding: str, errors="replace", csv_writer=None):
        csvfile = StringIO()
        
        if csv_writer is not None:
            wrt = csv_writer(csvfile)
        else:
            import csv
            wrt = csv.writer(csvfile)
        wrt.writerows(rows)

        csvfile.seek(0)
        bits = csvfile.getvalue().encode(encoding, errors=errors)
        return cls(bits=bits, content_type=ContentType(mimetype="text/plain", text_encoding=encoding, extension=".csv"))

    @classmethod
    def from_text_writer(cls, wrt, encoding: str, errors="replace", extension=".txt"):
        buf = StringIO()
        wrt(buf)
        buf.seek(0)
        bits = buf.getvalue().encode(encoding, errors=errors)
        return cls(bits=bits, content_type=ContentType(mimetype="text/plain", text_encoding=encoding, extension=extension))
    
    @classmethod
    def from_saving_file(cls, file, content_type: ContentType):
        buf = BytesIO()
        doc = file.load()
        doc.save(buf)
        return cls(bits=buf.getvalue(), content_type=content_type)
    
    @classmethod
    def from_binary_writer(cls, wrt, content_type: ContentType):
        buf = BytesIO()
        wrt(buf)
        return cls(bits=buf.getvalue(), content_type=content_type)
    
    def values(self, headers=None):
        # レスポンスに渡す引数を返す
        if USING_FRAMEWORK == "fastapi":
            if headers is None:
                headers = {}
            if self.content_type.encoding:
                headers["Content-Encoding"] = self.content_type.encoding
            return {
                "content": self.bits, 
                "media_type": self.content_type.mimetype,
                "headers": headers
            }
        else:
            raise NotImplementedError("ContentBits.to_response is not implemented for this framework")


CTS_PDF = ContentType(mimetype="application/pdf", extension=".pdf")
CTS_WORD = ContentType(mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document", extension=".docx")
CTS_EXCEL = ContentType(mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", extension=".xlsx")
