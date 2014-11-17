""" Main parameter class
"""
from collections import OrderedDict as odict
from itertools import groupby
# from models import climber2, sico, rembo, outletglacier

class AbstactParameter(object):
    """ Contain infos for one parameter ==> to be subclassed

    Useful methods:
    - parse_line
    - convert 
    - __str__ 
    """
    def __init__(self,name="",value="",units="", desc="", line="", group=""):
        self.name = name
        self.value = value
        self.units = units
        self.desc = desc 
        self.line = line  # the fixed part of the line, all but the valueone
        self.group = group # namelist group

    def __str__(self):
        " useful for a parameter file "
        raise NotImplementedError("need to be subclassed")

    def convert(self, newcls):
        " convert to another type of parameter format "
        attrs = ["name", "units", "values", "descr"]
        return newcls(**{nm:getattr(self, nm) for nm in attrs})

    def short(self):
        '''Output short string representation of parameter and value.
           Used for automatic folder name generation.'''
           
        # Store the param value as a string
        # Remove the plus sign in front of exponent
        # Remove directory slashes, periods and trailing .nc from string values
        value = "%s" % (self.value)                
        if "+" in value: value = value.replace('+','')  
        
        if "/" in value: value = value.replace('/','')
        if ".." in value: value = value.replace('..','')
        if ".nc" in value: value = value.replace('.nc','')
        
        # Remove all vowels and underscores from parameter name
        name = self.name
        for letter in ['a','e','i','o','u','A','E','I','O','U','_']:
            name = name[0] + name[1:].replace(letter, '')
        
        return ".".join([name,value])
        
    def __repr__(self):
        " informative representation, in prompt"
        return "{cls}({group},{name},{value})".format(cls=self.__class__, **self.__dict__)

    # def __str__(self):
    #     '''Output a string suitable for parameter file'''
    #     return "{module} : {name} = {value}".format(module=self.module, **self.__dict__)

    @property
    def module(self): 
        # can be overwritten in sub-classes
        return self.__class__.__name__.lower()

    @property
    def key(self):
        " unique ID "
        return (self.module, self.group, self.name)

    def __eq__(self, other):
        return self.key == other.key

    def __hash__(self):
        " to convert into a set or dictionary"
        return hash(self.key)


    @classmethod
    def read(cls, filename):
        """ read a list parameters and returns a Parameters class
        """
        raise NotImplementedError("need to be subclassed")

    @classmethod
    def parse_line(cls, string):
        raise NotImplementedError("need to be subclassed")


#
# model-specific parameters
#
class AlexParam(AbstactParameter):
    " Common format for Rembo and Sicopolis "

    @classmethod
    def parse_line(cls, string):
        line  = string.partition(":")
        units = line[0].strip()
        sep = "="
        if ":" in line[2]: sep = ":"
        line  = line[2].partition(sep)
        name  = line[0].strip()
        value = line[2].strip()
        
        # Also save the initial part of the line for re-writing
        line = string[0:41]

        return {'name':mame, 'value':value, 'units':units, 'line':line, 'desc':""}

    def __str__(self):
        '''Output a string suitable for parameter file'''

        if self.line:
            return "{} {}".format(self.line,self.value)
        else:
            line = "{name} - {desc} ({units})".format(**self.__dict__)
            return "{line:39} = {value}".format(line, **self.__dict__)

    @classmethod
    def read(cls, filename):
        # Load all parameters from the input file
        try:
            lines = open(filename,'r').readlines()
        except:
            print "File could not be opened: "+filename+'\n'
            raise
   
        # Loop to find parameters and load them into class
        if self.file in ("options_rembo","options_sico"):
            
            # Loop through lines and determine which parts correspond to
            # parameters, store these parts in self.all
            for line in self.lines:    
                first = ""
                if len(line) > 41: first = line.strip()[0]
                if not first == "" and not first == comment and line[40] in ("=",":"):
                    X = parameter(string=line)
                    self.all.append(X)

        return Parameters(cls._read_file(filename))

class SicoParam(AlexParam):
    module = "sico"

class RemboParam(AlexParam):
    module = "rembo"

class Climber2(AbstactParameter):
    " read CLIMBER2-type parameters"
    module = "climber2"

    @classmethod
    def parse_line(cls, string):

        line  = string.partition("|")
        units = ""
        value = line[0].strip()
        line  = line[2].partition("|")
        name  = line[0].strip()
        
        line  = string.partition("|")
        line  = line[2].strip()

        return {'name':mame, 'line':line, 'value':value, 'units':units}

    def __str__(self):
        line = self.line or "{name} : {desc} ({units})".format(**self.__dict__)
        return " {:<9}| {}".format(self.value,line)

        else:  # climber option file 'run'
            
            # Loop through lines and determine which parts correspond to
            # parameters, store these parts in self.all
            for line in self.lines:     
                first = line.strip()[0]
                if not first == "" and not first == "=":
                    X = parameter(string=line,module="climber")
                    self.all.append(X)


