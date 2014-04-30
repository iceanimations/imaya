# Date: Wed 28/11/2012
# Author : Qurban Ali (qurban.ali@iceanimations.com),
#          Hussain Parsaiyan (hussain.parsaiyan@iceanimations.com)

import random, os, shutil, warnings, re, stat, subprocess
import time
import hashlib
import functools
import cProfile
import tempfile
import itertools
op = os.path
import subprocess
import datetime
import collections
from os.path import curdir, join, abspath, splitunc, splitdrive, sep, pardir

class memoize(object):
   '''Decorator. Caches a function's return value each time it is called.
   If called later with the same arguments, the cached value is returned
   (not reevaluated).
   '''
   
   def __init__(self, func):
      self.func = func
      self.cache = {}
   def __call__(self, *args):
      if not isinstance(args, collections.Hashable):
         # uncacheable. a list, for instance.
         # better to not cache than blow up.
         return self.func(*args)
      if args in self.cache:
          return self.cache[args]
      else:
         value = self.func(*args)
         self.cache[args] = value
         return value
   def __repr__(self):
      '''Return the function's docstring.'''
      return self.func.__doc__
   def __get__(self, obj, objtype):
      '''Support instance methods.'''
      return functools.partial(self.__call__, obj)


def _abspath_split(path):
    abs = abspath(op.normpath(path))
    prefix, rest = splitunc(abs)
    is_unc = bool(prefix)
    if not is_unc:
        prefix, rest = splitdrive(abs)
    return is_unc, prefix, [x for x in rest.split(sep) if x]

def relpath(path, start=curdir):
    """Return a relative version of a path"""

    if not path:
        raise ValueError("no path specified")

    start_is_unc, start_prefix, start_list = _abspath_split(start)
    path_is_unc, path_prefix, path_list = _abspath_split(path)

    if path_is_unc ^ start_is_unc:
        raise ValueError("Cannot mix UNC and non-UNC paths (%s and %s)"
                                                            % (path, start))
    if path_prefix.lower() != start_prefix.lower():
        if path_is_unc:
            raise ValueError("path is on UNC root %s, start on UNC root %s"
                                                % (path_prefix, start_prefix))
        else:
            raise ValueError("path is on drive %s, start on drive %s"
                                                % (path_prefix, start_prefix))
    # Work out how much of the filepath is shared by start and path.
    i = 0
    for e1, e2 in zip(start_list, path_list):
        if e1.lower() != e2.lower():
            break
        i += 1

    rel_list = [pardir] * (len(start_list)-i) + path_list[i:]
    if not rel_list:
        return curdir
    return join(*rel_list)

op.relpath = relpath

def getTemp(mkd = False, suffix = "", prefix = "tmp", directory = None):
    tmp = getattr(tempfile,
                  "mkdtemp" if mkd else "mkstemp")(suffix = suffix,
                                                             prefix = prefix,
                                                             dir = directory)
    if mkd: return tmp
    else:
        os.close(tmp[0])
        return tmp[1]

def mayaFile(path):
    '''
    @return True if the file ends with extensions else False
    '''
    extensions = [".ma",
                  ".mb"]
    try:
        path = path.lower()
    except BaseException as e :
        print "util.mayaFile"
        raise e
    for extension in extensions:
        if path.endswith(extension): return True
    return False

def getIndPathComps(path):
    '''
    @return: all the path components in a list seperately
    '''
    comps = []
    split = op.split(path)
    while split[1]:
        comps.insert(0, split[1])
        split = op.split(split[0])
    if split[0]:
        comps.insert(0, op.normpath(split[0]))
    return comps

def getPathComps(path):
    '''
    @returns the directory below path
    '''
    #path = op.abspath(path)
    pathComps = []
    pathComps.append(path)
    for path in (op.dirname(path) if path != op.dirname(path) else None for _ in path):
        if path:
            pathComps.append(path)
        else: break
    return pathComps

def randomNumber():
    return random.random()

