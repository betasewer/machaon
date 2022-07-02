import subprocess
import threading
import queue

from typing import Any, List, Sequence, Optional

#
class StdoutReader():
    def __init__(self):
        self.endevent = False
        self.readlines = queue.Queue()
    
    def stop(self):
        self.endevent = True

    def read(self, buf, encoding):
        linebuf = ""
        bufread = buf.read
        chunk = 512
        readchar = None
        while not self.endevent:
            buf.flush()
            bits = bufread(chunk)
            try:
                text = bits.decode(encoding)
            except UnicodeDecodeError as e:
                for _ in range(4):
                    bits += bufread(1)
                    try:
                        text = bits.decode(encoding)
                    except UnicodeDecodeError:
                        continue
                    else:
                        break
                else:
                    text = "<{}>".format(e) # エンコードエラー
            
            for ch in text:
                if ch == '\r':
                    self.readlines.put(linebuf)
                    linebuf = ""
                elif ch == '\n':
                    if readchar == '\r':
                        continue
                    self.readlines.put(linebuf)
                    linebuf = ""
                else:
                    linebuf += ch
                readchar = ch
        
        if linebuf:
            self.readlines.put(linebuf)

#
#
#
def popen_capture(cmds, *, encoding=None, **popenargs):
    from machaon.platforms import ui
    shell_encoding = encoding or ui().default_encoding

    proc = subprocess.Popen(cmds, 
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
        **popenargs
    )
    
    stdoutreader = StdoutReader()
    readthread = threading.Thread(None, target=stdoutreader.read, args=(proc.stdout, shell_encoding), daemon=True, name="POpenCapture_StdIOReader")
    readthread.start()
    
    while True:
        # 入力を待つ
        inputmsg = yield PopenMessage(mode=POPEN_WAITINPUT)
        if inputmsg is None:
            proc.stdin.close()
        elif inputmsg:
            if inputmsg.mode == POPEN_KILLED:
                proc.kill()
                stdoutreader.stop()
                yield PopenMessage(mode=POPEN_KILLED) # send用に吐く最後のメッセージ
                break
            elif inputmsg.value is not None:
                proc.stdin.write((inputmsg.value+'\n').encode(shell_encoding))
                proc.stdin.flush()
        
        # 出力を取り出す
        try:
            msg = stdoutreader.readlines.get(timeout=0.2) # 読み取られた出力をキューから一行取り出す
            yield PopenMessage(value=msg, mode=POPEN_OUTPUT)
        except queue.Empty:
            # プロセス終了
            returncode = proc.poll()
            if returncode is not None:
                stdoutreader.stop()
                yield PopenMessage(value=returncode, mode=POPEN_FINISHED)
                break
            else:
                yield PopenMessage(mode=POPEN_OUTPUT_EMPTY) # inputとoutputでメッセージの数をそろえるための空メッセージ

    readthread.join(timeout=10) # タイムアウト後はデーモンスレッドなので強制終了となる

#
#
#
POPEN_OUTPUT = 0
POPEN_WAITINPUT = 1
POPEN_FINISHED = 2
POPEN_KILLED = 3
POPEN_OUTPUT_EMPTY = 4

class PopenMessage():
    def __init__(self, *, mode, value=None):
        self.value = value
        self.mode = mode
    
    def is_waiting_input(self):
        return self.mode == POPEN_WAITINPUT
        
    def is_output(self):
        return self.mode == POPEN_OUTPUT
    
    def is_empty(self):
        return self.mode == POPEN_OUTPUT_EMPTY
    
    def is_finished(self):
        return self.mode == POPEN_FINISHED
    
    def sendto(self, sequence, msg):
        newmsg = sequence.send(msg)
        self.value = newmsg.value
        self.mode = newmsg.mode
        return self
    
    def send_input(self, sequence, inputtext):
        self.value = inputtext
        return self.sendto(sequence, self)
    
    def skip_input(self, sequence):
        self.value = None
        return self.sendto(sequence, self)
    
    def end_input(self, sequence):
        return self.sendto(sequence, None)
    
    @property
    def returncode(self):
        if not self.is_finished():
            raise ValueError("Not finished yet")
        return self.value
    
    @property
    def text(self):
        if not self.is_output():
            raise ValueError("No text")
        return self.value

    def send_kill(self, sequence):
        self.mode = POPEN_KILLED
        return self.sendto(sequence, self)
    
#
#
#
if __name__ == "__main__":
    import sys
    if len(sys.argv)<2:
        cmds = ["time"]
    else:
        cmds = sys.argv[1:]
    
    proc = popen_capture(cmds, shell=True)
    for msg in proc:
        if msg.is_waiting_input():
            inp = input(">")
            if inp == 'q':
                msg.end_input(proc)
            elif inp:
                msg.send_input(proc, inp)
            else:
                msg.skip_input(proc)
        
        if msg.is_output():
            print(msg.text)
        
        if msg.is_finished():
            print("プロセスはコード={}で終了しました".format(msg.returncode))
        