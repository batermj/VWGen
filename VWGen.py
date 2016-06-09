#!/usr/bin/env python

import platform
import os
import sys
import json
import optparse
import zipfile
import shutil
import web
import time
from blessed import Terminal

try:
    import urlparse
    from urllib import urlencode
except: # For Python 3
    import urllib.parse as urlparse
    from urllib.parse import urlencode

from docker import Client
from docker.errors import *

global client, ctr
web.host           = None
web.client         = None
web.container_name = None
web.ctr            = None
web.db_ctr         = None
web.source         = None
web.payloads       = None
web.path           = None

web.expose         = None
web.dbms           = None
web.modules        = None
web.dbms           = None


class Logger(object):

    # Color codes
    STD = "\033[0;0m"
    BLUE = "\033[1;34m"
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"

    def __init__(self):
        pass

    @classmethod
    def log(self, fmt_string, *args):
        if len(args) == 0:
            print(fmt_string)
        else:
            print(fmt_string.format(*args))
        sys.stdout.write(self.STD)


    @classmethod
    def logInfo(self, fmt_string, *args):
        sys.stdout.write(self.BLUE)
        self.log(fmt_string, *args)
        sys.stdout.write(self.STD)


    @classmethod
    def logError(self, fmt_string, *args):
        sys.stdout.write(self.RED)
        self.log(fmt_string, *args)
        sys.stdout.write(self.STD)


    @classmethod
    def logSuccess(self, fmt_string, *args):
        sys.stdout.write(self.GREEN)
        self.log(fmt_string, *args)
        sys.stdout.write(self.STD)


if platform.system() == 'Darwin' or platform.system() == 'Windows':
    try:
        from docker.utils import kwargs_from_env  # TLS problem, can be referenced from https://github.com/docker/machine/issues/1335
        web.host = '{0}'.format(urlparse.urlparse(os.environ['DOCKER_HOST']).netloc.split(':')[0])
        client = Client(base_url='{0}'.format(os.environ['DOCKER_HOST']))
        kwargs = kwargs_from_env()
        kwargs['tls'].assert_hostname = False
        client = Client(**kwargs)
    except KeyError:
        web.host = '127.0.0.1'
        client = Client(base_url='unix://var/run/docker.sock')
    except:
        Logger.logError("[ERROR] $DOCKER_HOST variable undefined! Exit...")
        sys.exit(1)
else:
    web.host = '127.0.0.1'
    client = Client(base_url='unix://var/run/docker.sock')


class switch(object):
    def __init__(self, value):
        self.value = value
        self.fall = False
 
    def __iter__(self):
        """Return the match method once, then stop"""
        yield self.match
        raise StopIteration
     
    def match(self, *args):
        """Indicate whether or not to enter a case suite"""
        if self.fall or not args:
            return True
        elif self.value in args: # changed for v1.5, see below
            self.fall = True
            return True
        else:
            return False


parent_dir = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), os.pardir))
if os.path.exists(os.path.join(parent_dir, "demo")):
    sys.path.append(parent_dir)
from demo.demo import Demo
THEME_DIR = os.path.dirname(sys.modules['demo'].__file__)

demo = Demo()  # testing for now
ctr = None

class time_limit(object):
    def __init__(self, seconds):
        self.seconds = seconds

    def __enter__(self):
        self.die_after = time.time() + self.seconds
        return self

    def __exit__(self, type, value, traceback):
        pass

    @property
    def timed_reset(self):
        self.die_after = time.time() + self.seconds

    @property
    def timed_out(self):
        return time.time() > self.die_after