def archive(file_dir, file_name, copy = False, alternatePath = ""):
    '''
    Move the file file_dir, filename to file_dir, .archive, filename, file_name_date_modified
    '''
    # TODO: determine of to archive component who also have
    if alternatePath:
        if not op.exists(alternatePath):
            raise WindowsError
        else:
            fpath = alternatePath
    else:
        fpath = file_dir
        
    if not haveWritePermission(fpath):
        warnings.warn('Access denied...')
        return

    if not file_name:
        warnings.warn('No file name specified...')
        return
    if not fpath:
        warnings.warn('No file path specified...')
        return

    try:
        dir_names = os.listdir(file_dir)
    except WindowsError:
        warnings.warn('Incorrect path, use / instead of \\ in the path...')
        return

    if file_name not in dir_names:
        print dir_names, file_name
        warnings.warn('File doesn\'t exist...')
        return

    archive = op.join(fpath ,'.archive')
    if '.archive' not in os.listdir(fpath):
        # make .archive directory in case it doesn't exists
        os.mkdir(archive)
    
    _dir = os.listdir(archive)

    # name of the directory which contains all the version of the file
    fileArchive = op.join(archive , file_name) 

    if file_name not in _dir:
        # if directory specific to the file doesn't exists, create one
        os.mkdir(fileArchive)

    fileToArchive = op.join(file_dir, file_name)
    
    # date the file was modified.
    date = str(datetime.datetime.fromtimestamp(op.getmtime(fileToArchive))).replace(':', '-').replace(' ','_')
    
    finalPath = op.join(fileArchive, date)

    if op.exists(finalPath):
        if os.listdir(finalPath):
            try:
                if op.getsize(fileToArchive) == op.getsize(op.join(finalPath, filter(lambda theFile: op.isfile(op.join(finalPath, theFile)), os.listdir(finalPath))[0])):
                    return op.join(finalPath, file_name) # redundant code
                else:
                    finalPath = getTemp(prefix = date + "_", mkd = True, directory = fileArchive)

            except BaseException as e:
                print e
    else:
        pass

    if not op.exists(finalPath):        
        os.mkdir(finalPath)
        
    #print op.join(file_dir, file_name), finalPath
    if copy: shutil.copy2(fileToArchive, finalPath)
    else: shutil.move(fileToArchive, finalPath)
    
    return op.join(finalPath, file_name)

def listdir(path, dirs = True):
    
    path = path if op.isdir(path) else op.dirname(path)
    return filter(lambda sibling: not (op.isdir(op.join(path, sibling)) ^ dirs), os.listdir(path))

def localPath(path, localDrives):
    try:
        return any((path.lower().find(local_drive) != -1
                    for local_drive in localDrives))
    except BaseException as e:
        print "localPath"
        raise e

def normpath(path):
    return op.abspath(op.normpath(str(path)))

def lowestConsecutiveUniqueFN(dirpath, basename, hasExt = True, key = op.exists):
    ext = ""
    if hasExt:
        basename, ext = tuple(op.splitext(basename))
    else:
        pass
    
    # make unique name
    if not key(op.join(dirpath, basename) + ext):
        basename += ext

    else:
        num = 1
        while(True):
            if key(op.join(dirpath,
                           basename
                           + "_"
                           + str(num)) + ext):
                num += 1
                continue
            else:
                
                basename = basename + "_" + str(num) + ext
                break

    return basename

lCUFN = lowestConsecutiveUniqueFN

def silentShellCall(command): 
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return subprocess.call(command, startupinfo=startupinfo)

def setReadOnly(path):
    if haveWritePermission(path if op.isdir(path) else op.dirname(path)):
        fileAtt = os.stat(path)[0]
        if (fileAtt & stat.S_IWRITE):
           os.chmod(path, stat.S_IREAD)
        else: pass
    else: pass

def purgeChar(string, pattern = r"\W", replace = ""):
    return re.sub(r"[%s]" %pattern, replace, str(string))

def haveWritePermission(path, sub = False):

    '''
    @return: True if the user has write permission in *path*
             else False
    '''
    path = normpath(path)
    try:
        os.remove(getTemp(directory = path))
        return True
    except OSError, WindowsError:
        if kwarg.get("sub"):
            count = 1
            # check if the user has write permissions in subsequent subdirs
            for fl, fds, fls in os.walk(path):
                if count > 50: break
                for fd in fds:
                    count += 1
                    try:
                        os.remove(getTemp(directory = op.join(fl, fd)))
                        return True
                    except OSError, WindowsError:
                        continue
            return False
        else:
            return False

def scrollRight(self):
   # Doesn't belong here
    if self.pathScrollArea.width() < self.pathWidget.width():
        w = self.pathWidget.width() - self.pathScrollArea.width()
        q = w/20
        if w%20 > 0:
            q += 1
        self.pathWidget.scroll(-20*q, 0)
        self.scrolled -= 20*q

def pathSplitter(path, drive = False):
    '''
    splits a path and returns list of dir names
    @params:
            path: a valid path to some file or dir
            drive: list should include drive name or not (bool)
    '''
    if ":" in path:
        path = (":" + op.sep).join(path.split(":"))
    nodes = op.normpath(path if path else op.sep).split(op.sep)
    return nodes if drive else nodes[1:]

def longest_common_substring(s1, s2):
    set1 = set(s1[begin:end] for (begin, end) in
               itertools.combinations(range(len(s1)+1), 2))
    set2 = set(s2[begin:end] for (begin, end) in
               itertools.combinations(range(len(s2)+1), 2))
    common = set1.intersection(set2)
    maximal = [com for com in common
               if sum((s.find(com) for s in common)) == -1 * (len(common)-1)]
    return [(s, s1.index(s), s2.index(s)) for s in maximal]

def getParentWindowPos(parent, child, QtCore):
    parentCenter = QtCore.QPoint(parent.width()/2, parent.height()/2)
    childCenter = QtCore.QPoint(child.width()/2, child.height()/2)
    return  parentCenter - childCenter

