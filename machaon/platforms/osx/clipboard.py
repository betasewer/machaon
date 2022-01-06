import subprocess

def clipboard_copy(text):
    """ クリップボードにテキストをコピーする """
    process = subprocess.Popen("pbcopy", stdin=subprocess.PIPE, close_fds=True)
    process.communicate(text.encode('utf-8'))

def clipboard_paste(text):
    """ クリップボードからテキストをペーストする """
    process = subprocess.Popen(['pbpaste', 'r'], stdout=subprocess.PIPE, close_fds=True)
    stdout, stderr = process.communicate()
    return stdout.decode('utf-8')