class VWGen(object):

    def __init__(self, theme=None):
        self.color = 0
        self.theme_name = "startbootstrap-agency-1.0.6"  # startbootstrap-clean-blog-1.0.4, startbootstrap-agency-1.0.6
        self.theme_path = os.path.join(THEME_DIR, "themes", self.theme_name)
        self.output = os.path.join(THEME_DIR, "output")
        self.backend = ""
        self.image = ""
        self.dbms = ""
        self.attacks = []
        self.options = None
        self.source = None


    def __initBackend(self):
        # Do Backend Environment Initialization
        self = self


    def _index__initThemeEnv(self):
        self.__initBackend()
        with zipfile.ZipFile(self.theme_path + '.zip', "r") as z:
            z.extractall(self.output)
        with open(os.path.join(self.output, self.theme_name, "index.html"), 'rb') as src:
            self.source = src.read()


    def __initAttacks(self):
        from core.attack import attack

        Logger.logInfo("[INFO] Loading modules:")
        Logger.logInfo(u"[INFO] " + "\t {0}".format(u", ".join(attack.modules)))

        for mod_name in attack.modules:
            mod = __import__("core.attack." + mod_name, fromlist=attack.modules)
            mod_instance = getattr(mod, mod_name)()

            self.attacks.append(mod_instance)
            self.attacks.sort(lambda a, b: a.PRIORITY - b.PRIORITY)

        # Custom list of modules was specified
        if self.options is not None:
            # First deactivate all modules
            for attack_module in self.attacks:
                attack_module.doReturn = False

            opts = self.options.split(",")

            for opt in opts:
                if opt.strip() == "":
                    continue

                module = opt

                # deactivate some module options
                if module.startswith("-"):
                    module = module[1:]
                    if module == "all":
                        for attack_module in self.attacks:
                            if attack_module.name in attack.lists:
                                attack_module.doReturn = False
                    else:
                        found = False
                        for attack_module in self.attacks:
                            if attack_module.name == module:
                                found = True
                                attack_module.doReturn = False
                        if not found:
                            Logger.logError("[ERROR] Unable to find a module named {0}".format(module))

                # activate some module options
                else:
                    if module.startswith("+"):
                        module = module[1:]
                    else:
                        module = attack.default
                    if module == "all":
                        Logger.logError("[ERROR] Keyword 'all' was not safe enough for activating all modules at once. Specify modules names instead.")
                    else:
                        found = False
                        for attack_module in self.attacks:
                            if attack_module.name == module:
                                found = True
                                attack_module.doReturn = True
                        if not found:
                            Logger.logError("[ERROR] Unable to find a module named {0}".format(module))


    def setColor(self):
        self.color = 1


    def generate(self):
        self.__initAttacks()

        deps = None
        for index, x in enumerate(self.attacks):
            if x.doReturn:
                print('')
                if x.require:
                    x.loadRequire([y for y in self.attacks if y.name in x.require])
                    deps = ", ".join([y.name for y in self.attacks if y.name in x.require])

        for x in self.attacks:
            if x.doReturn:
                x.logG(u"[+] Launching module {0}".format(x.name))
                x.logG(u"   and its deps: {0}".format(deps if deps is not None else 'None'))
                if self.color == 1:
                    x.setColor()
                target_dir = os.path.join(self.output, self.theme_name)
                web.payloads = x.Job(self.source, self.backend, self.dbms, target_dir)

        return [self.output, os.path.join(self.output, self.theme_name)]


    def setBackend(self, backend="php"):
        self.backend = backend
        for case in switch(self.backend):
            if case('php'):
                self.image = 'richarvey/nginx-php-fpm'
                self.mount_point = '/usr/share/nginx/html'
                break
            if case('php7'):
                self.image = 'richarvey/nginx-php-fpm:beta70'
                self.mount_point = '/usr/share/nginx/html'
                break
            if case():
                Logger.logError("[ERROR] Backend {0} not supported!".format(self.backend))
                sys.exit(1)


    def setDBMS(self, DBMS):
        self.dbms = DBMS
        web.container_name = '{0}_ctr'.format(self.dbms)
        if self.dbms is not None:
            if self.dbms == 'Mysql':
                try:
                    web.db_ctr = web.client.create_container(image='mysql', name='{0}'.format(web.container_name),
                        environment={
                            "MYSQL_ROOT_PASSWORD": "root_password",
                            "MYSQL_DATABASE": "root_mysql"
                        }
                    )
                except APIError:
                    for line in web.client.pull('mysql', tag="latest", stream=True):
                        Logger.logInfo("[INFO]" + json.dumps(json.loads(line), indent=4))
                    web.db_ctr = web.client.create_container(image='mysql', name='{0}'.format(web.container_name),
                        environment={
                            "MYSQL_ROOT_PASSWORD": "root_password",
                            "MYSQL_DATABASE": "root_mysql"
                        }
                    )
                web.client.start(web.db_ctr)
            elif self.dbms == 'Mongo':
                try:
                    web.db_ctr = web.client.create_container(image='mongo', name='{0}'.format(web.container_name))
                except APIError:
                    for line in web.client.pull('mongo', tag="latest", stream=True):
                        Logger.logInfo("[INFO]" + json.dumps(json.loads(line), indent=4))
                    web.db_ctr = web.client.create_container(image='mongo', name='{0}'.format(web.container_name))
                web.client.start(web.db_ctr)


    def setModules(self, options=None):
        self.options = options


