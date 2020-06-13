from typing import Union

#
#
#
class milestone_message():
    def __init__(self, id, args):
        self.id = id
        self.args = args
    
    def __repr__(self):
        return "<milestone_message id={} args={}>".format(self.id, repr(self.args))
    
    def bind(self, **args):
        args = {k:args[k] for k in self.args.keys()}
        return milestone_message(self.id, args)
    
    def __getattr__(self, name):
        return self.args[name]
    
    def __eq__(self, right):
        if isinstance(right, milestone_message):
            return self.id == right.id
        elif isinstance(right, int):
            return self.id == right
        return False

#
milestone_id = int
milestone_type = Union[milestone_id, milestone_message]

class milestone_auto_id:
    value = 1000

#
#
#
def milestone() -> milestone_id:
    milestone_auto_id.value += 1
    return milestone_auto_id.value

#
def milestone_msg(*argnames, id=None) -> milestone_message:
    if id is None:
        id = milestone()
    args = {name:None for name in argnames}
    return milestone_message(id, args)

        
"""        
from milestone import milestone

class progress():
    ALREADY_INSTALLED = milestone()
    DOWNLOADING = milestone_msg("size")
    PIP_INSTALLING = milestone()
    PRIVATE_REQUIREMENT = milestone_msg("name")
    NOT_INSTALLED = milestone()
    UNINSTALLING = milestone()
    PIP_UNINSTALLING = milestone()
    NO_UPDATE_NEEDED = milestone()
    PIP_UPDATING = milestone()

"""
    
    

