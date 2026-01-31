#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
#                    Author: Florent TOURNOIS | License: MIT                   
# =============================================================================


import logging
import sys
import os
import os.path
import yaml
import pandas as pd
import codecs
import collections
from copy import deepcopy
import win32com.client as win32
from jinja2 import Template
import re

import pymdtools.common as common
import pymdtools.instruction as mdinst
from pymdtools import mistunege as mistune

from . import genenv
from . import renderer

# -----------------------------------------------------------------------------
# The filename of the default configuration
# -----------------------------------------------------------------------------
__DEFAULT_CONF_FILENAME__ = "default.conf"

# -----------------------------------------------------------------------------
# The filename of the default configuration
# -----------------------------------------------------------------------------
__EXT_FILENAME__ = ".conf"

# -----------------------------------------------------------------------------
__cid_re__ = \
    r"src=['\"]cid:(?P<name>[\.a-zA-Z0-9_-]+)['\"]"

###############################################################################
# Recursive dict merge. Inspired by :meth:``dict.update()``, instead of
# updating only top-level keys, dict_merge recurses down into dicts nested
# to an arbitrary depth, updating keys. The ``merge_dct`` is merged into
# ``dct``.
#
# This version will return a copy of the dictionary and leave the original
#     arguments untouched.
#
# The optional argument ``add_keys``, determines whether keys which are
#     present in ``merge_dict`` but not ``dct`` should be included in the
#     new dict.
#
#
# Code from https://gist.github.com/angstwad/bf22d1822c38a92ec0a9
#
# Args:
#         dct (dict) onto which the merge is executed
#         merge_dct (dict): dct merged into dct
#         add_keys (bool): whether to add new keys
#
# Returns:
#         dict: updated dict
###############################################################################
def __dict_merge(dct, merge_dct, add_keys=True):
    dct = deepcopy(dct)

    if not add_keys:
        merge_dct = {
            k: merge_dct[k]
            for k in set(dct).intersection(set(merge_dct))
        }

    for k, value in merge_dct.items():
        if isinstance(dct.get(k), dict) \
           and isinstance(value, collections.Mapping):
            dct[k] = __dict_merge(dct[k], value, add_keys=add_keys)
        elif isinstance(dct.get(k), list) \
                and isinstance(value, list):
            dct[k].extend(value)
        else:
            dct[k] = value
    return dct


###############################################################################
# Compute an absolute path from the config parameter
#
# @param paths list of paths to compute
# @return the absolute path
###############################################################################
def path(*paths):
    result = ""
    for path_element in paths:
        if len(result) > 0:
            result = os.path.join(path_element, result)
        else:
            result = path_element
        if os.path.isabs(result):
            return os.path.normpath(common.set_correct_path(result))

    return os.path.normpath(common.set_correct_path(result))

###############################################################################
# Expand paths in the config file
#
# @param data the config part
# @param root the root of the config part
# @return the dict of the config
###############################################################################
def expand_paths(data, root):
    if 'root' not in data:
        data['root'] = './'

    # Set the root path absolute
    data['root'] = path(data['root'], root)

    for key in data:
        if isinstance(data[key], dict):
            data[key] = expand_paths(data[key], data['root'])
        elif isinstance(data[key], list):
            new_list = []
            for element in data[key]:
                new_list.append(path(element, data['root'], root))
            data[key] = new_list
        else:
            data[key] = path(data[key], data['root'], root)

    return data

###############################################################################
# Read conf yaml
#
# @param filename the config filename
# @return the dict of the config
###############################################################################
def __read_yaml(filename):
    logging.debug('Read the yaml config file %s', (filename))
    filename = common.check_is_file_and_correct_path(filename)
    filename_path = os.path.dirname(filename)
    with codecs.open(filename, "r", "utf-8") as ymlfile:
        result = yaml.load(ymlfile, Loader=yaml.FullLoader)

    logging.debug('Read finished for the yaml config file %s', (filename))

    if 'paths' not in result:
        return result

    includes_full = []
    if 'paths' in result and 'includes' in result['paths']:
        for inc_fn in result['paths']['includes']:
            inc_fn_full = os.path.join(filename_path, inc_fn)
            includes_full.append(inc_fn_full)
            with codecs.open(inc_fn_full, "r", "utf-8") as ymlfile:
                include_conf = yaml.load(ymlfile, Loader=yaml.FullLoader)
            result = __dict_merge(include_conf, result, add_keys=True)

    result['paths']['includes'] = includes_full

    logging.debug('Add some info in the config result for all paths')

    if 'base_search' not in result['paths']:
        result['paths']['base_search']=[os.path.split(filename)[0], './']

    result['paths'] = expand_paths(result['paths'],
                                   os.path.split(filename)[0])

    if 'conf_folder' not in result['paths']:
        result['paths']['conf_folder'] = os.path.split(filename)[0]
    if 'conf_filename' not in result['paths']:
        result['paths']['conf_filename'] = filename
    

    return result

