""" Main parameter class
"""
# from __future__ import absolute_import
from collections import OrderedDict as odict
from itertools import groupby
from namelist import Namelist
# from models import climber2, sico, rembo, outletglacier

def _parse_value(v):
    try:
        return eval(v)
    except:
        return v

class Parameter(object):
    """ Contain infos for one parameter ==> to be subclassed

    Useful methods:
    - loads, dumps
    - read, write
    - convert 
    - __str__ 
    """
    module = None

    def __init__(self,name="",value="",units="", desc="", line="", group=""):
        self.name = name
        self.value = value
        self.units = units
        self.group = group # namelist group
        self.desc = desc 
        self.line = line  # the fixed part of the line, all but the valueone

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
        # return "{cls}({group},{name},{value})".format(cls=self.__class__.__name__, **self.__dict__)
        # return "P({group},{name},{value})".format(**self.__dict__)
        return "P(%r, %r, %r)" % (self.group, self.name, self.value)

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

    It is design to contain many types of parameters, even though in practice
    we will have to do mostly with homogeneous parameter types (e.g. distinct 
    parameter sets for Climber2, Sico and so on). If so, the class could be 
    thinned down a bit. Anyway, a flat list of parameter, whatever the grouping, 
    seems a good idea. It is always easy, later to use groupby or the like.

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
        [Parameter("basal","beta",2e4),Parameter("basal","mode","constant")]
        """
        def test(p):
            for k in kwargs:
                if getattr(p, k) != kwargs[k]: 
                    return False
            return True
        return self.__class__(p for p in self if test(p))

    # def filter_by_cls(self, paramcls):
    #     " return a list of parameters with instance from a same class "
    #     return self.__class__(p for p in self if isinstance(p, paramcls))
    #
    def item(self, **kwargs):
        """ same as filter, but return a single parameter (or raise error)
        >>> params.get(name="beta", group="basal", module="outletglacier")
        Parameter("basal","beta",2e4)
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
        for val, g in groupby(self, lambda x:getattr(x,key)): # iterator
            if val not in groups:
                groups[val] = self.__class__(g)
            else:
                groups[val].extends(list(g))

        # descend further? recursive call to groupby
        if len(keys) > 0:
            for val in groups:
                groups[val] = groups[val].groupby(keys[0], *keys[1:])

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

    def __repr__(self):
        " display on screen "
        return self.__class__.__name__+"([\n"+ ",\n".join([4*" "+repr(p) for p in self] + ["])"])

    #
    # The two following read / write method actually handle the I/O of 
    # a list of parameters, not a single parameter (which does not make sense)
    # even though the class stores information for a single parameter.
    # This are not proper methods, but it is convenient to have them tied to the 
    # class.
    #
    @classmethod
    def read(cls, filename, verbose=True):
        """ read a list parameters and returns a Parameters class
        """
        if verbose:
            print "Read {} params from {}".format(cls.__name__,filename)
        with open(filename) as f:
            string = f.read()
        return cls.loads(string)

    @classmethod
    def write(cls, filename, params, verbose=True):
        """ Write a list of parameters of the same group to file
        """
        string = cls.dumps(params)
        if verbose:
            print "Write {} params to {}".format(cls.__name__, filename)
        with open(filename, "w") as f:
            f.write(string)

    @classmethod
    def loads(cls, string):
        """ parse a parameters file (as string) and returns a Parameters class
        """
        raise NotImplementedError("need to be subclassed")

    @classmethod
    def dumps(cls, params):
        """ Convert a list of parameters of the same group to file, for writing
        returns : string
        """
        raise NotImplementedError("need to be subclassed")

class AbstractLineWise(AbstractParameters):
    """ a class to handle line-by-line parameter files (i.e. no namelists)
    """
    comment = "#"

    @staticmethod
    def parse_line(string):
        " parse a line and return an instance of that parameter "
        raise NotImplementedError("need to be subclassed")

    @staticmethod
    def to_line(self, param):
        " return a line-string represention of one paramater"
        raise NotImplementedError("need to be subclassed")

    def dumps(self):
        """ Convert a list of parameters of the same group to file, for writing
        returns : string
        """
        return "\n".join( [self.to_line(p) for p in self] )

