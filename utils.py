
def getNiceName(name, full=False):
    if full:
        return name.replace(':', '_').replace('|', '_')
    return name.split(':')[-1].split('|')[-1]


frameno_re = re.compile(r'\d+')
def removeLastNumber(path, bychar='?'):
    dirname, basename = op.split(path)
    numbers = frameno_re.findall(basename)
    if numbers:
        pos = basename.rfind(numbers[-1])
        basename = basename[:pos] + basename[pos:].replace(numbers[-1], bychar
                * len(numbers[-1]))
        path = op.normpath( op.join(dirname, basename) )
        return path, numbers[-1]
    return path, ''


def newScene(func = None):
    '''
    Make a bare scene.
    '''
    def wrapper(*arg, **kwarg):

        if kwarg.get("newScene"):
            pc.newFile(f=True)
        else: pass
        return func(*arg, **kwarg)
    return wrapper if func else pc.newFile(f=True)


def newcomerObjs(func):
    '''
    @return: the list of objects that were added to the scene
    after calling func
    '''
    def wrapper(*arg, **kwarg):
        selection = cmds.ls(sl = True)
        cur = cmds.ls()
        func(*arg, **kwarg)
        new = objSetDiff(cmds.ls(), cur)
        pc.select(selection)
        return new
    return wrapper


def undoChunk(func):
    ''' This is a decorator for all functions that cause a change in a maya
    scene. It wraps all changes of the decorated function in a single undo
    chunk
    '''
    def _wrapper(*args, **dargs):
        res = None
        try:
            undoChunk = dargs.pop('chunkOpen')
        except KeyError:
            undoChunk = None
        if undoChunk is True:
            pc.undoInfo(openChunk=True)
        try:
            res = func(*args, **dargs)
        finally:
            if undoChunk is False:
                pc.undoInfo(closeChunk=True)
            return res
    return _wrapper

