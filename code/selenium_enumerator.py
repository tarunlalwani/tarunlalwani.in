import json
import os
import urllib

from fabric.api import local, env
import marionette_driver

from marionette_harness import Marionette

import sys
import psutil

from fabric.context_managers import hide, settings
from selenium import webdriver
from selenium.common.exceptions import WebDriverException

OS_DETERMINED = None
IS_MAC = True
IS_WINDOWS = None
IS_LINUX = None

if OS_DETERMINED is None:
    if sys.platform == "darwin":
        IS_MAC = True


def run_cmd(cmd):
    with settings(hide('running', 'stdout', 'stderr', 'warnings', "aborts", "status"),
                  warn_only=True):
        try:
            data = local(cmd, capture=True)
        except Exception as ex:
            pass
        return data


def get_processes_id(process_name):
    PIDS = None

    if IS_MAC:
        PIDS = run_cmd("lsof -c '{}' -t".format(process_name)).split("\n")
    return PIDS


def get_processes_info(pids):
    return [
        {
            "pid": int(pid),
            "cmd": psutil.Process(pid=int(pid)).cmdline()
        }
        for pid in pids]


def get_ports_from_process(processes):
    ports = []

    for process in processes:
        process_name = process['cmd'][0]

        if process_name == "geckodriver" or process_name == "chromedriver":
            port_index = process['cmd'].index("--port") + 1
            if port_index > 0:
                port = process['cmd'][port_index]
                ports.append({"name": process_name, "port": port, "pid": process['pid']})
    return ports


def get_running_firefox(geckodriver=True):
    if not geckodriver:
        raise NotImplemented()


# ins2 = Marionette(port=64765)
# ins2.start_session()
#
# # ins2 = Marionette(host="127.0.0.1", port=60860)
# # ins2.start_session()
# # ins = marionette_driver.geckoinstance.GeckoInstance(host="127.0.0.1", port=60860)
#
#
#
# # driver = webdriver.Firefox()
# # driver.get("http://www.google.com")
#
# pids = get_processes_id("geckodriver")
# processes = get_processes_info(pids)
# data = get_ports_from_process(processes)
#
# print data
#
# print "we are here"

# from selenium import webdriver
#
# driver = webdriver.Firefox()
# executor_url = driver.command_executor._url
# session_id = driver.session_id
# driver.get("http://tarunlalwani.com")
#
# print session_id
# print executor_url
# print driver.capabilities


def get_sessions_from_executor(executor_url):
    sessions_req = urllib.request.urlopen(executor_url + "/sessions")
    sessions_data = sessions_req.read()
    sessions_encoding = sessions_req.info().get_content_charset('utf-8')

    sessions = json.loads(sessions_data.decode(sessions_encoding))

    for session in sessions["value"]:
        yield (session["id"], session["capabilities"]["browserName"])


def create_driver_session(session_id, executor_url):
    # type: (str, str) -> WebDriver
    from selenium.webdriver.remote.webdriver import WebDriver as RemoteWebDriver

    # Save the original function, so we can revert our patch
    org_command_execute = RemoteWebDriver.execute

    def new_command_execute(self, command, params=None):
        if command == "newSession":
            # Mock the response
            return {'success': 0, 'value': None, 'sessionId': session_id}
        else:
            return org_command_execute(self, command, params)

    # Patch the function before creating the driver object
    RemoteWebDriver.execute = new_command_execute

    new_driver = webdriver.Remote(command_executor=executor_url, desired_capabilities={})
    new_driver.session_id = session_id

    # Replace the patched function with original function
    RemoteWebDriver.execute = org_command_execute

    return new_driver

# driver2 = create_driver_session(session_id, executor_url)
# print driver2.current_url

#ins2 = Marionette(host="127.0.0.1", port=65090)
# ins2.start_session()
# ins = marionette_driver.geckoinstance.GeckoInstance(host="127.0.0.1", port=60860)
# ins2.
#print ins2.session_id


def create_driver_session_firefox(executor_url):
    _driver = create_driver_session("dummy", executor_url)

    try:
        _driver.current_url
    except WebDriverException as ex:
        session_id = ex.msg.replace("Got unexpected session id dummy expected ", "")
        if session_id:
            _driver = create_driver_session(session_id, executor_url)
            return _driver

    raise Exception("failed to find session id and create driver")

driver = create_driver_session_firefox("http://127.0.0.1:52099")

driver.get("http://google.com")