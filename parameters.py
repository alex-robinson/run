""" Main parameter class
"""
# from __future__ import absolute_import
from collections import OrderedDict as odict
from itertools import groupby
from namelist import Namelist
# from models import climber2, sico, rembo, outletglacier

class AbstactParameter(object):
    """ Contain infos for one parameter ==> to be subclassed

    Useful methods:
    - read
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
        return "{cls}({group},{name},{value})".format(cls=self.__class__.__name__, **self.__dict__)

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

    #
    # The two following read / write method actually handle the I/O of 
    # a list of parameters, not a single parameter (which does not make sense)
    # even though the class stores information for a single parameter.
    # This are not proper methods, but it is convenient to have them tied to the 
    # class.
    #
    @classmethod
    def read(cls, filename):
        """ read a list parameters and returns a Parameters class
        """
        raise NotImplementedError("need to be subclassed")

    @staticmethod
    def write(filename, params):
        """ Write a list of parameters of the same group to file
        """
        raise NotImplementedError("need to be subclassed")

#
# model-specific parameters
#
class AlexParam(AbstactParameter):
    " Common format for Rembo and Sicopolis "

    @classmethod
    def parse_line(cls, string):
        """ Parse one line and return a parameter instance
        """
        line  = string.partition(":")
        units = line[0].strip()
        sep = "="
        if ":" in line[2]: sep = ":"
        line  = line[2].partition(sep)
        name  = line[0].strip()
        value = line[2].strip()
        
        # Also save the initial part of the line for re-writing
        line = string[0:41]
        return cls(name=name, value=value, units=units, line=line)

    def __str__(self):
        '''Output a string suitable for parameter file'''

        if self.line:
            return "{} {}".format(self.line,self.value)
        else:
            line = "{name} - {desc} ({units})".format(**self.__dict__)
            return "{line:39} = {value}".format(line, **self.__dict__)

    @classmethod
    def read(cls, filename):
        """ Read a file of parameters and returns a Parameters instance
        """
        # Load all parameters from the input file
        try:
            lines = open(filename,'r').readlines()
        except:
            print "File could not be opened: "+filename+'\n'
            raise

        # Loop to find parameters and load them into class
        comment = "#"
        params = Parameters()
        for line in lines:
            first = ""
            if len(line) > 41: first = line.strip()[0]
            if not first == "" and not first == comment and line[40] in ("=",":"):
                p = cls.parse_line(line)
                params.append(p)
        return params

class SicoParam(AlexParam):
    module = "sico"

class RemboParam(AlexParam):
    module = "rembo"

class Climber2Param(AbstactParameter):
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

        return cls(name=name, line=line, value=value)

    def __str__(self):
        line = self.line or "{name} : {desc} ({units})".format(**self.__dict__)
        return " {:<9}| {}".format(self.value,line)

    @classmethod
    def read(cls, filename):
        """ Read CLIMBER-2 parameter config and returns a Parameters instance
        """ 
        try:
            lines = open(filename,'r').readlines()
        except:
            print "File could not be opened: "+filename+'\n'
            raise
        params = Parameters()
        for line in lines:
            first = line.strip()[0]
            if not first == "" and not first == "=":
                p = cls.parse_line(line.strip())
                params.append(p)
        return params

    @classmethod
    def write(cls, filename, params):
        lines = [str(p) for p in params]
        with open(filename, 'w') as f:
            f.write("\n".join(lines))

class NamelistParam(AbstactParameter):

    @classmethod
    def read(cls, filename):
        with open(filename, 'r') as f:
            input_str = f.read()
        nml = Namelist.parse_file(input_str)

        # flatten namelist to store it in the Parameters class
        params = Parameters()
        for g in nml.groups:
            for nm in nml.groups[g]:
                p = cls(name=nm, value=nml.groups[g][nm], group=g)
                params.append(p)
        return params

    @classmethod
    def write(cls, filename, params):
        # convert back to Namelist class (with groups and so)
        nml = cls.to_nml(params)
        print "Write namelist to", filename
        with open(filename, 'w') as f:
            f.write(nml)

    @classmethod
    def to_nml(cls, params):
        " convert a list of Parameters to Namelist class "
        groups = params.groupby('group', 'name') # 2nd degree ordered dict of Params
        return Namelist(groups)

class OutletGlacierParam(NamelistParam):
    module = "outletglacier"

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

class Parameters(list):
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
        " return True if all elements have distinct keys"
        return len(set(self)) != len(self) # set uses __hash__ to remove duplicates

    def drop_duplicates(self, keep=-1, item=None):
        """ drop duplicates, by default keep the last inserted parameter
        """
        item = item or (lambda params : params[keep]) # function must return one item from a list
        groups = self.groupby('key')
        for k in groups:
            groups[k] = item(groups[k])
        return self.__class__(groups.values()) # only keep the values

    def groupby(self, key, *keys):
        """ return nested ordered dict of Parameters

        >>> params.groupby('module')
        OrderedDict([('climber2', Params(...)), ('rembo',Params(...)), ...])

        Adding more keys increases the depth of the grouping
        """
        # group all by the first key
        groups = odict()
        for val, g in groupby(self, key): # iterator
            if val not in groups:
                groups[val] = self.__class__(g)
            else:
                groups[val].extends(list(g))

        # descend further? recursive call to groupby
        if len(keys) > 0:
            for val in groups:
                groups[val] = groups[val].groupby(keys[0], **keys[1:])

        return groups

    #
    # setter/getter: convenience function, wrapper around item()
    #
    def set(self, name, value, **kwargs):
        " set value of one parameter, identified by its name and other attributes"
        self.item(name=name, **kwargs).value = value

    def get(self, name, **kwargs):
        " get value of one parameter, identified by its name and other attributes"
        return self.item(name=name, **kwargs).value

    #
    # I / O
    #
    @staticmethod
    def read(filename, paramcls):
        return paramcls.read(filename)

    def write(self, filename, paramcls):
        params = [p for p in self if isinstance(p, paramcls)]
        paramcls.write(filename, params)

    def __repr__(self):
        " display on screen "
        lines = ["Parameters("] + ["\t"+repr(p) for p in self] + [")"]
        return "\n".join(lines)

if __name__ == "__main__":
    print "Test read namelist"
    params1 = RemboParam.read("examples/options_rembo")
    params2 = Climber2Param.read("examples/run")
    params3 = OutletGlacierParam.read("examples/params.nml")

    print ""
    print params1
    print ""
    print params2
    print ""
    print params3
