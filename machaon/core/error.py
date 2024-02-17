from typing import Any

class ErrorSetValue:
    def __init__(self, error, value=None, message=None, stackdelta=0):
        self.error: Exception = error
        self.value: Any = value
        self.message: str = message
        self.stackdelta = stackdelta
        
    def __repr__(self) -> str:
        return "<ErrorSetValue {}\n    {}\n    {}>".format(
            self.error, self.message, self.value
        )
    
    def displays(self):
        if self.message is not None:
            yield "エラー発生:" + self.message
        
        if self.error is not None:
            from machaon.types.stacktrace import ErrorObject
            err = ErrorObject(self.error)
            for l in err.short_display(self.stackdelta).splitlines():
                yield "    " + l

        if self.value is None and self.message is None:
            return

        parts = []
        if self.value is not None:
            if isinstance(self.value, (list, tuple)):
                parts.append("{}".format(self.value))
            else:
                parts.append("({})".format(self.value))
        yield " ".join(parts)



class ErrorSet:
    def __init__(self, message):
        self._errors = []
        self._message = message

    def try_(self, fn, *args, value=None, message=None):
        try:
            return fn(*args)
        except Exception as e:
            self.add(e, value, message, 1)

    def add(self, e: Exception, value= None, message:str = None, stackdelta = 0):
        self._errors.append(ErrorSetValue(e, value, message, stackdelta))

    def failed(self):
        return len(self._errors) > 0

    def throw_if_failed(self):
        if self._errors:
            raise self.Error(self._errors, self._message)
    
    def printout(self, *, spirit=None, printer=None):
        if self._errors:
            err = self.Error(self._errors, self._message)
            if spirit:
                spirit.post("error", str(err))
            elif printer:
                printer(str(err))
        
    def __enter__(self):
        return self
    
    def __exit__(self, et, ev, tb):
        self.throw_if_failed()

    class Error(Exception):
        def __str__(self):
            errors = self.args[0]
            message = self.args[1]

            # 最初の1件だけ表示
            if not errors:
                return "<no error is contained>"
            
            count = len(errors)

            header = "{}件のエラーが発生:".format(min(count, 3))
            if message is not None:
                header += " ［{}］".format(message)
            lines = [header]
            for x in errors[:3]:
                x: ErrorSetValue
                lines.extend(x.displays())
                lines.append("")
            if count > 3:
                lines.append("  ...（さらに{}件のエラーが発生)".format(count-3))

            return "\n".join(lines)
