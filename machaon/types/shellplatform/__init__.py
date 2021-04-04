
#
#
#
def shellplatform():
    """
    プラットフォームごとの実装を呼び出す
    """
    module = None 
    import sys
    system = sys.platform
    if system == "win32":
        import machaon.types.shellplatform.win32 as module
    elif system == "darwin":
        import machaon.types.shellplatform.darwin as module
    else:
        raise ValueError("Unsupported system: "+system)
    return module
    
