#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
#
# Copyright (c) 2018 Florent TOURNOIS
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# -----------------------------------------------------------------------------

import logging
import sys
import os
import os.path
import re

import pyoutlookmailing as pyom

# -----------------------------------------------------------------------------
def my_super_function(messages,undeliverable):    
        list_of_undelivered_email_addresses = []
        last_n_days = dt.datetime.now() - dt.timedelta(days = 25)
        messages = messages.Restrict("[ReceivedTime] >= '" +last_n_days.strftime('%m/%d/%Y %H:%M %p')+"'")
        rl= list()
        pattern = re.compile('To: ".*\n?',re.MULTILINE)       
        for counter, message in enumerate(messages):
                message.SaveAs("undeliverable_emails.msg")
                f = r'some_absolute_path'  
                try:
                        msg = extract_msg.Message(f)
                        print(counter)
                        if msg.body.find("undeliverable")!= -1 or msg.body.find("Undeliverable")!= -1 or msg.subject.find("Undeliverable")!= -1 or msg.subject.find("undeliverable")!= -1 or msg.body.find("wasn't found at")!= -1:
                                rl.append(message)
                                m = re.search(pattern, msg.body)
                                m = m[0]
                                mail_final = m.split('"')[1]   
                                list_of_undelivered_email_addresses.append(mail_final)
                                list_of_undelivered_email_addresses=list(filter(None, list_of_undelivered_email_addresses))
                        else:
                                print('else')
                except:
                        pass
        if len(rl) ==0:
                pass
        else:
                for m in tqdm(rl):
                        m.Move(undeliverable)
        return list_of_undelivered_email_addresses

# -----------------------------------------------------------------------------
class find_undelivered:
    
# -----------------------------------------------------------------------------
def test_email(item):
    if item.Class == 46:
        list_email = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', str(item.Body))
        print(list_email)

    pattern = re.compile('To: ".*\n?',re.MULTILINE) 

    msg = str(item.subject + " " + item.body).lower()


    tokens=["undeliverable", "wasn't found at", "non remis", 
            "not delivery", "undelivered", "returned mail",
            "delivery status notification (failure)"]

    find=False

    while (not find) and len(tokens)>0:
        find=msg.find(tokens[0])!= -1
        tokens=tokens[1:] 

    if find:
        list_email = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', str(item.Body))
        if len(list_email)>0:
            print(list_email[0])

    return


# -----------------------------------------------------------------------------
def parse_all_emails(root_folder, folder_path, fun_email):
    if len(folder_path) == 0:
        messages = root_folder.Items
        count = 0
        max = len(messages)
        for item in messages: 
            count=count+1
            logging.info("%05d / %05d"%(count, max))
            fun_email(item)
        return

    for folder in root_folder.Folders:
        if str(folder) == folder_path[0]:
            parse_all_emails(folder, folder_path[1:], fun_email)


# # -----------------------------------------------------------------------------
# def parse_all_folder(folders, previous_name = "root", folder_name = "Mois en cours"):
#     for folder in folders:
#         next_name = previous_name+" / "+str(folder) 
#         if str(folder) == folder_name:
#             print(next_name + " --> " + str(len(folder.Items)))
#         if len(folder.Folders)>0:
#             parse_all_folder(folder.Folders, next_name)

# -----------------------------------------------------------------------------
def test_undelivered():
    import win32com.client

    outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    accounts= win32com.client.Dispatch("Outlook.Application").Session.Accounts

    parse_all_emails(outlook, ["ANTS - Florent Tournois", "Mois en cours"], 
                    test_email)

    for account in accounts:
        print(account.DeliveryStore.DisplayName)
        inbox = outlook.Folders(account.DeliveryStore.DisplayName)
        # if account.DeliveryStore.DisplayName == 'place_your_account_name_here':
        #     for folder in inbox.Folders:

# -----------------------------------------------------------------------------
def test_common():
    conf = pyom.load_conf("test.conf", __get_this_folder())
    conf = pyom.compute_conf(conf)
    pyom.send_email(conf)

# -----------------------------------------------------------------------------
def test_gdc():
    conf = pyom.load_conf("invitation_gdc_en.conf", __get_this_folder())
    conf = pyom.compute_conf(conf)
    pyom.send_email(conf)

# -----------------------------------------------------------------------------
def test_02():
    conf = pyom.load_conf("test_02.conf", __get_this_folder())
    conf = pyom.compute_conf(conf)
    pyom.send_email(conf)

# -----------------------------------------------------------------------------
def test_conf(config_filename):
    conf = pyom.load_conf(config_filename, __get_this_folder())
    conf = pyom.compute_conf(conf)
    pyom.send_email(conf)

# -----------------------------------------------------------------------------
def test_gdansk():
    conf = pyom.load_conf("invitation_gdansk_en.conf", __get_this_folder())
    conf = pyom.compute_conf(conf)
    pyom.send_email(conf)

# -----------------------------------------------------------------------------
def test_convert_img():
    img = pyom.html_img("./template/img/EUDIW Unfold4.png")
    print(img)


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
# Set up the logging system
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

# -----------------------------------------------------------------------------
# Main script call only if this script is runned directly
# -----------------------------------------------------------------------------
def __main():
    # ------------------------------------
    logging.info('Started %s', __get_this_filename())
    logging.info('The Python version is %s.%s.%s',
                 sys.version_info[0], sys.version_info[1], sys.version_info[2])

    test_undelivered()

    logging.info('Finished')
    # ------------------------------------


# -----------------------------------------------------------------------------
# Call main function if the script is main
# Exec only if this script is runned directly
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    __set_logging_system()
    __main()
