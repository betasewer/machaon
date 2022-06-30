import subprocess

class Exports:
    @staticmethod
    def clipboard_copy(text):
        """ クリップボードにテキストをコピーする """
        process = subprocess.Popen("pbcopy", stdin=subprocess.PIPE, close_fds=True)
        process.communicate(text.encode('utf-8'))

    @staticmethod
    def clipboard_paste():
        """ クリップボードからテキストをペーストする """
        process = subprocess.Popen(['pbpaste', 'r'], stdout=subprocess.PIPE, close_fds=True)
        stdout, stderr = process.communicate()
        return stdout.decode('utf-8')