#
# model-specific parameters
#
class AlexParams(AbstractLineWise):
    " Common format for Rembo and Sicopolis "

    @staticmethod
    def parse_line(string):
        """ Parse one line and return a parameter instance
        """
        # NOTE: could be transformed as a class method
        # to pass the Parameter instance some model-specific
        # information, e.g. "module" or even the container class
        # it belongs to (cls). Not needed for now.
        line  = string.partition(":")
        units = line[0].strip()
        sep = "="
        if ":" in line[2]: sep = ":"
        line  = line[2].partition(sep)
        name  = line[0].strip()
        value = line[2].strip()
        value = _parse_value(value)
        
        # Also save the initial part of the line for re-writing
        line = string[0:41]
        return Parameter(name=name, value=value, units=units, line=line) 

    @staticmethod
    def to_line(param):
        '''Output a string suitable for parameter file'''
        # no string markers "" needed here
        if param.line:
            return "{} {}".format(param.line,param.value)
        else:
            line = "{name} - {desc} ({units})".format(**param.__dict__)
            return "{line:39} = {value}".format(line=line, value=param.value)

    @classmethod
    def loads(cls, string):
        """ Read a file of parameters and returns a Parameters instance
        """
        # Loop to find parameters and load them into class
        lines = string.split("\n")
        params = cls()  # this class, to have the appropriate dumps / loads methods
        for line in lines:
            first = ""
            if len(line) > 41: first = line.strip()[0]
            if not first == "" and not first == cls.comment and line[40] in ("=",":"):
                p = cls.parse_line(line)
                params.append(p)
        return params


class Climber2Params(AbstractLineWise):
    " read CLIMBER2-type parameters"
    module = "climber2"

    @staticmethod
    def parse_line(string):

        line  = string.partition("|")
        units = ""
        value = line[0].strip()
        line  = line[2].partition("|")
        name  = line[0].strip()
        
        line  = string.partition("|")
        line  = line[2].strip()

        value = _parse_value(value)

        return Parameter(name=name, line=line, value=value)

    @staticmethod
    def to_line(param):
        # string marker needed, therefore repr()
        line = param.line or "{name} : {desc} ({units})".format(**param.__dict__)
        return " {:<9}| {}".format(repr(param.value),line)

    @classmethod
    def loads(cls, string):
        """ Read CLIMBER-2 parameter config and returns a Parameters instance
        """ 
        lines = string.split("\n")
        params = cls()
        for line in lines:
            if line.strip() == "": continue
            first = line.strip()[0]
            if not first == "" and not first == "=":
                p = cls.parse_line(line.strip())
                params.append(p)
        return params

class NamelistParams(AbstractParameters):

    @classmethod
    def loads(cls, input_str):
        nml = Namelist.parse_file(input_str)

        # flatten namelist to store it in the Parameters class
        params = cls()
        for g in nml.groups:
            for nm in nml.groups[g]:
                p = Parameter(name=nm, value=nml.groups[g][nm], group=g)
                params.append(p)
        return params

    def dumps(self):
        # convert back to Namelist class (with groups and so)
        nml = self.to_nml()
        return nml.dump()

    def to_nml(self):
        " convert a list of Parameters to Namelist class "
        groups = odict()
        for k, g in groupby(self, lambda x: x.group):
            groups[k] = odict([(p.name, p.value) for p in g])
        return Namelist(groups)
 
if __name__ == "__main__":
    print "Test read namelist"
    params1 = AlexParams.read("examples/options_rembo")
    params2 = Climber2Params.read("examples/run")
    params3 = NamelistParams.read("examples/params.nml")

    print "In-memory representation"
    print ""
    print params1
    print ""
    print params2
    print ""
    print params3


    print "Dumped-string, write-ready"
    print ""
    print params1.dumps()
    print ""
    print params2.dumps()
    print ""
    print params3.dumps()

    print " "
    print "Test access parameter"
    print "Rembo:"
    print "domain=", repr(params1.get('domain'))
    print ""
    print "CLIMBER2:"
    print "NYRMX=", repr(params2.get('NYRMX'))
    print ""
    print "OutletGlacier:"
    print "beta=", repr(params3.get('beta'))
    print "&smb mode=", repr(params3.get('mode', group='smb'))
    print "&submelt mode=", repr(params3.get('mode', group='submelt'))

    print " "
    print "Test modify parameter"
    print "set beta to 40000"
    print " "
    params3.set('beta', 40000, group='dynamics')
    params4 = params3.filter(group='dynamics')
    print params4.dumps()