#
# Which container type for the parameters?
# - requirements/preferences: 
#   - keep order of the parameter in each group
#   - allows but does not require a specific tree structure (e.g. module=>group=>name)
#   - does not duplicate the key info and the content of a parameter (e.g. pb with dict)
#   - does not let two "same" parameters coexist (e.g. cool with dict, pb with list)
#   - easily access individual elements
#   - performance not essential
#
# - OrderedDict : redundancy with key (would need to introduce special checks during insertion)
# - set : cool, but looses order
# - list : many cool functions to organize data, but risk of duplicating params
# 
# Ideally, an ordered set would be just what we need, but does not exist as built-in
# See e.g. https://github.com/LuminosoInsight/ordered-set/blob/master/ordered_set.py
#
# A list seems a reasonable tradeoff, with additional checks on insertion

class AbstractParameters(list):
    """ The data structure of a parameter list. 

    It contains various method to explore the data.
    It reilies on the "key" attribute of the contained Param class,
    which identifies one parameter uniquely, on which __eq__ is based,
    and therefore the list.index() function can be called on a parameter

    Additional methods shipped with list:
    - append : append new element
    - extends : extend with another list
    - sort : in-place sort (can be provided with a key function)
    """
    def filter(self, **kwargs):
        """ filter parameters by any parameter attribute, returns a sub-list 
        >>> params.filter(group="basal", module="outletglacier")
        [OutletGlacierParam("basal","beta",2e4), OutletGlacierParam("basal","mode","constant")]
        """
        def test(p):
            for k in kwargs:
                if getattr(p, k) != kwargs[k]: 
                    return False
            return True
        return self.__class__(p for p in self if test(p))

    def item(self, **kwargs):
        """ same as filter, but return a single parameter (or raise error)
        >>> params.get(name="beta", group="basal", module="outletglacier")
        OutletGlacierParam("basal","beta",2e4)
        """
        r = self.filter(**kwargs)
        assert len(r) == 1, "{} match(es) for {}".format(len(r), kwargs)
        return r[0]

    def update(self, params, verbose=True):
        """ update parameter list with another parameter list (in-place operation)
        relies on the __eq__ method of the contained Params class

        Note: use self.update([p]) to add a single parameter
        """
        for p in params:
            # replace if element already exists
            try:
                i = self.index(p)
                if verbose: 
                    print "{}: {} ==> {}".format(p.key, self[i].value, p.value)
                self[i] = p  # update existing parameter
            # otherwise just append 
            except:
                self.append(p)

    def copy(self):
        " copy the container, not the contained object (`p.value` 3 will affect both lists)"
        return [p for p in self]

    def keys(self, key='key'):
        """ check the keys present in the parameter 
        >>> params.keys('group')
        ['submelt', 'dynamic', 'calving']
        """
        return self.to_dict(key).keys()

    def to_dict(self, key='key'):
        " return an ordered dict (automatically drop duplicates w.r.t the key !)"
        return odict([(getattr(p, key),p) for p in self])

    def has_duplicates(self):
        " return True if all element have distinct keys"
        return len(set(self)) != len(self) # set uses __hash__ to remove duplicates

    # function below sort the parameters ...
    def drop_duplicates(self, keep=-1, item=None, key='key'):
        " drop duplicates, using keep as an index (e.g. 0 or -1)"
         item = item or lambda params : params[keep] # function must return one item from a list
         return self.__class__(item(list(g)) for k, g groupby(sorted(self, key), key))

    # def groupby(self, key='module'):
    #     """ useful to group by module, or/and by group
    #     check that self.has_duplicates() is False beforehand
    #
    #     Returns and an imbricated structure of Ordered dictionaries
    #     """
    #     res = odict() 
    #     for k in (key,) + keys:
    #         params = params.filter(k)
    #
    #     return groupby(self, lambda p:getattr(p, key))

class Parameters(AbstractParameters):
    """ This class contains more specific utilities to file I/O and so on.

    Split from AbstractParameters for no good reason except maybe elegance...
    """
    #
    # setter/getter: convenience function, wrapper around item()
    #
    def set(self, name, value, **kwargs):
        " set value of one parameter, identified by its name and other attributes"
        self.item(name=name, **kwargs).value = value

    def get(self, name, **kwargs):
        " get value of one parameter, identified by its name and other attributes"
        return self.item(name=name, **kwargs).value
