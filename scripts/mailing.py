#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# @copyright Copyright (C) Florent TOURNOIS - All Rights Reserved
# 	All Rights Reserved.
# 	Unauthorized copying of this file, via any medium is strictly prohibited
# 	Dissemination of this information or reproduction of this material
# 	is strictly forbidden unless prior written permission is obtained
# 	from Florent TOURNOIS.
# -----------------------------------------------------------------------------

import logging
import sys
import os
import traceback
import argparse
import ctypes  # An included library with Python install.

import pyoutlookmailing as pyom

# -----------------------------------------------------------------------------
# test the filename for argparsing
#
# @param filename The filename
# @return filename.
# -----------------------------------------------------------------------------
def is_real_file(filename):
    """
    'Type' for argparse - checks that file exists but does not open.
    """
    if not os.path.isfile(filename):
        # Argparse uses the ArgumentTypeError to give a rejection message like:
        # error: argument input: x does not exist
        raise argparse.ArgumentTypeError(f"{filename} does not exist")
    return filename


# -----------------------------------------------------------------------------
def message_box(text, title):
    """Create a windows message box

    Args:
        text (string): The message
        title (string): The title of the windows
    """
    ctypes.windll.user32.MessageBoxW(0, text, title, 0)


# -----------------------------------------------------------------------------
def get_parser_for_command_line():
    """Define the parsing of arguments of the command line

    Returns:
        parser: the parser
    """
    description = "Sen email from conf file"

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--conf', dest="conf_filename", required=True,
                        type=is_real_file,
                        help="the configuration file in yaml", metavar="FILE")
    parser.add_argument('--send-mail', dest="send_mail", required=False,
                        choices=['yes', 'no'], default='no',
                        help="Send email or just draft")
    parser.add_argument('--windows', action='store_true', dest='windows',
                        help='Define if we need all popups windows.')
    parser.add_argument('--verbose', action='store_true', dest='verbose',
                        help='Put the logging system on the console for info.')

    return parser

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


# -----------------------------------------------------------------------------
# Logging system
# -----------------------------------------------------------------------------
def __set_logging_system():
    log_filename = os.path.splitext(os.path.abspath(
        os.path.realpath(__get_this_filename())))[0] + '.log'
    logging.basicConfig(filename=log_filename, level=logging.DEBUG,
                        format='%(asctime)s: %(message)s',
                        datefmt='%m/%d/%Y %I:%M:%S %p')
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    # set a format which is simpler for console use
    formatter = logging.Formatter('%(asctime)s: %(levelname)-8s %(message)s')
    # tell the handler to use this format
    console.setFormatter(formatter)
    # add the handler to the root logger
    logging.getLogger('').addHandler(console)
    return console

# -----------------------------------------------------------------------------
# Main script
# -----------------------------------------------------------------------------
def __main():
    console = __set_logging_system()
    # ------------------------------------
    logging.info('+')
    logging.info('-------------------------------------------------------->>')
    logging.info('Started %s', __get_this_filename())
    logging.info('The Python version is %s.%s.%s',
                 sys.version_info[0], sys.version_info[1], sys.version_info[2])

    try:
        parser = get_parser_for_command_line()
        logging.info("parsing args")
        args = parser.parse_args()
        logging.info("parsing done")

        if args.verbose:
            console.setLevel(logging.INFO)

        logging.info("conf_filename=%s", args.conf_filename)
        logging.info("send_mail=%s", repr(args.send_mail))
        logging.info("verbose=%s", args.verbose)

        args.send_mail_bool = (args.send_mail == "yes")

        conf = pyom.load_conf(args.conf_filename, __get_this_folder())
        conf = pyom.compute_conf(conf)


    except argparse.ArgumentError as errmsg:
        logging.error(str(errmsg))
        if ('args' in locals()) and (args.windows):
            message_box(text=parser.format_usage(), title='Usage')

    except SystemExit:
        if ('args' in locals()) and (args.windows):
            message_box(text=parser.format_help(), title='Help')

    except Exception as ex:
        logging.error(str(ex))
        if ('args' in locals()) and (args.windows):
            message_box(text=str(ex), title='Usage')

    except:
        var = traceback.format_exc()
        logging.error('Unknown error : \n %s', var)
        if ('args' in locals()) and (args.windows):
            message_box(text='Unknown error : \n' + var,
                        title='Error in this program')
        # raise

    logging.info('Finished')
    logging.info('<<--------------------------------------------------------')
    logging.info('+')
    # ------------------------------------

# -----------------------------------------------------------------------------
# Call main if the script is main
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    __main()