if __name__ == "__main__":
    try:
        usage = "usage: %prog [options] arg1 arg2"
        p = optparse.OptionParser(usage=usage, version="VWGen v0.1")
        p.add_option('--expose',
                    action="store", dest="expose", type="int", default=80, metavar='EXPOSE_PORT',
                    help="configure the port of the host for container binding (Default: 80)")
        p.add_option('--database',
                    action="store", dest="dbms", type="string", default=None, metavar='DBMS',
                    help="configure the dbms for container linking")
        p.add_option('--module',
                    action="store", dest="modules", default="+unfilter", metavar='LIST',
                    help="list of modules to load (Default: +unfilter)")
        p.add_option('--color',
                    action="store_true", dest="color",
                    help="set terminal color")
        group = optparse.OptionGroup(p, 'Not supported', 'Following options are still in development!')
        group.add_option('--console', '-c',
                    action="store_true", metavar='CONSOLE',
                    help="enter console mode")
        group.add_option('--verbose', '-v',
                    action="store_true", dest="verbosity", metavar='LEVEL',
                    help="set verbosity level")
        group.add_option('--file',
                    action="store", dest="source", type="string", default=None, metavar='FILENAME',
                    help="specify the file that VWGen will gonna operate on")
        p.add_option_group(group)
        options, arguments = p.parse_args()

        # set sys.argv to the remaining arguments after
        # everything consumed by optparse
        if options.source is not None:
            web.source = options.source

            # This is not required if you've installed pycparser into
            # your site-packages/ with setup.py
            #
            sys.path.extend(['./core/pycparser'])
            from pycparser import parse_file

            ast = parse_file(web.source, use_cpp=True,
                    cpp_path='gcc',
                    cpp_args=['-E', r'-Iutils/fake_libc_include'])

            ast.show()

        web.expose = options.expose
        web.dbms = options.dbms
        web.modules = options.modules

        web.client = client
        web.ctr = ctr
        gen = VWGen()
        if options.color:
            gen.setColor()
        gen.setBackend()
        gen.setDBMS(web.dbms)
        gen.setModules(web.modules)
        gen._index__initThemeEnv()
        [folder, path] = gen.generate()
        web.path = path
        if web.payloads is not None:
            try:
                web.ctr = web.client.create_container(image='{0}'.format(gen.image), ports=[80], volumes=['{0}'.format(gen.mount_point), '/etc/php5/fpm/php.ini'],
                    host_config=web.client.create_host_config(
                        port_bindings={
                            80: web.expose
                        },
                        binds={
                            "{0}".format(web.path): {
                                'bind': '{0}'.format(gen.mount_point),
                                'mode': 'rw',
                            },
                            "{0}".format(os.path.join(web.path, 'php.ini')): {
                                'bind': '/etc/php5/fpm/php.ini',
                                'mode': 'ro'
                            }
                        },
                        links={ '{0}'.format(web.container_name): '{0}'.format(gen.dbms) } if gen.dbms is not None else None
                    ),
                    environment={ "DEBS": "expect" } if web.payloads['extra'] and web.payloads['extra']['expect'] == 1 else None
                , name='VW')
            except APIError:
                for line in web.client.pull('{0}'.format(gen.image), tag="latest", stream=True):
                    Logger.logInfo("[INFO]" + json.dumps(json.loads(line), indent=4))
                web.ctr = web.client.create_container(image='{0}'.format(gen.image), ports=[80], volumes=['{0}'.format(gen.mount_point), '/etc/php5/fpm/php.ini'],
                    host_config=web.client.create_host_config(
                        port_bindings={
                            80: web.expose
                        },
                        binds={
                            "{0}".format(web.path): {
                                'bind': '{0}'.format(gen.mount_point),
                                'mode': 'rw',
                            },
                            "{0}".format(os.path.join(web.path, 'php.ini')): {
                                'bind': '/etc/php5/fpm/php.ini',
                                'mode': 'ro'
                            }
                        },
                        links={ '{0}'.format(web.container_name): '{0}'.format(gen.dbms) } if gen.dbms is not None else None
                    ),
                    environment={ "DEBS": "expect" } if web.payloads['extra'] and web.payloads['extra']['expect'] == 1 else None
                , name='VW')

            web.client.start(web.ctr)

            url = ['http', '{0}:{1}'.format(web.host, web.expose), '/', '', '', '']
            params = {}

            if web.payloads['key'] is not None:
                for index, _ in enumerate(web.payloads['key']):
                    params.update({'{0}'.format(web.payloads['key'][index]): '{0}'.format(web.payloads['value'][index])})

            query = params

            url[4] = urlencode(query)

            t = Terminal()
            with t.location(0, t.height - 1):
                Logger.logSuccess(t.center(t.blink("[SUCCESS] Browse: {0}".format(urlparse.urlunparse(url)))))

            with time_limit(600) as t:
                for line in web.client.logs(web.ctr, stderr=False, stream=True):
                    time.sleep(0.1)
                    Logger.logInfo("[INFO] " + line)
                    if t.timed_out:
                        break
                    else:
                        t.timed_reset
    except (KeyboardInterrupt, SystemExit, RuntimeError):
        Logger.logInfo("[INFO] See you next time.")
    except APIError as e:
        Logger.logError("\n" + "[ERROR] " + str(e.args[0]))
        Logger.logInfo("\n[INFO] Taking you to safely leave the program.")
    finally:
        try:
            shutil.rmtree(web.path)
            web.client.remove_container(web.db_ctr, force=True) if web.db_ctr is not None else None
            web.client.remove_container(web.ctr, force=True)
        except (TypeError, NullResource):
            pass
        except APIError:
            Logger.logError("[ERROR] Some APIErrors found! You may need to remove containers by yourself.")