###############################################################################
# Read conf yaml
#
# @param filename the config filename
# @return the dict of the config
###############################################################################
def read_yaml(filename):
    logging.debug('Read the yaml config file %s', (filename))
    filename = common.check_is_file_and_correct_path(filename)
    result = __read_yaml(filename)

    (folder, loc_filename) = os.path.split(filename)
    (loc_filename, filename_ext) = os.path.splitext(loc_filename)

    local_filename = os.path.join(
        folder, loc_filename) + ".local" + filename_ext
    logging.debug("local_filename = %s", local_filename)

    if not os.path.isfile(local_filename):
        return result

    logging.debug('Read the yaml local config file %s', (local_filename))
    local_conf = __read_yaml(local_filename)
    result = __dict_merge(result, local_conf)

    return result

# -----------------------------------------------------------------------------
def load_conf(filename, folder = "./"):
    "Read a conf file and return the dict"
    logging.debug('Load the configuration file: %s', filename)
    run_folder = os.getcwd()
    filename=common.search_for_file(filename,
                                    [run_folder, folder],['./','conf'],2)
    result = {}

    filename = os.path.abspath(filename)
    if not os.path.isfile(filename):
        logging.info('The configuration file does not exists.')
        logging.info('The configuration filename is %s', filename)
        return result

    result = read_yaml(filename)

    return result

# -----------------------------------------------------------------------------
def compute_conf(conf, cmd_line_args=None):
    conf = read_excel_list(conf)
    if 'email' in conf:
        if 'content' not in conf['email']:
            conf['email']['content']={}
        if 'filename'  not in conf['email']['content']:
            md_filename = cmd_line_args.conf_filename
            md_filename = common.filename_ext_to_md(md_filename)
            conf['email']['content']['filename'] = md_filename
            logging.info('Content filename: %s', md_filename)

    conf = read_content_filename(conf)

    if cmd_line_args is not None:
        if cmd_line_args.send_mail != "conf":
            conf['really_send']= (cmd_line_args.send_mail=="yes")
            logging.info('The command line override the conf parameter '
                         'Send_mail = %s', repr(conf['really_send']))

    env = genenv.GenerationEnvironment(conf)
    conf = txt2html(conf, env)
    conf = htmlbody(conf, env)
    return conf

# -----------------------------------------------------------------------------
def default_conf():
    " Read default conf "
    logging.debug('Load the default configuration.')
    filename = os.path.join(__get_this_folder(), __DEFAULT_CONF_FILENAME__)
    return load_conf(filename)

# -----------------------------------------------------------------------------
def email_excel_list(xl_filename, xl_column, folders = ['./']):
    "Read excel column email list"
    logging.info("Read excel file '%s' column '%s'",xl_filename, xl_column)
    result=[]
    filename=common.search_for_file(xl_filename,
                                    folders,
                                    [os.getcwd(),'./','excel','xl'],2)
    xl_list = pd.read_excel(filename)

    columns = []
    if isinstance(xl_column,str):
        columns.append(xl_column)
    if isinstance(xl_column,list):
        columns.extend(xl_column)
    
    for col in columns:
        if col in xl_list:
            for key in xl_list[col]:
                if isinstance(key, str) and '@' in key:
                    result.append(key.lower())
        logging.info("columns=%20s > number of email=%03d", col, len(result))

    count = len(result)
    result = list(dict.fromkeys(result))
    if count != len(result):
        logging.info("    > Only %d unique", len(result))
    return result

# -----------------------------------------------------------------------------
def read_excel_list(conf):
    " read all excel file"
    for key in conf:
        if (isinstance(conf[key], dict)) and \
            ("excel_file" in conf[key]) and \
            ("excel_column_name" in conf[key]):
            emails = email_excel_list(conf[key]["excel_file"],
                                      conf[key]["excel_column_name"],
                                      conf['paths']['base_search'])
            if ('list' not in conf[key]) or \
                (not isinstance(conf[key]['list'], list)):
                conf[key]['list']=[]
            new_list = []
            for x in conf[key]['list']:
                if isinstance(x, str) and '@' in key:
                    new_list.append(x.lower())
            conf[key]['list']=new_list
            conf[key]['list'].extend(emails)
            del conf[key]["excel_file"]
            del conf[key]["excel_column_name"]
    return conf

# -----------------------------------------------------------------------------
def read_content_filename(conf):
    " read all content filename"
    for key in conf:
        if (isinstance(conf[key], dict)) and \
            ("content" in conf[key]) and \
            ("filename" in conf[key]["content"]):
            object = conf[key]["content"]
            filename=common.search_for_file(object["filename"],
                                            conf['paths']['base_search'],
                                            ['./','conf','files'],2)
            conf[key]['content']['txt'] = common.get_file_content(filename)

            vars = mdinst.get_vars_from_md_text(conf[key]['content']['txt'])
            for x in vars:
                logging.info("Override the parameter %s='%s'", x,vars[x])
                conf[key][x]=vars[x]
            # conf[key]['content']['txt'] = \
            #     Template(conf[key]['content']['txt']).render(conf[key])

            del conf[key]["content"]["filename"]

    return conf

