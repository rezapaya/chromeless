import chromeless
import os
import shutil
from string import Template
import simplejson as json

class OSAppifier(object):
    def __init__(self):
        # instantiate a dirs object which has some important directories
        # as properties
        self.dirs = chromeless.Dirs()

        print "OSAppifier initialized"

    def _sub_and_copy(self, src, dst, mapping):
        template_content = ""
        with open(src, 'r') as f:
            template_content = f.read()
        s = Template(template_content)
        final_contents = s.substitute(mapping)
        with open(dst, 'w') as f:
            f.write(final_contents)

        
    def output_xulrunner_app(self, dir, browser_code_dir, browser_code_main, dev_mode,
                             harness_options, verbose=True):
        # XXX: maybe ALL of this can be shared code between platforms??
        print "Building xulrunner app in >%s< ..." % dir 
        
        # extract information about the application from appinfo.json
        app_info = chromeless.AppInfo(dir=browser_code_dir)

        res_dir = os.path.join(os.path.dirname(__file__), "resources")

        # copy all the template files which require no substitution
        template_dir = os.path.join(res_dir, "xulrunner.template")
        if verbose:
            print "  ... copying application template"

        for f in os.listdir(template_dir):
            src = os.path.join(template_dir, f)
            dst = os.path.join(dir, f)
            if (os.path.isdir(src)): 
                shutil.copytree(src, dst)
            else:
                shutil.copy(src, dst)

        # sub in application.ini
        if verbose:
            print "  ... creating application.ini"

        app_ini_template = os.path.join(res_dir, "application.ini.template")
        app_ini_path = os.path.join(dir, "application.ini")

        self._sub_and_copy(app_ini_template, app_ini_path, {
                "application_name": app_info.name,
                "application_vendor": app_info.vendor,
                "short_version": app_info.version,
                "build_id": app_info.build_id,
                "developer_email": app_info.developer_email
        })

        # now copy in packages
        # XXX: only copying in dependencies would be A Good Thing
        if verbose:
            print "  ... copying in CommonJS packages"
        shutil.copytree(os.path.join(self.dirs.cuddlefish_root, "packages"),
                        os.path.join(dir, "packages"))

        # and browser code
        if verbose:
            print "  ... copying in browser code (%s)" % browser_code_dir 
        shutil.copytree(browser_code_dir, os.path.join(dir, "browser_code"))

        # now munge harness_options a bit to get correct path to brtowser_code in
        browser_code_path = "browser_code"
        if browser_code_main:
            browser_code_path = os.path.join(browser_code_path, browser_code_main)
        static_opts = json.loads(harness_options['staticArgs'])
        static_opts["browser_embeded_path"] = browser_code_path
        harness_options['staticArgs'] = json.dumps(static_opts)

        # and write harness options
        if verbose:
            print "  ... writing harness options"

        with open(os.path.join(dir, "harness-options.json"), 'w') as f:
            f.write(json.dumps(harness_options, indent=4))
        
        # XXX: support for extra packages located outside of the packages/ directory!

        print "output_xulrunner_app called"        


    def output_app_shell(self, browser_code_dir, dev_mode, verbose=True):
        # first, determine the application name
        app_info = chromeless.AppInfo(dir=browser_code_dir)
        output_dir = os.path.join(self.dirs.build_dir, app_info.name) + ".app"

        if verbose:
            print "Building application in >%s< ..." % output_dir 

        # obliterate old directory if present
        if os.path.exists(output_dir):
            if verbose:
                print "  ... removing previous application"
            shutil.rmtree(output_dir)

        # now let's mock up a XUL.framework dir
        framework_dir = os.path.join(output_dir, "Contents", "Frameworks", "XUL.framework")
        os.makedirs(framework_dir)
        
        # create the current version dir
        cur_ver_dir = os.path.join(framework_dir, "Versions")
        os.makedirs(cur_ver_dir)
        cur_ver_dir = os.path.join(cur_ver_dir, "Current")
        xul_bin_src = os.path.join(self.dirs.build_dir, "xulrunner-sdk", "bin")

        # and recursivly copy in the bin/ directory out of the sdk 
        if verbose:
            print "  ... copying in xulrunner binaries"
        shutil.copytree(xul_bin_src, cur_ver_dir)

        # create links inside framework
        for f in ("XUL", "xulrunner-bin", "libxpcom.dylib"):
            tgt = os.path.relpath(os.path.join(cur_ver_dir, f), framework_dir)
            os.symlink(tgt, os.path.join(framework_dir, f))

        # now it's time to write a parameterized Info.plist
        if verbose:
            print "  ... writing Info.plist"
        info_plist_path = os.path.join(output_dir, "Contents", "Info.plist")
        template_path = os.path.join(os.path.dirname(__file__), "resources", "Info.plist.template")
        self._sub_and_copy(template_path, info_plist_path, {
                "application_name": app_info.name,
                "short_version": app_info.version,
                "full_version": (app_info.version + "." + app_info.build_id)
        })

        # we'll create the MacOS (binary) dir and copy over the xulrunner binary
        if verbose:
            print "  ... placing xulrunner binary"

        macos_dir = os.path.join(output_dir, "Contents", "MacOS")
        os.makedirs(macos_dir)
        xulrunner_stub_path = os.path.join(cur_ver_dir, "xulrunner")
        shutil.copy(xulrunner_stub_path, macos_dir)

        # Finally, create the resources dir (where the xulrunner application will live
        if verbose:
            print "  ... creating resources directory"
        resources_path = os.path.join(output_dir, "Contents", "Resources")
        os.makedirs(resources_path)

        return { "xulrunner_app_dir": resources_path } 