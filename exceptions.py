class ExportError(Exception):
    '''
    Maya asset export failed.
    '''
    def __init__(self, *arg, **kwarg):
        self.code = 0
        self.error = (
                "Export failed. Some error occured while exporting maya scene."
                )
        self.value = kwarg.get("obj", "")
        self.strerror = self.__str__()

    def __str__(self):
        return (self.value + ". " if self.value else "") + self.error


class ShaderApplicationError(Exception):
    '''
    Unable to apply shader.
    '''
    def __init__(self, *arg, **kwarg):
        self.code = 1
        self.error = "Unable to apply shader"
        self.strerror = self.__str__()

    def __str__(self):
        return "ShaderApplicationError: ", self.error