# -----------------------------------------------------------------------------
def md2html(md_content, env, context):
    context['paths'] = env.template_conf['paths']
    my_renderer = renderer.RendererDispatch(jinja_env=env.jinja_env,
                                            context=context)
    html_converter = mistune.Markdown(renderer=my_renderer)

    return html_converter(md_content)

# -----------------------------------------------------------------------------
def txt2html(conf, env):
    for key in conf:
        if (isinstance(conf[key], dict)) and \
            ("content" in conf[key]) and \
            ("txt" in conf[key]["content"]):
            txt = conf[key]["content"]["txt"]
            conf[key]['content'] = \
                md2html(txt, env, conf[key])
            # print(conf[key]['content'])
    return conf

# -----------------------------------------------------------------------------
def htmlbody(conf, env):
    if 'email' not in conf:
        logging.warning("no email in config")
        return conf

    email=conf['email']

    if 'template' not in email:
        logging.warning("no template in email config")
        return conf
    if 'content' not in email:
        logging.warning("no content in email config")
        return conf

    html_body = \
        env.jinja_env.get_template(email['template']).render(email)
    
    conf['email']['html_body']=html_body
    common.set_file_content("essai.html", html_body)
    return conf

# -----------------------------------------------------------------------------
# Update meeting points
# -----------------------------------------------------------------------------
def new_email(conf):
    logging.debug("Create outlook email")
    outlook = win32.Dispatch('outlook.application')

    mail = outlook.CreateItem(0)
    if 'from' not in conf:
        return mail
    
    sender = conf['from']
    From = None
    for myEmailAddress in outlook.Session.Accounts:
        if sender in str(myEmailAddress):
            From = myEmailAddress
            break

    if From is not None:
        # This line basically calls the "mail.SendUsingAccount = xyz@email.com" outlook VBA command
        mail._oleobj_.Invoke(*(64209, 0, 8, 0, From))

    return mail


# -----------------------------------------------------------------------------
def __send_email(conf, cid={}):
    email = new_email(conf)
    
    email.To = ' ; '.join(conf['to']['list'])
    if 'cc' in conf and isinstance(conf['cc'], dict) and 'list' in conf['cc']:
        email.Cc = ' ; '.join(conf['cc']['list'])
    if 'Bcc' in conf and isinstance(conf['cc'], dict) and 'list' in conf['cc']:
        email.Cc = ' ; '.join(conf['bcc']['list'])
    email.Subject = conf['email']['subject']
    email.HTMLBody = conf['email']['html_body']
    # email.HTMLBody = Template(conf['email']['html_body']).render(conf['email'])

    # print('-----------------------------------------')
    # print(conf['email']['content'])
    # print('-----------------------------------------')
    # print(email.HTMLBody)
    # print('-----------------------------------------')

    for cidname in cid:
        att = email.Attachments.Add(cid[cidname], 1, 0)
        att.PropertyAccessor.SetProperty('http://schemas.microsoft.com/mapi/proptag/0x3712001F', cidname);
    
    if 'attachments' in conf['email']:
        list_files= conf['email']['attachments']
        for f in list_files:
            filename=common.search_for_file(f,
                                            conf['paths']['base_search'],
                                            ['./','conf','files'],2)
            email.Attachments.Add(filename)

    if conf['really_send']:
        email.Send()
    else:
        logging.info(" >>> Email is saved")
        email.Save()

    return conf

# -----------------------------------------------------------------------------
def send_email(conf):
    if ('to' not in conf) or ('list' not in conf['to']):
        logging.warning("there is no 'to' in the conf")
        return conf
    
    # search the cid
    cid={}
    search_folder = [conf['paths']['img']] + conf['paths']['base_search']
    current_text = conf['email']['html_body']
    # print("------------------------")
    # print(current_text)
    # print("------------------------")
    match_cid = re.search(__cid_re__, current_text)
    while match_cid is not None:
        name = match_cid.group('name')
        filename=common.search_for_file(name,
                                        search_folder,
                                        ['./','img', 'conf','files'],2)
        cid[name]=filename
        current_text = current_text[match_cid.end(0):]
        match_cid = re.search(__cid_re__, current_text)
        
    if ('individual_email' not in conf['to']) or \
        (not conf['to']['individual_email']):
        logging.info(" >>> send email to %s", conf['to']['list'])
        return __send_email(conf, cid)

    initial_list=[]
    for email in conf['to']['list']:
        initial_list.append(email)

    count = 0
    count_max = len(initial_list)
    for email in initial_list:
        count=count+1
        conf['to']['list'] = [email]
        logging.info(" %03d/%03d send email to %s", count, count_max, email)
        __send_email(conf, cid)

    conf['to']['list'] = initial_list

    return conf


# -----------------------------------------------------------------------------
def __get_this_folder():
    """ Return the folder of this script with frozen compatibility
    @return the folder of THIS script.
    """
    return os.path.split(os.path.abspath(os.path.realpath(
        __get_this_filename())))[0]

# -----------------------------------------------------------------------------
def __get_this_filename():
    """ Return the filename of this script with frozen compatibility
    @return the filename of THIS script.
    """
    return __file__ if not getattr(sys, 'frozen', False) else sys.executable
