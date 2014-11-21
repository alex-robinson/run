""" Main parameter class
"""
# from __future__ import absolute_import
from collections import OrderedDict as odict
import warnings
import copy
from itertools import groupby
from functools import wraps
from namelist import Namelist
# from models import climber2, sico, rembo, outletglacier

def _parse_value(v):
    try:
        return eval(v)
    except:
        return v

#
# Namelist
# 
def _to_str_nml(params):
    """ Write with namelist format
    """
    # convert to Namelist class
    groups = odict()
    for k, g in groupby(params, lambda x: x.group):
        if k == "":
            print list(g)
            raise ValueError("Group not defined. Cannot write to namelist. See Parameters' set_group() method.")
        groups[k] = odict([(p.name, p.value) for p in g])
    nml = Namelist(groups)
    string = nml.dump()
    return string

def _parse_file_nml(cls, string):
    nml = Namelist.parse_file(string)

    # flatten namelist to store it in the Parameters class
    params = cls()
    for g in nml.groups:
        for nm in nml.groups[g]:
            p = Parameter(name=nm, value=nml.groups[g][nm], group=g)
            params.append(p)
    return params

#
# Generic functions for Line-by-line format
#
def _to_str_linebyline_generic(params, param_to_line):
    string = "\n".join(param_to_line(p) for p in params)
    return string

def _parse_file_linebyline_generic(cls, string, line_parser, comment="#"):
    lines = string.split("\n")
    params = cls()
    for line in lines:
        if line == "" or line.startswith(comment):
            continue
        try:
            p = line_parser(line)
        except Exception as error:
            "Problem parsing line: "+line
            raise
        params.append(p)
    return params

#
# Alex format
# 
def _parse_line_alex(string):
    """ Parse one line and return a parameter instance for Alex format
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

def _parse_file_alex(cls, string):
    return _parse_file_linebyline_generic(cls, string, _parse_line_alex)

def _param_to_line_alex(param):
    if param.line:
        l = "{} {}".format(param.line,param.value)
    else:
        line = "{name} - {desc} ({units})".format(**param.__dict__)
        l = "{line:39} = {value}".format(line=line, value=param.value)
    return l

def _to_str_alex(params):
    return _to_str_linebyline_generic(params, _param_to_line_alex)


#
# Climber2 format
# 
def _parse_line_climber2(string):
    line  = string.partition("|")
    units = ""
    value = line[0].strip()
    line  = line[2].partition("|")
    name  = line[0].strip()
    
    line  = string.partition("|")
    line  = line[2].strip()
    value = _parse_value(value)

    return Parameter(name=name, line=line, value=value)

def _parse_file_climber2(cls, string):
    return _parse_file_linebyline_generic(cls, string, _parse_line_climber2, comment='=')

def _param_to_line_climber2(param):
    line = param.line or "{name} : {desc} ({units})".format(**param.__dict__)
    return " {:<9}| {}".format(repr(param.value),line)

def _to_str_climber2(params):
    return _to_str_linebyline_generic(params, _param_to_line_climber2)

#
# Parameter class
#

class Parameter(object):
    """ Contain infos for one parameter
    """
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
        return (self.group, self.name)

    def __eq__(self, other):
        return self.key == other.key

    def __hash__(self):
        " to convert into a set (or be used as dictionary key)"
        return hash(self.key)


class Parameters(list):
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
        >>> params.filter(group="basal")
        [P("basal","beta",2e4),P("basal","mode","constant")]
        """
        def test(p):
            for k in kwargs:
                if getattr(p, k) != kwargs[k]: 
                    return False
            return True
        return self.__class__(p for p in self if test(p))

    def item(self, **kwargs):
        """ same as filter, but return a single parameter (or raise error)
        >>> params.get(name="beta", group="basal")
        P("basal","beta",2e4)
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
        return [copy.copy(p) for p in self]

    def keys(self, key='key'):
        """ check all available values for a particular attribute
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

    def drop_duplicates(self):
        " "
        return list(self.to_dict().iteritems())

    #
    # setter/getter: convenience function, wrapper around item()
    #
    def set(self, name, value, **kwargs):
        " set value of one parameter, identified by its name and other attributes"
        self.item(name=name, **kwargs).value = value

    def set_group(self, newgroup, **kwargs):
        """ set 'group' attribute for all or a subset of parameters
        >>> params.set_group('somegroup')
        >>> params.set_group('somegroup', group="oldgroup")
        """
        for p in self.filter(**kwargs):
            p.group = newgroup

    def get(self, name, **kwargs):
        " get value of one parameter, identified by its name and other attributes"
        return self.item(name=name, **kwargs).value

    def __repr__(self):
        " display on screen "
        return self.__class__.__name__+"([\n"+ ",\n".join([4*" "+repr(p) for p in self] + ["])"])

    #
    # I / O
    #
    @staticmethod
    def _write_from_str(filename, file_str, verbose):
        " write a string to file "
        if not filename:
            # as an example, can indicate None or "" for filename 
            # ==> will simply output the string
            return file_str
        if verbose: print "Write params to {}".format(filename)
        with open(filename, "w") as f:
            f.write(file_str)

    @staticmethod
    def _read_to_str(filename, verbose):
        " read a file to string "
        if verbose: print "Read params from {}".format(filename)
        with open(filename) as f:
            file_str = f.read()
        return file_str

    @classmethod
    def read_nml(cls, filename, verbose=True):
        file_str = cls._read_to_str(filename, verbose=verbose)
        return _parse_file_nml(cls, file_str)

    def write_nml(self, filename, verbose=True):
        file_str = _to_str_nml(self)
        return self._write_from_str(filename, file_str, verbose)

    @classmethod
    def read_alex(cls, filename, verbose=True):
        file_str = cls._read_to_str(filename, verbose=verbose)
        return _parse_file_alex(cls, file_str)

    def write_alex(self, filename, verbose=True):
        file_str = _to_str_alex(self)
        return self._write_from_str(filename, file_str, verbose)

    @classmethod
    def read_climber2(cls, filename, verbose=True):
        file_str = cls._read_to_str(filename, verbose=verbose)
        return _parse_file_climber2(cls, file_str)

    def write_climber2(self, filename, verbose=True):
        file_str = _to_str_climber2(self)
        return self._write_from_str(filename, file_str, verbose)
 
if __name__ == "__main__":
    print "Test read namelist"
    params1 = Parameters.read_alex("examples/options_rembo")
    params2 = Parameters.read_climber2("examples/run")
    params3 = Parameters.read_nml("examples/params.nml")

    print "In-memory representation"
    print ""
    print params1
    print ""
    print params2
    print ""
    print params3

    print "Display string to file"
    print ""
    print params1.write_alex(filename=None)
    print ""
    print params2.write_climber2(filename=None)
    print ""
    # print params2.write_nml(filename=None)
    print params3.write_nml(filename=None)

    print "Actual writing to file"
    print ""
    print params1.write_alex(filename="alex.tmp")
    print params2.write_climber2(filename="climber2.tmp")
    print params3.write_nml(filename="nml.tmp")


    print ""
    print "Namelist to Alex"
    print ""
    print params3.write_nml(filename=None)

    print ""
    print "Alex to Namelist"
    print ""
    # param1 = param1.copy() # avoid in-place modif
    params1.set_group("sico")
    params1.write_nml(filename=None)

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
    print params4.write_nml(filename=None)