def getSequenceFiles(filepath):
    '''
    Get the sequence of files that are similar and exists in filename's
    directory. The sequence will be either negative or positive or both
    numerically increasing sequence.

    The function is a reverse engineered version of what Maya's file node
    uses for sequences.
    '''
    filename = normpath(filepath)
    dirname = op.dirname(filename)
    basename = op.basename(filename)
    filename, filext = op.splitext(basename)
    res = re.match(r'^(.*?)(\D)(-?\d*)$', filename)
    if not res:
        #Cannot be part of sequence of files
        return None
    # making match pattern for all the files in the sequence
    seqPattern = re.compile(('^' + ''.join(res.groups()[:-1]) +
                             '(-?)(\\d+)' + filext + '$').replace('.', '\\.'))
    #getting all the files from the directory and check whose names match the
    # sequence pattern
    return [normpath(os.path.join(dirname,dbn))
            for dbn in os.listdir(dirname)
            if seqPattern.match(dbn)]

def copyFilesTo(desPath, files = []):
    copiedTo = []
    if not op.exists(desPath) or not op.isdir(desPath):
        return copiedTo
    for fl in files:
        if op.isfile(fl) and op.exists(fl):
            desFile = op.join(desPath,
                              lCUFN(desPath,
                                    op.basename(fl), hasExt = True,
                                    key = op.exists))
            shutil.copy2(fl, desFile)
            copiedTo.append(desFile)
        else: return copiedTo
    return copiedTo

def lower(ls=[]):
    '''
    @ls: list of strings
    @return: all the string lowercased in the form of a generator
    '''
    try:
        return ((string.lower() for string in ls)
                if isinstance(ls, list)
                else (ls.lower()
                      if isinstance(ls, basestring) else ls))
    except BaseException as e:
        print e

def isDirInPath(dir, path):
    '''
    @return: True if the "dir" is in "path", else returns False
    '''
    dirs = pathSplitter(path)
    dirs = [str(x.lower()) for x in dirs]
    if str(dir.lower()) in dirs:
        return True
    else: return False
    
def gotoLocation(path):
    path = normpath(path)
    if os.name == 'nt':
       subprocess.Popen('explorer /select' + ',' + path)
    else:
       # http://askubuntu.com/q/23596/44293
       subprocess.Popen('xdg-open ' + path)

def getFileMDate(path):
    return str(datetime.datetime.fromtimestamp(op.getmtime(path))).split('.')[0]

def timestampToDateTime(timestamp):
    return str(datetime.datetime.fromtimestamp(timestamp)).split('.')[0]

def profile(sort='cumulative', lines=50, strip_dirs=False):
    """A decorator which profiles a callable.
    Example usage:

    >>> @profile
        def factorial(n):
            n = abs(int(n))
            if n < 1:
                    n = 1
            x = 1
            for i in range(1, n + 1):
                    x = i * x
            return x
    ...
    >>> factorial(5)
    Thu Jul 15 20:58:21 2010    /tmp/tmpIDejr5

             4 function calls in 0.000 CPU seconds

       Ordered by: internal time, call count

       ncalls  tottime  percall  cumtime  percall filename:lineno(function)
            1    0.000    0.000    0.000    0.000 profiler.py:120(factorial)
            1    0.000    0.000    0.000    0.000 {range}
            1    0.000    0.000    0.000    0.000 {abs}

    120
    >>>
    """
    def outer(fun):
        def inner(*args, **kwargs):
            file = tempfile.NamedTemporaryFile(delete=False)
            prof = cProfile.Profile()
            try:
                ret = prof.runcall(fun, *args, **kwargs)
            except:
                file.close()
                raise

            prof.print_stats()
            # stats = pstats.Stats(file.name)
            # if strip_dirs:
            #     stats.strip_dirs()
            # if isinstance(sort, (tuple, list)):
            #     stats.sort_stats(*sort)
            # else:
            #     stats.sort_stats(sort)
            # stats.print_stats(lines)

            return ret
        return inner

    # in case this is defined as "@profile" instead of "@profile()"
    if hasattr(sort, '__call__'):
        fun = sort
        sort = 'cumulative'
        outer = outer(fun)
    return outer

def getDirs(path):
    
   if path and op.exists(path):
        return os.listdir(path)

def timeMe(func):
    def wrapper(*args, **kwargs):
        t = time.time()
        result = func(*args, **kwargs)
        print time.time() - t
        return result
    return wrapper
@timeMe
def sha512OfFile(path):
    if not op.exists(path):
       raise Exception
    with open(path, "rb") as testFile:
        hash = hashlib.sha512()
        while True:
            piece = testFile.read(1024**3)
            if piece:
                hash.update(piece)
            else: 
                hex_hash = hash.hexdigest()
                break
    return hex_hash 

def clearList(lis):
    try:
       del lis[:]
    except:
       return False

if __name__ == "__main__":
   print __name__
